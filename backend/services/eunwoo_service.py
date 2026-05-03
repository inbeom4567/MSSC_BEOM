"""차은우 Gemini 초안 서비스.

Task #7 — SVG 부품 라벨링 초안 자동 생성.

흐름:
    1. SVG 본문 → svg_to_png (있으면) 로 PNG base64 변환
       (svg_to_png 미존재 시 SVG 텍스트 자체를 Gemini에 전달)
    2. PNG + 시스템프롬프트(eunwoo_system_prompt.txt) + 응답 스키마 → Gemini
    3. Gemini 응답 JSON 파싱 → AiDraft 변환
    4. 디스크 캐싱 (backend/data/svg_library/ai_drafts/{part_id}.json)

에러 처리:
    - GEMINI_API_KEY 없음 / Gemini 호출 실패 → 빈 AiDraft 반환 (서비스는 유지)
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

from models.svg_part import AiDraft, ParamDef
from services import svg_library_service

load_dotenv()
logger = logging.getLogger(__name__)


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "eunwoo_system_prompt.txt"
)


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------


def _load_system_prompt() -> str:
    if not _PROMPT_PATH.exists():
        logger.warning(f"eunwoo_system_prompt.txt 없음 — 기본 프롬프트 사용")
        return (
            "너는 차은우다. 입력된 SVG가 무슨 그림인지 추정해 JSON 라벨 초안을 "
            "만들고 형님(교사)께 확인을 요청한다."
        )
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _try_render_png(part_svg: str) -> tuple[str | None, str]:
    """SVG → PNG base64 시도.

    Task #4.5의 svg_to_png 모듈이 아직 미구현일 수 있어 try/except로 보호.
    실패 시 (None, 사유) 반환.
    """
    try:
        from services.svg_to_png import svg_to_png  # type: ignore[import-not-found]
    except Exception as e:  # noqa: BLE001
        return None, f"svg_to_png 미존재: {e}"

    try:
        png_bytes = svg_to_png(part_svg)  # bytes 반환 가정
        return base64.b64encode(png_bytes).decode(), "ok"
    except Exception as e:  # noqa: BLE001
        return None, f"svg_to_png 호출 실패: {e}"


def _empty_draft(note: str) -> AiDraft:
    return AiDraft(
        name="",
        category="",
        subcategory="",
        tags=[],
        variable_params=[],
        confidence=0.0,
        questions_for_teacher=[],
        gemini_raw=f"[draft skipped] {note}",
    )


def _parse_gemini_text_to_draft(text: str) -> AiDraft:
    """Gemini 응답 텍스트(JSON) → AiDraft 변환.

    eunwoo_system_prompt.txt 의 출력 스키마 기준:
        { "message": "...", "draft": {...}, "questions_for_teacher": [...] }
    """
    raw = text.strip()
    json_str = raw
    # ```json ... ``` 코드블록 제거
    if "```" in raw:
        m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
        if m:
            json_str = m.group(1)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"Gemini 응답 JSON 파싱 실패: {e} — 본문 일부: {raw[:200]}")
        return AiDraft(gemini_raw=raw)

    draft_block = data.get("draft", {}) if isinstance(data, dict) else {}
    questions = data.get("questions_for_teacher", []) if isinstance(data, dict) else []

    params: list[ParamDef] = []
    for pd in draft_block.get("variable_params", []) or []:
        try:
            params.append(ParamDef.model_validate(pd))
        except Exception as e:  # noqa: BLE001
            logger.debug(f"ParamDef 검증 실패 {pd!r}: {e}")

    confidence = draft_block.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    return AiDraft(
        name=str(draft_block.get("name", "")),
        category=str(draft_block.get("category", "")),
        subcategory=str(draft_block.get("subcategory", "")),
        tags=[str(t) for t in (draft_block.get("tags") or [])],
        variable_params=params,
        confidence=confidence,
        questions_for_teacher=[str(q) for q in (questions or [])],
        gemini_raw=raw,
    )


# ---------------------------------------------------------------------------
# 클라이언트
# ---------------------------------------------------------------------------


class EunwooService:
    """SVG 부품 라벨링 초안 생성 — 캐시 우선, Gemini 호출은 미스 시에만."""

    def __init__(self, model: str = GEMINI_MODEL, api_key: str | None = None):
        self.model = model
        self.api_key = api_key if api_key is not None else GEMINI_API_KEY
        self._system_prompt = _load_system_prompt()

    # ---- 공개 API ----------------------------------------------------------

    def suggest_label(self, part_svg: str, part_id: str) -> AiDraft:
        """부품 SVG에 대한 라벨 초안 생성 (캐시 우선)."""
        cached = svg_library_service.load_ai_draft(part_id)
        if cached is not None:
            return cached

        if not self.api_key:
            draft = _empty_draft("GEMINI_API_KEY 없음")
            svg_library_service.save_ai_draft(part_id, draft)
            return draft

        png_b64, note = _try_render_png(part_svg)
        try:
            response_text = self._call_gemini(part_svg=part_svg, png_b64=png_b64)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Gemini 호출 실패 ({part_id}): {e}")
            draft = _empty_draft(f"Gemini 실패: {e}")
            svg_library_service.save_ai_draft(part_id, draft)
            return draft

        draft = _parse_gemini_text_to_draft(response_text)
        if note != "ok":
            # PNG 변환 실패 사실을 raw에 남겨 디버그
            draft.gemini_raw = f"[note] {note}\n{draft.gemini_raw}"
        svg_library_service.save_ai_draft(part_id, draft)
        return draft

    # ---- 내부 호출 ---------------------------------------------------------

    def _call_gemini(self, part_svg: str, png_b64: str | None) -> str:
        """Gemini REST 호출. SVG 본문(텍스트) + (있으면) PNG 이미지 동시 전달."""
        parts: list[dict] = [{"text": self._system_prompt}]

        if png_b64:
            parts.append(
                {"inline_data": {"mime_type": "image/png", "data": png_b64}}
            )

        # SVG 원본 텍스트도 함께 — 작은 부품은 텍스트만으로도 충분히 단서가 된다
        svg_snippet = part_svg
        if len(svg_snippet) > 12000:
            svg_snippet = svg_snippet[:12000] + "\n<!-- ...(생략) -->"
        parts.append(
            {
                "text": (
                    "다음은 카탈로그 등록 대상 부품 SVG 본문이다. "
                    "위 시스템 지시에 따라 JSON 한 덩어리로만 응답하라.\n\n"
                    "```svg\n" + svg_snippet + "\n```"
                )
            }
        )

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            },
        }

        url = f"{BASE_URL}/{self.model}:generateContent?key={self.api_key}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            err_body = e.read().decode(errors="replace")[:500]
            raise RuntimeError(
                f"Gemini HTTP {e.code}: {err_body}"
            ) from e

        candidates = body.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini 응답에 candidates 없음: {body}")
        gen_parts = candidates[0].get("content", {}).get("parts", [])
        texts = [p.get("text", "") for p in gen_parts if "text" in p]
        return "\n".join(texts).strip()


__all__ = ["EunwooService"]
