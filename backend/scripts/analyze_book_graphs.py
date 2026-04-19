"""book/ 폴더의 HWPX 기출 파일에서 그래프 이미지를 추출하고
Gemini로 수능 SVG 스타일 규칙을 분석하여 graph_style_report.json에 저장."""

import io
import sys
import json
import base64
import zipfile
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.gemini_service import analyze_graph, analyze_graph_style

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

BOOK_DIR = Path(__file__).parent.parent.parent / "book"
OUTPUT_FILE = Path(__file__).parent.parent / "data" / "graph_style_report.json"

# Gemini는 BMP 미지원 → JPEG로 변환. PNG/JPG만 직접 전송.
IMAGE_EXTENSIONS = {".bmp", ".jpg", ".jpeg", ".png"}


def _to_jpeg_base64(data: bytes, ext: str) -> tuple[str, str]:
    """이미지 bytes를 Gemini 호환 JPEG base64로 변환. BMP는 PIL로 변환."""
    if ext in (".jpg", ".jpeg"):
        return base64.b64encode(data).decode(), "image/jpeg"
    if ext == ".png":
        return base64.b64encode(data).decode(), "image/png"
    # BMP → JPEG 변환 (PIL 사용)
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode(), "image/jpeg"
    except Exception:
        # PIL 없으면 원본 그대로 (에러 허용)
        return base64.b64encode(data).decode(), "image/bmp"


def extract_images_from_hwpx(hwpx_path: Path) -> list:
    """HWPX ZIP에서 BinData/ 이미지 파일을 base64로 추출. BMP는 JPEG 변환."""
    images = []
    try:
        with zipfile.ZipFile(hwpx_path) as z:
            for name in z.namelist():
                if not name.startswith("BinData/"):
                    continue
                ext = Path(name).suffix.lower()
                if ext not in IMAGE_EXTENSIONS:
                    continue
                data = z.read(name)
                b64, media_type = _to_jpeg_base64(data, ext)
                images.append({
                    "name": name,
                    "base64": b64,
                    "media_type": media_type,
                })
    except Exception as e:
        logger.warning(f"  [경고] {hwpx_path.name} 열기 실패: {e}")
    return images


def _aggregate_styles(results: list) -> dict:
    """스타일 결과 목록에서 필드별 샘플 집계."""
    fields = [
        "axis_arrow", "tick_marks", "origin_label", "curve_style",
        "asymptote_style", "point_style", "label_placement",
        "shading_style", "overall_size", "svg_notes",
    ]
    aggregated = {}
    for field in fields:
        values = [
            r["style"].get(field, "")
            for r in results
            if r.get("style", {}).get(field)
        ]
        aggregated[field] = values[:8]  # 최대 8개 샘플
    return aggregated


def _load_existing(year_filter: str | None) -> tuple[list, set]:
    """기존 결과 로드. 이미 처리된 파일 경로 집합 반환."""
    if not OUTPUT_FILE.exists():
        return [], set()
    try:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            data = json.load(f)
        existing = data.get("styles", [])
        # year_filter가 다른 경우 해당 연도 결과만 제외하고 유지
        done_files = {r["file"] for r in existing}
        return existing, done_files
    except Exception:
        return [], set()


def _save(results: list, hwpx_files: list, total_images: int,
          graph_images: int, errors: int, year_filter: str | None) -> None:
    aggregated = _aggregate_styles(results)
    report = {
        "analyzed_at": datetime.now().isoformat(),
        "year_filter": year_filter or "전체",
        "total_hwpx_files": len(hwpx_files),
        "total_images": total_images,
        "graph_images": graph_images,
        "errors": errors,
        "styles": results,
        "aggregated": aggregated,
    }
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def main(year_filter: str = None):
    """
    year_filter: "2025년" 처럼 특정 연도만 처리. None이면 전체.
    이미 처리된 파일은 건너뜀 (중단 후 재실행 가능).
    사용법:
      python scripts/analyze_book_graphs.py           # 전체
      python scripts/analyze_book_graphs.py 2025년    # 2025년만
    """
    if year_filter:
        year_path = BOOK_DIR / year_filter
        if not year_path.exists():
            logger.error(f"디렉토리 없음: {year_path}")
            sys.exit(1)
        hwpx_files = sorted(year_path.rglob("*.hwpx"))
    else:
        hwpx_files = sorted(BOOK_DIR.rglob("*.hwpx"))

    logger.info(f"HWPX 파일 {len(hwpx_files)}개 처리 시작")

    existing_results, done_files = _load_existing(year_filter)
    results = list(existing_results)
    total_images = 0
    graph_images = len([r for r in results])
    errors = 0

    skipped = 0
    for hwpx_path in hwpx_files:
        rel = str(hwpx_path.relative_to(BOOK_DIR))
        if rel in done_files:
            skipped += 1
            logger.info(f"\n[건너뜀] {rel}")
            continue

        logger.info(f"\n[{rel}]")
        images = extract_images_from_hwpx(hwpx_path)
        logger.info(f"  이미지 {len(images)}개 추출")
        total_images += len(images)

        for img in images:
            try:
                analysis = analyze_graph(img["base64"], img["media_type"])
                if not analysis.get("has_graph", False):
                    continue
                graph_images += 1
                logger.info(f"  그래프: {img['name']} (타입: {analysis.get('graph_type')})")

                style = analyze_graph_style(img["base64"], img["media_type"])
                results.append({
                    "file": rel,
                    "image": img["name"],
                    "graph_type": analysis.get("graph_type", "unknown"),
                    "description": analysis.get("description", ""),
                    "style": style,
                })
            except Exception as e:
                errors += 1
                logger.warning(f"  [에러] {img['name']}: {e}")

        # 파일 하나 완료될 때마다 저장
        _save(results, hwpx_files, total_images, graph_images, errors, year_filter)
        logger.info(f"  → 저장 완료 ({len(results)}개 그래프 누적)")

    logger.info(f"\n{'='*50}")
    logger.info(f"완료: HWPX {len(hwpx_files)}개 (건너뜀 {skipped}개) / 이미지 {total_images}개 / 그래프 {graph_images}개 / 에러 {errors}개")
    logger.info(f"결과 저장: {OUTPUT_FILE}")


if __name__ == "__main__":
    year_filter = sys.argv[1] if len(sys.argv) > 1 else None
    main(year_filter)
