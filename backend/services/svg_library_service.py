"""SVG 라이브러리 카탈로그 서비스.

Task #5 — 카탈로그/진행상태 CRUD + 부품 SVG 조회.

파일 기반 영속화:
    - backend/data/svg_library/catalog.json   : 부품 메타데이터 (Catalog)
    - backend/data/svg_library/progress.json  : 라벨링 진행상태 (Progress)
    - backend/data/svg_library/parts/         : 분할된 부품 SVG
    - backend/data/svg_library/parts/parts_meta.json : 분할 결과 메타

원자적 쓰기(atomic write):
    - 임시 파일 → os.replace 로 원자적 교체. 동시성 안전.

호출부:
    - backend/api/svg_library.py 의 7개 엔드포인트.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any

from models.svg_part import (
    AiDraft,
    Bbox,
    Catalog,
    ParamDef,
    Progress,
    SvgPart,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 경로 상수
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).resolve().parent.parent
LIBRARY_DIR = _BACKEND_DIR / "data" / "svg_library"
PARTS_DIR = LIBRARY_DIR / "parts"
CATALOG_PATH = LIBRARY_DIR / "catalog.json"
PROGRESS_PATH = LIBRARY_DIR / "progress.json"
AI_DRAFTS_DIR = LIBRARY_DIR / "ai_drafts"
PARTS_META_PATH = PARTS_DIR / "parts_meta.json"

# 동시 쓰기 보호용 락 (단일 프로세스 한정 — 멀티 프로세스 환경은 file lock 필요)
_lock = RLock()


# ---------------------------------------------------------------------------
# 원자적 IO 헬퍼
# ---------------------------------------------------------------------------


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """JSON을 원자적으로 기록.

    같은 디렉토리에 임시 파일을 만들고 ``os.replace`` 로 교체한다.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp_name, str(path))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"JSON 읽기 실패 {path}: {e} — 기본값 반환")
        return default


# ---------------------------------------------------------------------------
# 카탈로그 / 진행상태
# ---------------------------------------------------------------------------


def load_catalog() -> Catalog:
    raw = _read_json(CATALOG_PATH, {"version": "1.0", "total_count": 0, "parts": []})
    try:
        return Catalog.model_validate(raw)
    except Exception as e:  # noqa: BLE001
        logger.error(f"catalog.json 검증 실패: {e} — 빈 카탈로그 반환")
        return Catalog()


def save_catalog(catalog: Catalog) -> None:
    catalog.total_count = len(catalog.parts)
    payload = catalog.model_dump(mode="json")
    _atomic_write_json(CATALOG_PATH, payload)


def load_progress() -> Progress:
    raw = _read_json(PROGRESS_PATH, {
        "scope": "trial",
        "total": 0,
        "labeled": 0,
        "skipped": 0,
        "in_progress_id": None,
    })
    try:
        return Progress.model_validate(raw)
    except Exception as e:  # noqa: BLE001
        logger.error(f"progress.json 검증 실패: {e} — 기본값 반환")
        return Progress()


def save_progress(progress: Progress) -> None:
    payload = progress.model_dump(mode="json")
    _atomic_write_json(PROGRESS_PATH, payload)


# ---------------------------------------------------------------------------
# 부품 ID/경로 헬퍼
# ---------------------------------------------------------------------------

_FILENAME_ID_RE = re.compile(r"^#?(\d+)_(\d+)\.svg$")


def _filename_to_part_id(filename: str) -> str:
    """``#4_001.svg`` → ``4-001`` 형식 ID."""
    m = _FILENAME_ID_RE.match(filename)
    if not m:
        # fallback — 확장자 빼고 그대로 사용
        return Path(filename).stem.lstrip("#").replace("_", "-")
    return f"{m.group(1)}-{m.group(2)}"


def _resolve_part_path(part: SvgPart) -> Path:
    """SvgPart.filename 을 절대 경로로 변환.

    filename은 카탈로그 루트(``LIBRARY_DIR``) 기준 상대경로 (``parts/...``).
    """
    rel = part.filename.replace("\\", "/")
    candidate = LIBRARY_DIR / rel
    if candidate.exists():
        return candidate
    # filename이 'parts/' 접두사 없이 들어온 경우 보정
    return PARTS_DIR / Path(rel).name


def find_part(catalog: Catalog, part_id: str) -> SvgPart | None:
    for p in catalog.parts:
        if p.id == part_id:
            return p
    return None


def part_to_svg_text(part: SvgPart) -> str:
    """부품 ID → SVG 본문 문자열."""
    p = _resolve_part_path(part)
    if not p.exists():
        raise FileNotFoundError(f"부품 SVG 없음: {p}")
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


def ingest_from_meta(force: bool = False) -> dict[str, Any]:
    """``parts/parts_meta.json`` 을 카탈로그로 흡수.

    ``svg_splitter.split_svg`` 가 이미 부품 SVG를 만들어 놨다는 전제.
    카탈로그에 없는 신규 부품만 추가하고 progress.total을 갱신한다.

    Returns:
        ingest 결과 요약 dict
    """
    with _lock:
        if not PARTS_META_PATH.exists():
            return {
                "added": 0,
                "skipped": 0,
                "total": 0,
                "warning": "parts_meta.json 없음 — svg_splitter 먼저 실행 필요",
            }

        meta = _read_json(PARTS_META_PATH, {})
        meta_parts: list[dict[str, Any]] = meta.get("parts", []) or []

        catalog = load_catalog()
        existing_ids = {p.id for p in catalog.parts}

        added = 0
        skipped_existing = 0
        for entry in meta_parts:
            filename = entry.get("filename", "")
            if not filename:
                continue
            pid = _filename_to_part_id(filename)
            if pid in existing_ids and not force:
                skipped_existing += 1
                continue
            bbox_list = entry.get("bbox") or [0, 0, 0, 0]
            try:
                bx, by, bx2, by2 = (float(v) for v in bbox_list[:4])
                bbox = Bbox(
                    x=bx,
                    y=by,
                    width=max(0.0, bx2 - bx),
                    height=max(0.0, by2 - by),
                )
            except Exception:  # noqa: BLE001
                bbox = Bbox(x=0, y=0, width=0, height=0)

            new_part = SvgPart(
                id=pid,
                filename=f"parts/{filename}",
                bbox=bbox,
                path_count=int(entry.get("path_count", 0) or 0),
            )
            if pid in existing_ids and force:
                # 기존 항목 업데이트 — 이름/태그는 보존
                for i, p in enumerate(catalog.parts):
                    if p.id == pid:
                        new_part.name = p.name
                        new_part.category = p.category
                        new_part.subcategory = p.subcategory
                        new_part.tags = p.tags
                        new_part.variable_params = p.variable_params
                        new_part.ai_draft = p.ai_draft
                        new_part.verified_by_teacher = p.verified_by_teacher
                        catalog.parts[i] = new_part
                        break
            else:
                catalog.parts.append(new_part)
                existing_ids.add(pid)
                added += 1

        save_catalog(catalog)

        # progress.total 갱신 (전체 부품 수 기준)
        progress = load_progress()
        progress.total = len(catalog.parts)
        # labeled / skipped는 보존
        save_progress(progress)

        return {
            "added": added,
            "skipped_existing": skipped_existing,
            "total": len(catalog.parts),
            "source": meta.get("source", ""),
        }


def ingest_from_path(svg_path: str, force: bool = False) -> dict[str, Any]:
    """원본 SVG 경로를 받아 svg_splitter 실행 후 카탈로그 흡수.

    분할 결과가 이미 존재하면 idempotent하게 흡수만 수행.
    """
    from services.svg_splitter import split_svg  # 지연 import (의존 격리)

    src = Path(svg_path)
    if not src.is_absolute():
        # MathSolution 루트 기준 상대 경로 허용
        src = (_BACKEND_DIR.parent / svg_path).resolve()

    result: dict[str, Any] = {
        "split": None,
        "ingest": None,
    }

    if not src.exists():
        # 분할 없이 기존 parts_meta만 흡수 시도 (idempotent fallback)
        result["warning"] = f"원본 SVG 없음: {src} — 기존 parts_meta로 흡수만 수행"
        result["ingest"] = ingest_from_meta(force=force)
        return result

    try:
        split_result = split_svg(src, PARTS_DIR)
        result["split"] = {
            "total_parts": split_result.total_parts,
            "skipped": split_result.skipped,
            "warnings": split_result.warnings,
        }
    except Exception as e:  # noqa: BLE001
        logger.error(f"svg_splitter 실패: {e}")
        result["split_error"] = str(e)

    result["ingest"] = ingest_from_meta(force=force)
    return result


# ---------------------------------------------------------------------------
# Next / Label / Skip
# ---------------------------------------------------------------------------


def get_next_unlabeled(catalog: Catalog | None = None) -> SvgPart | None:
    """검증되지 않은 다음 부품 반환 (없으면 None)."""
    cat = catalog or load_catalog()
    for p in cat.parts:
        if not p.verified_by_teacher:
            return p
    return None


def label_part(part_id: str, draft: dict[str, Any]) -> SvgPart:
    """교사 확정 라벨 저장.

    Args:
        part_id: SvgPart.id (예 '4-001')
        draft: {name, category, subcategory, tags, variable_params}
    """
    with _lock:
        catalog = load_catalog()
        part = find_part(catalog, part_id)
        if not part:
            raise KeyError(f"부품 없음: {part_id}")

        part.name = str(draft.get("name", part.name))
        part.category = str(draft.get("category", part.category))
        part.subcategory = str(draft.get("subcategory", part.subcategory))
        tags = draft.get("tags")
        if isinstance(tags, list):
            part.tags = [str(t) for t in tags]
        params = draft.get("variable_params")
        if isinstance(params, list):
            try:
                part.variable_params = [
                    ParamDef.model_validate(pd) for pd in params
                ]
            except Exception as e:  # noqa: BLE001
                logger.warning(f"variable_params 검증 실패: {e} — 기존 값 유지")
        part.verified_by_teacher = True
        from models.svg_part import _utcnow  # type: ignore[attr-defined]
        part.updated_at = _utcnow()

        save_catalog(catalog)

        progress = load_progress()
        progress.labeled = sum(1 for p in catalog.parts if p.verified_by_teacher)
        progress.in_progress_id = None
        save_progress(progress)
        return part


def skip_part(part_id: str) -> Progress:
    """부품 스킵 (라벨링 건너뜀, verified_by_teacher 유지)."""
    with _lock:
        progress = load_progress()
        progress.skipped += 1
        if progress.in_progress_id == part_id:
            progress.in_progress_id = None
        save_progress(progress)
        return progress


def set_in_progress(part_id: str) -> None:
    with _lock:
        progress = load_progress()
        progress.in_progress_id = part_id
        save_progress(progress)


# ---------------------------------------------------------------------------
# AI 초안 캐시
# ---------------------------------------------------------------------------


def load_ai_draft(part_id: str) -> AiDraft | None:
    p = AI_DRAFTS_DIR / f"{part_id}.json"
    if not p.exists():
        return None
    raw = _read_json(p, {})
    if not raw:
        return None
    try:
        return AiDraft.model_validate(raw)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"AiDraft 검증 실패 {part_id}: {e}")
        return None


def save_ai_draft(part_id: str, draft: AiDraft) -> None:
    AI_DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(AI_DRAFTS_DIR / f"{part_id}.json", draft.model_dump(mode="json"))


__all__ = [
    "LIBRARY_DIR",
    "PARTS_DIR",
    "CATALOG_PATH",
    "PROGRESS_PATH",
    "AI_DRAFTS_DIR",
    "PARTS_META_PATH",
    "load_catalog",
    "save_catalog",
    "load_progress",
    "save_progress",
    "ingest_from_path",
    "ingest_from_meta",
    "get_next_unlabeled",
    "label_part",
    "skip_part",
    "set_in_progress",
    "find_part",
    "part_to_svg_text",
    "load_ai_draft",
    "save_ai_draft",
]
