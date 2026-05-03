"""SVG 라이브러리 라벨링 API.

Task #5 — 7개 엔드포인트:

    POST /api/svg-library/ingest             분할/카탈로그 흡수
    GET  /api/svg-library/next                다음 라벨링 대상 + ai_draft
    POST /api/svg-library/label               최종 라벨 저장
    POST /api/svg-library/skip                스킵
    GET  /api/svg-library/catalog             카탈로그 전체 조회
    GET  /api/svg-library/progress            진행 상태 조회
    GET  /api/svg-library/part/{id}/preview.png  PNG 미리보기

EunwooService는 ``next`` 시점에 호출되어 AI 초안을 생성하고 캐싱한다.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from services import svg_library_service
from services.eunwoo_service import EunwooService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/svg-library", tags=["svg-library"])

# 단일 인스턴스 — 시스템 프롬프트 캐싱 효과
_eunwoo = EunwooService()


# ---------------------------------------------------------------------------
# 요청 모델
# ---------------------------------------------------------------------------


class IngestRequest(BaseModel):
    path: str = Field(default="", description="원본 SVG 경로 (절대/상대). 비우면 기존 parts_meta로 흡수.")
    force: bool = Field(default=False, description="기존 카탈로그 항목도 메타로 갱신")


class LabelRequest(BaseModel):
    part_id: str
    name: str = ""
    category: str = ""
    subcategory: str = ""
    tags: list[str] = Field(default_factory=list)
    variable_params: list[dict[str, Any]] = Field(default_factory=list)


class SkipRequest(BaseModel):
    part_id: str


# ---------------------------------------------------------------------------
# 미리보기 PNG (svg_to_png 미존재 시 placeholder)
# ---------------------------------------------------------------------------

# TODO(Task #4.5 — 은우 A): 본 모듈은 svg_to_png 가 생기면 자동으로 사용한다.
# 미존재 시 1x1 투명 PNG를 placeholder로 반환한다.

_TRANSPARENT_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _render_part_preview(part_svg: str) -> tuple[bytes, str]:
    """SVG → PNG bytes 시도. 실패 시 placeholder 반환."""
    try:
        from services.svg_to_png import svg_to_png  # type: ignore[import-not-found]
    except Exception:
        return _TRANSPARENT_PNG_1X1, "placeholder"

    try:
        png_bytes = svg_to_png(part_svg)
        return png_bytes, "ok"
    except Exception as e:  # noqa: BLE001
        logger.warning(f"svg_to_png 호출 실패: {e} — placeholder 반환")
        return _TRANSPARENT_PNG_1X1, "error"


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------


@router.post("/ingest")
async def ingest(req: IngestRequest):
    """원본 SVG를 분할하고 카탈로그에 흡수.

    `path`가 비어있으면 기존 ``parts/parts_meta.json`` 만으로 카탈로그를 갱신한다.
    이미 분할된 결과가 있으면 idempotent 하게 동작한다.
    """
    try:
        if req.path:
            result = svg_library_service.ingest_from_path(req.path, force=req.force)
        else:
            result = {"ingest": svg_library_service.ingest_from_meta(force=req.force)}
        progress = svg_library_service.load_progress()
        return {
            "status": "ok",
            "result": result,
            "progress": progress.model_dump(mode="json"),
        }
    except Exception as e:  # noqa: BLE001
        logger.error(f"ingest 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/next")
async def next_part():
    """라벨링 안 된 다음 부품 + AI 초안 반환."""
    try:
        catalog = svg_library_service.load_catalog()
        part = svg_library_service.get_next_unlabeled(catalog)
        if part is None:
            return {"status": "complete", "message": "모든 부품 라벨링 완료"}

        try:
            svg_text = svg_library_service.part_to_svg_text(part)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

        # AI 초안 (캐시 우선)
        ai_draft = _eunwoo.suggest_label(part_svg=svg_text, part_id=part.id)

        # 부품에 ai_draft 부착 후 저장 (UI 재로드시 일관성)
        if part.ai_draft is None or part.ai_draft.gemini_raw != ai_draft.gemini_raw:
            part.ai_draft = ai_draft
            svg_library_service.save_catalog(catalog)

        svg_library_service.set_in_progress(part.id)

        return {
            "status": "ok",
            "id": part.id,
            "filename": part.filename,
            "bbox": part.bbox.model_dump(mode="json"),
            "path_count": part.path_count,
            "svg": svg_text,
            "ai_draft": ai_draft.model_dump(mode="json"),
            "preview_url": f"/api/svg-library/part/{part.id}/preview.png",
        }
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"next 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/label")
async def label(req: LabelRequest):
    """교사 확정 라벨 저장."""
    try:
        part = svg_library_service.label_part(
            part_id=req.part_id,
            draft={
                "name": req.name,
                "category": req.category,
                "subcategory": req.subcategory,
                "tags": req.tags,
                "variable_params": req.variable_params,
            },
        )
        progress = svg_library_service.load_progress()
        return {
            "status": "ok",
            "part": part.model_dump(mode="json"),
            "progress": progress.model_dump(mode="json"),
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.error(f"label 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skip")
async def skip(req: SkipRequest):
    """부품 스킵 (라벨 저장 없이 다음으로)."""
    try:
        progress = svg_library_service.skip_part(req.part_id)
        return {"status": "ok", "progress": progress.model_dump(mode="json")}
    except Exception as e:  # noqa: BLE001
        logger.error(f"skip 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog")
async def catalog():
    """카탈로그 전체."""
    try:
        cat = svg_library_service.load_catalog()
        return cat.model_dump(mode="json")
    except Exception as e:  # noqa: BLE001
        logger.error(f"catalog 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/progress")
async def progress():
    """라벨링 진행 상태."""
    try:
        prog = svg_library_service.load_progress()
        return prog.model_dump(mode="json")
    except Exception as e:  # noqa: BLE001
        logger.error(f"progress 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/part/{part_id}/preview.png")
async def part_preview(part_id: str):
    """부품 SVG → PNG 미리보기.

    svg_to_png 모듈 미존재 시 1x1 placeholder PNG 반환.
    """
    try:
        catalog = svg_library_service.load_catalog()
        part = svg_library_service.find_part(catalog, part_id)
        if not part:
            raise HTTPException(status_code=404, detail=f"부품 없음: {part_id}")
        try:
            svg_text = svg_library_service.part_to_svg_text(part)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

        png_bytes, status = _render_part_preview(svg_text)
        headers = {
            "Cache-Control": "public, max-age=3600",
            "X-Preview-Status": status,
        }
        return Response(content=png_bytes, media_type="image/png", headers=headers)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"preview 실패 {part_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
