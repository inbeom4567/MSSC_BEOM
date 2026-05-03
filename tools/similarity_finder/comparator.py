"""유사문제 찾기 comparator — Claude API 래퍼 + 프롬프트 빌더 + JSON 파서."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import anthropic


_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompt.txt"
_LOCAL_ENV_PATH = Path(__file__).resolve().parent / ".env"
_BACKEND_ENV_PATH = Path(__file__).resolve().parent.parent.parent / "backend" / ".env"

# 모델별 단가 (USD per 1M tokens, 2026-04 기준)
# cache_write = 1.25x input, cache_read = 0.1x input
_PRICING = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00,
                          "cache_write": 3.75, "cache_read": 0.30},
    "claude-opus-4-7":   {"input": 15.00, "output": 75.00,
                          "cache_write": 18.75, "cache_read": 1.50},
}
_USD_TO_KRW = 1380  # 근사치 (표시용)


def _load_system_prompt() -> str:
    return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _read_key_from_env_file(path: Path) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("ANTHROPIC_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _load_api_key() -> str:
    # 우선순위: 유사문항 전용 .env → 환경변수 → backend/.env
    key = _read_key_from_env_file(_LOCAL_ENV_PATH)
    if key:
        return key
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    key = _read_key_from_env_file(_BACKEND_ENV_PATH)
    if key:
        return key
    raise RuntimeError(
        f"ANTHROPIC_API_KEY를 찾지 못했습니다.\n"
        f"{_LOCAL_ENV_PATH} 파일을 만들고 다음을 입력하세요:\n"
        f"ANTHROPIC_API_KEY=sk-ant-...여기에-키-붙여넣기..."
    )


def _load_client():
    return anthropic.Anthropic(api_key=_load_api_key())


def compare(
    original: str,
    problems: list[dict],
    model: str = "claude-sonnet-4-6",
    chunk_size: int = 100,
    progress_callback=None,
) -> dict:
    """원본 문제와 문제집을 비교해 유사 문제 번호 반환.

    Args:
        original: 원본 문제 텍스트 (`read_hwpx` 결과).
        problems: `split_problems` 결과 리스트.
        model: claude-sonnet-4-6 또는 claude-opus-4-7.
        chunk_size: 한 번에 보낼 최대 문제 수.
        progress_callback: 진행 알림 callable(str). 없으면 무시.

    Returns:
        {"쌍둥이": [{"번호": int, "이유": str}, ...], "유형유사": [...]}
    """
    system = _load_system_prompt()
    client = _load_client()
    chunks = chunk_problems(problems, chunk_size=chunk_size)

    chunk_results = []
    usage_totals = {"input_tokens": 0, "output_tokens": 0,
                    "cache_write": 0, "cache_read": 0}
    for idx, chunk in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(f"Claude 호출 중 ({idx}/{len(chunks)})…")

        user_message = build_user_message(original, chunk)
        raw_text, usage = _call_claude(client, system, user_message, model)
        chunk_results.append(parse_response(raw_text))
        for k in usage_totals:
            usage_totals[k] += usage.get(k, 0)

    merged = merge_results(chunk_results)
    merged["_meta"] = {
        "model": model,
        "usage": usage_totals,
        "cost": compute_cost(model, usage_totals),
    }
    return merged


def _call_claude(client, system: str, user: str, model: str, retry: bool = True):
    """Claude 호출 + JSON 파싱 실패 시 1회 재시도. (text, usage_dict) 반환."""
    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        u = response.usage
        usage = {
            "input_tokens": getattr(u, "input_tokens", 0) or 0,
            "output_tokens": getattr(u, "output_tokens", 0) or 0,
            "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0,
            "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
        }
        return response.content[0].text, usage
    except Exception:
        if retry:
            return _call_claude(client, system, user, model, retry=False)
        raise


def compute_cost(model: str, usage: dict) -> dict:
    """usage 토큰 수로부터 USD/KRW 비용 계산. 알 수 없는 모델이면 0 반환."""
    p = _PRICING.get(model)
    if not p:
        return {"usd": 0.0, "krw": 0}
    usd = (
        usage.get("input_tokens", 0) * p["input"]
        + usage.get("output_tokens", 0) * p["output"]
        + usage.get("cache_write", 0) * p["cache_write"]
        + usage.get("cache_read", 0) * p["cache_read"]
    ) / 1_000_000
    return {"usd": usd, "krw": int(round(usd * _USD_TO_KRW))}


def parse_response(raw: str) -> dict:
    """Claude 응답에서 JSON을 추출해 {"쌍둥이": [...], "유형유사": [...]} 반환.

    마크다운 코드펜스(```json ... ```)를 벗기고, 키가 누락되면 빈 리스트로 채움.
    유효한 JSON이 없으면 ValueError.
    """
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude 응답을 JSON으로 파싱 실패: {e}")

    if not isinstance(data, dict):
        raise ValueError(f"응답이 객체가 아님: {type(data).__name__}")

    return {
        "쌍둥이": data.get("쌍둥이", []),
        "유형유사": data.get("유형유사", []),
    }


def build_user_message(original: str, problems: list[dict]) -> str:
    """원본 문제 + 문제집을 Claude에게 보낼 사용자 메시지로 조립.

    Args:
        original: 원본 HWPX에서 추출한 텍스트.
        problems: split_problems() 결과. 각 항목 {"number": int, "text": str}.

    Returns:
        Claude user message 전체 문자열.
    """
    lines = ["# 원본 문제", original.strip(), "", f"# 문제집 (총 {len(problems)}문제)"]
    for p in problems:
        lines.append(f"## {p['number']}번")
        lines.append(p['text'].strip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def chunk_problems(problems: list[dict], chunk_size: int = 100) -> list[list[dict]]:
    """문제집이 너무 크면 chunk_size 단위로 분할.

    Args:
        problems: 문제 리스트.
        chunk_size: 한 청크당 최대 문제 수.

    Returns:
        분할된 문제 청크 리스트. 빈 리스트면 빈 리스트 반환.
    """
    if not problems:
        return []
    return [problems[i : i + chunk_size] for i in range(0, len(problems), chunk_size)]


def merge_results(chunk_results: list[dict]) -> dict:
    """배치 결과들을 병합. 번호 중복은 첫 번째 발견만 유지.

    Args:
        chunk_results: 각 청크의 비교 결과 리스트.
                      각 항목은 {"쌍둥이": [...], "유형유사": [...]} 형태.

    Returns:
        병합된 결과. 번호 중복은 제거됨.
    """
    merged = {"쌍둥이": [], "유형유사": []}
    seen = {"쌍둥이": set(), "유형유사": set()}
    for result in chunk_results:
        for bucket in ("쌍둥이", "유형유사"):
            for item in result.get(bucket, []):
                num = item.get("번호")
                if num is None or num in seen[bucket]:
                    continue
                seen[bucket].add(num)
                merged[bucket].append(item)
    return merged
