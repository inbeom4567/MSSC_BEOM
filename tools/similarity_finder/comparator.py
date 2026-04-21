"""유사문제 찾기 comparator — Claude API 래퍼 + 프롬프트 빌더 + JSON 파서."""
from __future__ import annotations

import json
import re


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
