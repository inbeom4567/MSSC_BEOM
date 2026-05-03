"""SVG → PNG 변환 서비스.

Task #4.5 — 갈량 피드백 상1 반영 (2026-04-25, 차은우)

도구 결정: **resvg-py** 채택.

근거(2026-04-25 벤치마크, 부품 `#4_031.svg` viewBox 139x83 / 텍스트 20개 / HyhwpEQ
폰트 사용 / 800x600 캔버스 / 5회 평균):
    resvg-py    → 변환 평균 64ms, PNG 50KB, 콜드 스타트 없음, pip 1줄(983KB whl).
    Playwright  → 변환 평균 60ms(스크린샷 단계만), PNG 25KB, Chromium 기동 1~2초
                  + 약 200MB 다운로드, OS별 별도 바이너리 필요.
양쪽 모두 한글/수식(HyhwpEQ) 폰트를 정확히 렌더링하여 시각 품질은 동등하다. 그러나
(1) 의존성 면에서 resvg-py가 압도적으로 가볍고 Docker linux 빌드 비용도 거의 없으며,
(2) 변환 함수 호출 한 번이면 PNG 바이트가 즉시 반환되어 동시성 풀 관리가 불필요하고,
(3) 폰트 임베딩이 `font_files=[...]` 경로 리스트만으로 끝난다(Playwright는 매번 HTML
래퍼에 base64 데이터 URL을 끼워야 함). 따라서 469개 부품 일괄 변환과 `/preview.png`
엔드포인트 양쪽에 resvg-py가 우월하다고 판단하여 채택했다.

CLI 예: ``python -m backend.services.svg_to_png <input.svg> <output.png> [width] [height]``
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# 동일 패키지의 폰트 폴더 (font_service.py와 동일한 위치)
FONTS_DIR = Path(__file__).resolve().parent.parent / "data" / "fonts"

# resvg-py가 신뢰할 폰트 파일 확장자
_FONT_EXTS = {".ttf", ".otf"}

# 한 번만 디스크 스캔하기 위한 캐시
_cached_font_files: Optional[List[str]] = None


def _collect_font_files() -> List[str]:
    """``backend/data/fonts/``의 TTF/OTF 파일 절대경로 리스트를 반환.

    HyhwpEQ·HancomEQN 등 수식체가 누락되지 않도록 모든 .ttf/.otf 파일을
    그대로 resvg에 주입한다. 결과는 프로세스 수명 동안 캐시한다.
    """
    global _cached_font_files
    if _cached_font_files is not None:
        return _cached_font_files

    if not FONTS_DIR.exists():
        logger.warning(f"폰트 디렉터리가 없습니다: {FONTS_DIR}")
        _cached_font_files = []
        return _cached_font_files

    files = sorted(
        str(p) for p in FONTS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in _FONT_EXTS
    )
    logger.info(f"resvg 폰트 주입 대상: {len(files)}개 ({FONTS_DIR})")
    _cached_font_files = files
    return files


def svg_to_png(
    svg_text: str,
    width: int = 800,
    height: int = 600,
    *,
    background: Optional[str] = None,
) -> bytes:
    """SVG 문자열을 PNG 바이트로 변환.

    **비율 보존 정책**: resvg는 SVG의 ``viewBox`` 비율을 유지한다. ``width``와
    ``height``를 모두 지정하면 둘 중 더 작은 박스에 맞춰 축소되며 결과 PNG의
    실제 픽셀 크기는 SVG 비율 그대로다(예: viewBox 가로:세로=10:6 + 인자
    640x480 → 출력 640x384). 정확한 픽셀 일치가 필요하면 호출 후 PIL 등으로
    여백을 패딩하거나 SVG에 ``<rect>`` 배경을 추가하라.

    Args:
        svg_text: SVG XML 문자열 (`<svg ...>...</svg>`)
        width: 출력 PNG의 최대 너비(px). 기본 800.
        height: 출력 PNG의 최대 높이(px). 기본 600.
        background: 배경색(예: `"#ffffff"`). None이면 투명.

    Returns:
        PNG 바이너리(bytes).

    Raises:
        ImportError: resvg_py 미설치
        ValueError: svg_text가 비었거나 변환 실패
    """
    if not svg_text or not svg_text.strip():
        raise ValueError("svg_text가 비어 있습니다")
    if width <= 0 or height <= 0:
        raise ValueError(f"width/height는 양수여야 합니다 (got {width}x{height})")

    try:
        import resvg_py  # type: ignore
    except ImportError as e:
        raise ImportError(
            "resvg-py가 설치되어 있지 않습니다. "
            "`pip install resvg-py>=0.3.1`을 실행하십시오."
        ) from e

    fonts = _collect_font_files()

    try:
        result = resvg_py.svg_to_bytes(
            svg_string=svg_text,
            width=width,
            height=height,
            font_files=fonts,
            background=background,
            # 시스템 폰트 스캔은 비활성화 — Docker linux 환경 일관성 확보
            skip_system_fonts=True,
            # 텍스트 렌더링 품질 우선 (기본은 ‘optimizeLegibility’)
        )
    except Exception as e:
        raise ValueError(f"SVG 변환 실패: {e}") from e

    # resvg-py 0.3.x는 list[int]를 반환 → bytes로 정규화
    if isinstance(result, list):
        result = bytes(result)
    if not isinstance(result, (bytes, bytearray)):
        raise ValueError(f"resvg가 예상치 못한 타입을 반환: {type(result).__name__}")

    return bytes(result)


def svg_file_to_png(
    input_path: str | Path,
    output_path: str | Path,
    width: int = 800,
    height: int = 600,
    *,
    background: Optional[str] = None,
) -> Path:
    """파일 경로 기반의 편의 래퍼.

    Returns:
        실제로 쓰여진 PNG 파일 경로.
    """
    in_p = Path(input_path)
    out_p = Path(output_path)

    if not in_p.is_file():
        raise FileNotFoundError(f"입력 SVG가 없습니다: {in_p}")

    svg_text = in_p.read_text(encoding="utf-8")
    png = svg_to_png(svg_text, width=width, height=height, background=background)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_bytes(png)
    return out_p


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main(argv: List[str]) -> int:
    if len(argv) < 2 or len(argv) > 4:
        print(
            "Usage: python -m backend.services.svg_to_png "
            "<input.svg> <output.png> [width=800] [height=600]",
            file=sys.stderr,
        )
        return 2

    in_path = argv[0]
    out_path = argv[1]
    width = int(argv[2]) if len(argv) >= 3 else 800
    height = int(argv[3]) if len(argv) >= 4 else 600

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    written = svg_file_to_png(in_path, out_path, width=width, height=height)
    size = written.stat().st_size
    print(f"OK  {written}  ({size:,} bytes, {width}x{height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
