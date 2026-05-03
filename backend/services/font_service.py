"""폰트 등록 및 조회 서비스.

backend/data/fonts/ 폴더의 TTF/OTF 파일을 Matplotlib font_manager에 등록하고
메타데이터(family/style/weight/path)를 조회할 수 있는 API를 제공합니다.

Task #1 — Font Registration Pipeline (2026-04-24)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

FONTS_DIR = Path(__file__).resolve().parent.parent / "data" / "fonts"

# 파일명 → 메타데이터 매핑 (family/style/weight 표준화)
# Matplotlib가 추출하는 이름과 별개로 우리가 선언적으로 관리한다.
_FONT_META_MAP: Dict[str, Dict[str, str]] = {
    "HCRBatang.ttf":                     {"family": "HCR Batang",          "style": "normal", "weight": "regular"},
    "HCRBatang-Bold.ttf":                {"family": "HCR Batang",          "style": "normal", "weight": "bold"},
    "HYHWPEQ.TTF":                       {"family": "HY Hwp Equation",     "style": "normal", "weight": "regular"},
    "HancomEQN.ttf":                     {"family": "Hancom EQN",          "style": "normal", "weight": "regular"},
    "KoPubDotumLight.ttf":               {"family": "KoPub Dotum",         "style": "normal", "weight": "light"},
    "KoPubDotumMedium.ttf":              {"family": "KoPub Dotum",         "style": "normal", "weight": "medium"},
    "KoPubDotumBold.ttf":                {"family": "KoPub Dotum",         "style": "normal", "weight": "bold"},
    "KoPubWorld Dotum_Pro Light.otf":    {"family": "KoPubWorld Dotum Pro","style": "normal", "weight": "light"},
    "KoPubWorld Dotum_Pro Medium.otf":   {"family": "KoPubWorld Dotum Pro","style": "normal", "weight": "medium"},
    "KoPubWorld Dotum_Pro Bold.otf":     {"family": "KoPubWorld Dotum Pro","style": "normal", "weight": "bold"},
}


def _iter_font_files() -> List[Path]:
    """FONTS_DIR에서 TTF/OTF 파일을 나열."""
    if not FONTS_DIR.exists():
        return []
    return sorted(
        p for p in FONTS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in (".ttf", ".otf")
    )


def register_fonts() -> List[str]:
    """FONTS_DIR의 모든 TTF/OTF 파일을 Matplotlib font_manager에 등록.

    Returns:
        등록된 family name 리스트 (중복 제거).
    """
    registered: List[str] = []
    seen = set()

    try:
        from matplotlib import font_manager
    except Exception as e:
        logger.warning(f"Matplotlib 로드 실패 — 폰트 등록 건너뜀: {e}")
        return registered

    for font_path in _iter_font_files():
        try:
            font_manager.fontManager.addfont(str(font_path))
            # family 이름 추출: 우선 선언적 매핑, 없으면 matplotlib이 인식한 이름
            meta = _FONT_META_MAP.get(font_path.name)
            if meta:
                family = meta["family"]
            else:
                # fallback: matplotlib에서 직접 조회
                try:
                    from matplotlib.font_manager import FontProperties
                    fp = FontProperties(fname=str(font_path))
                    family = fp.get_name()
                except Exception:
                    family = font_path.stem
            if family not in seen:
                seen.add(family)
                registered.append(family)
            logger.info(f"폰트 등록: {font_path.name} → {family}")
        except Exception as e:
            # 하나 실패해도 나머지는 계속 처리
            logger.warning(f"폰트 등록 실패 ({font_path.name}): {e}")

    logger.info(f"폰트 등록 완료: {len(registered)}개 family, {len(_iter_font_files())}개 파일")
    return registered


def list_fonts() -> List[Dict[str, str]]:
    """사용 가능한 폰트의 메타데이터 리스트를 반환.

    Returns:
        [{filename, family, style, weight, path, size}, ...]
    """
    results: List[Dict[str, str]] = []
    for font_path in _iter_font_files():
        meta = _FONT_META_MAP.get(font_path.name, {})
        family = meta.get("family")
        if not family:
            # 선언되지 않은 폰트는 matplotlib에서 추출 시도
            try:
                from matplotlib.font_manager import FontProperties
                fp = FontProperties(fname=str(font_path))
                family = fp.get_name()
            except Exception:
                family = font_path.stem
        results.append({
            "filename": font_path.name,
            "family": family,
            "style": meta.get("style", "normal"),
            "weight": meta.get("weight", "regular"),
            "path": str(font_path),
            "size": font_path.stat().st_size,
        })
    return results


def get_font_path(name: str) -> Optional[Path]:
    """파일명 또는 family name으로 폰트 파일 경로를 반환.

    Args:
        name: 파일명(예: "HCRBatang.ttf") 또는 family name(예: "HCR Batang")

    Returns:
        Path 또는 None
    """
    if not name:
        return None

    # Path traversal 방지: 경로 구분자 및 상위 이동 차단
    if ".." in name or "/" in name or "\\" in name:
        return None

    # 1. 정확한 파일명 매칭
    candidate = FONTS_DIR / name
    try:
        candidate_resolved = candidate.resolve()
        fonts_dir_resolved = FONTS_DIR.resolve()
        # FONTS_DIR 안에 있는지 확인
        candidate_resolved.relative_to(fonts_dir_resolved)
        if candidate_resolved.is_file():
            return candidate_resolved
    except (ValueError, OSError):
        pass

    # 2. family name 매칭 (첫 번째 매칭 파일 반환)
    for font_path in _iter_font_files():
        meta = _FONT_META_MAP.get(font_path.name, {})
        if meta.get("family", "").lower() == name.lower():
            return font_path

    return None


def is_path_safe(filename: str) -> bool:
    """파일명이 FONTS_DIR 경계를 벗어나지 않는지 확인 (path traversal 방지)."""
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        return False
    try:
        resolved = (FONTS_DIR / filename).resolve()
        resolved.relative_to(FONTS_DIR.resolve())
        return True
    except (ValueError, OSError):
        return False
