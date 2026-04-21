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
