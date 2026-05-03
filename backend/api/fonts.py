"""폰트 조회·serve API.

Endpoints:
    GET /api/fonts/list       → list_fonts() 결과 JSON
    GET /api/fonts/{filename} → 폰트 바이너리 FileResponse

Task #1 — Font Registration Pipeline (2026-04-24)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from services.font_service import FONTS_DIR, get_font_path, is_path_safe, list_fonts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fonts", tags=["fonts"])

# 확장자별 Content-Type 매핑
_MIME_BY_EXT = {
    ".ttf": "font/ttf",
    ".otf": "font/otf",
}


@router.get("/list")
async def fonts_list():
    """backend/data/fonts/ 내 모든 폰트의 메타데이터 반환."""
    items = list_fonts()
    return {"count": len(items), "fonts": items}


@router.get("/{filename}")
async def fonts_get(filename: str):
    """폰트 파일 바이너리 반환.

    Path traversal 방지: filename에 "..", "/", "\\"가 포함되면 400.
    """
    # 1. 경로 안전성 검증
    if not is_path_safe(filename):
        logger.warning(f"폰트 요청 차단 (unsafe path): {filename!r}")
        raise HTTPException(status_code=400, detail="유효하지 않은 파일명입니다.")

    # 2. 파일 조회 (파일명 또는 family name 모두 허용)
    font_path = get_font_path(filename)
    if not font_path or not font_path.is_file():
        raise HTTPException(status_code=404, detail=f"폰트를 찾을 수 없습니다: {filename}")

    # 3. MIME 타입 결정
    suffix = font_path.suffix.lower()
    media_type = _MIME_BY_EXT.get(suffix, "application/octet-stream")

    # 4. 장기 캐시 + 크로스 오리진 허용 (@font-face용)
    headers = {
        "Cache-Control": "public, max-age=31536000, immutable",
        "Access-Control-Allow-Origin": "*",
    }

    return FileResponse(
        path=str(font_path),
        media_type=media_type,
        filename=font_path.name,
        headers=headers,
    )
