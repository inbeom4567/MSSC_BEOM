"""SVG 자동 분할기.

Illustrator에서 내보낸 평면 SVG(<g>/<symbol> 없이 <path>가 쭉 나열된 구조)를
좌표 클러스터링으로 개별 부품 SVG로 분리한다.

사용법::

    python -m backend.services.svg_splitter <input.svg> <output_dir>

주요 파이프라인은 ``split_svg`` 함수 한 방에 담겨 있다. 내부 단계는 다음과 같다.

1. ``parse_svg``        — lxml 로 SVG 파싱, ``<defs>`` 추출, 그리기 요소 수집
2. ``compute_bboxes``   — 각 요소의 bbox (minx, miny, maxx, maxy) 계산
3. ``cluster_paths``    — DBSCAN(eps = viewBox 대각선의 5%, min_samples=1)
4. ``write_part_svg``   — 클러스터별 SVG 문서 쓰기 (viewBox 재계산)
5. ``parts_meta.json``  — 부품 메타데이터 저장

주의:
- 원본 ``<defs>`` 블록(``.st0 { fill:none; ... }`` 스타일)은 그대로 복사한다.
- 잘못된 path ``d`` 속성이 있으면 해당 요소는 스킵하고 경고를 출력한다.
- Python 3.14, Windows 환경, UTF-8 경로(한글·공백·``#`` 포함) 전제.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
from lxml import etree
from sklearn.cluster import DBSCAN
from svgpathtools import parse_path

# ---------------------------------------------------------------------------
# 데이터 클래스
# ---------------------------------------------------------------------------


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
NS = {"svg": SVG_NS, "xlink": XLINK_NS}

# 클러스터링 대상 그리기 요소 태그 (로컬 태그명 기준)
DRAWABLE_TAGS = {
    "path",
    "polygon",
    "polyline",
    "circle",
    "rect",
    "line",
    "ellipse",
    "text",
}


@dataclass
class Bbox:
    """축 정렬 경계 상자."""

    minx: float
    miny: float
    maxx: float
    maxy: float

    @property
    def width(self) -> float:
        return max(0.0, self.maxx - self.minx)

    @property
    def height(self) -> float:
        return max(0.0, self.maxy - self.miny)

    @property
    def cx(self) -> float:
        return (self.minx + self.maxx) / 2.0

    @property
    def cy(self) -> float:
        return (self.miny + self.maxy) / 2.0

    def as_list(self) -> list[float]:
        return [self.minx, self.miny, self.maxx, self.maxy]

    @classmethod
    def union(cls, boxes: Iterable["Bbox"]) -> "Bbox":
        boxes = list(boxes)
        if not boxes:
            raise ValueError("bbox union 대상이 비어있다")
        return cls(
            minx=min(b.minx for b in boxes),
            miny=min(b.miny for b in boxes),
            maxx=max(b.maxx for b in boxes),
            maxy=max(b.maxy for b in boxes),
        )


@dataclass
class SvgData:
    """파싱 결과 컨테이너."""

    tree: etree._ElementTree
    root: etree._Element
    view_box: Bbox
    defs_element: etree._Element | None
    elements: list[etree._Element]  # 그리기 요소(path 등)만


@dataclass
class PartInfo:
    id: int
    filename: str
    bbox: list[float]
    path_count: int


@dataclass
class SplitResult:
    source: str
    parts: list[PartInfo] = field(default_factory=list)
    total_parts: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 1. 파싱
# ---------------------------------------------------------------------------


def parse_svg(path: Path) -> SvgData:
    """SVG 파일을 파싱해 defs 와 그리기 요소 목록을 반환한다."""
    if not path.exists():
        raise FileNotFoundError(f"입력 SVG 없음: {path}")

    # huge_tree=True — Illustrator 출력이 꽤 크다
    parser = etree.XMLParser(remove_blank_text=False, huge_tree=True)
    tree = etree.parse(str(path), parser)
    root = tree.getroot()

    vb_attr = root.get("viewBox")
    if not vb_attr:
        # fallback: width/height
        width = float(root.get("width", "1") or 1)
        height = float(root.get("height", "1") or 1)
        view_box = Bbox(0.0, 0.0, width, height)
    else:
        parts = [float(x) for x in re.split(r"[\s,]+", vb_attr.strip()) if x]
        if len(parts) != 4:
            raise ValueError(f"viewBox 파싱 실패: {vb_attr!r}")
        x, y, w, h = parts
        view_box = Bbox(x, y, x + w, y + h)

    defs_element = root.find(f"{{{SVG_NS}}}defs")

    # 그리기 요소: defs 안의 것은 제외 (재사용 정의)
    elements: list[etree._Element] = []
    for elem in root.iter():
        # 주석·처리명령 등 비-Element 노드 스킵 (lxml 6+ 에서 QName 에 넘기면 에러)
        if not isinstance(elem.tag, str):
            continue
        tag = etree.QName(elem).localname
        if tag not in DRAWABLE_TAGS:
            continue
        # defs 하위면 제외
        ancestor = elem.getparent()
        in_defs = False
        while ancestor is not None and ancestor is not root:
            if etree.QName(ancestor).localname == "defs":
                in_defs = True
                break
            ancestor = ancestor.getparent()
        if in_defs:
            continue
        elements.append(elem)

    return SvgData(
        tree=tree,
        root=root,
        view_box=view_box,
        defs_element=defs_element,
        elements=elements,
    )


# ---------------------------------------------------------------------------
# 2. bbox 계산
# ---------------------------------------------------------------------------


def _safe_float(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _parse_points(points_str: str) -> list[tuple[float, float]]:
    """polygon/polyline의 points 속성 파싱."""
    nums = [float(n) for n in re.split(r"[\s,]+", points_str.strip()) if n]
    pairs: list[tuple[float, float]] = []
    for i in range(0, len(nums) - 1, 2):
        pairs.append((nums[i], nums[i + 1]))
    return pairs


_TRANSLATE_RE = re.compile(
    r"translate\(\s*(-?\d+(?:\.\d+)?)\s*[,\s]\s*(-?\d+(?:\.\d+)?)\s*\)"
)
_TRANSLATE_SINGLE_RE = re.compile(r"translate\(\s*(-?\d+(?:\.\d+)?)\s*\)")
_MATRIX_RE = re.compile(
    r"matrix\("
    r"\s*(-?\d+(?:\.\d+)?)[\s,]+(-?\d+(?:\.\d+)?)[\s,]+"
    r"(-?\d+(?:\.\d+)?)[\s,]+(-?\d+(?:\.\d+)?)[\s,]+"
    r"(-?\d+(?:\.\d+)?)[\s,]+(-?\d+(?:\.\d+)?)\s*\)"
)


def _accumulate_translation(elem: etree._Element) -> tuple[float, float]:
    """요소부터 루트까지 조상 체인의 transform 중 평행이동 성분을 누적.

    Illustrator 평면 SVG 는 대부분 ``translate(tx ty)`` 혹은
    ``matrix(1 0 0 1 e f)`` 형태의 평행이동만 사용한다. 회전·스케일이 있으면
    정확한 bbox 를 위해서는 svgpathtools 의 ``transformed`` 를 써야 하지만
    현재 대상 SVG 에는 등장하지 않으므로 평행이동만 보정한다.
    """
    tx_total = 0.0
    ty_total = 0.0
    cur: etree._Element | None = elem
    while cur is not None:
        t = cur.get("transform")
        if t:
            # 여러 transform 함수가 공백으로 나열 — 각각 평행이동 성분만 더함
            for m in _TRANSLATE_RE.finditer(t):
                tx_total += float(m.group(1))
                ty_total += float(m.group(2))
            # translate(x) 단일 인자는 ty=0
            for m in _TRANSLATE_SINGLE_RE.finditer(t):
                # 위 2인자 정규식과 겹치지 않도록 substring 확인
                span = m.group(0)
                if "," not in span and len(span.split()) <= 1:
                    # 2인자 정규식이 매치 안 된 경우에만 사용
                    if not _TRANSLATE_RE.search(span):
                        tx_total += float(m.group(1))
            for m in _MATRIX_RE.finditer(t):
                # matrix(a b c d e f) — 평행이동은 (e, f)
                tx_total += float(m.group(5))
                ty_total += float(m.group(6))
        cur = cur.getparent()
    return tx_total, ty_total


def _bbox_for_element(elem: etree._Element) -> Bbox | None:
    """단일 요소의 bbox를 계산한다. 실패 시 None.

    조상 체인의 ``translate(...)`` / ``matrix(... e f)`` 평행이동을 누적해 최종
    bbox 에 더한다. Illustrator 가 ``<text transform="translate(a b)">`` 형태로
    좌표를 숨기는 케이스를 올바르게 반영하기 위해서다.
    """
    if not isinstance(elem.tag, str):
        return None
    tag = etree.QName(elem).localname

    bb: Bbox | None = None
    try:
        if tag == "path":
            d = elem.get("d")
            if not d:
                return None
            p = parse_path(d)
            if len(p) == 0:
                return None
            xmin, xmax, ymin, ymax = p.bbox()
            bb = Bbox(float(xmin), float(ymin), float(xmax), float(ymax))

        elif tag in ("polygon", "polyline"):
            pts = _parse_points(elem.get("points", ""))
            if not pts:
                return None
            xs = [x for x, _ in pts]
            ys = [y for _, y in pts]
            bb = Bbox(min(xs), min(ys), max(xs), max(ys))

        elif tag == "circle":
            cx = _safe_float(elem.get("cx"))
            cy = _safe_float(elem.get("cy"))
            r = _safe_float(elem.get("r"))
            bb = Bbox(cx - r, cy - r, cx + r, cy + r)

        elif tag == "ellipse":
            cx = _safe_float(elem.get("cx"))
            cy = _safe_float(elem.get("cy"))
            rx = _safe_float(elem.get("rx"))
            ry = _safe_float(elem.get("ry"))
            bb = Bbox(cx - rx, cy - ry, cx + rx, cy + ry)

        elif tag == "rect":
            x = _safe_float(elem.get("x"))
            y = _safe_float(elem.get("y"))
            w = _safe_float(elem.get("width"))
            h = _safe_float(elem.get("height"))
            bb = Bbox(x, y, x + w, y + h)

        elif tag == "line":
            x1 = _safe_float(elem.get("x1"))
            y1 = _safe_float(elem.get("y1"))
            x2 = _safe_float(elem.get("x2"))
            y2 = _safe_float(elem.get("y2"))
            bb = Bbox(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))

        elif tag == "text":
            # 텍스트는 글자 메트릭 없이는 정확한 bbox를 못 구함 → 좌표 기준 근사.
            # Illustrator 는 translate(...) 로 실제 위치를 표현하는 경우가 많으므로
            # 조상 transform 누적과 합쳐져 올바른 클러스터링 좌표가 나온다.
            x = _safe_float(elem.get("x"))
            y = _safe_float(elem.get("y"))
            bb = Bbox(x, y - 1.0, x + 1.0, y)

    except Exception:  # noqa: BLE001 — 잘못된 속성은 무시
        return None

    if bb is None:
        return None

    # 조상 체인 translate/matrix 평행이동 누적 적용
    try:
        tx, ty = _accumulate_translation(elem)
    except Exception:  # noqa: BLE001
        tx, ty = 0.0, 0.0
    if tx or ty:
        bb = Bbox(bb.minx + tx, bb.miny + ty, bb.maxx + tx, bb.maxy + ty)
    return bb


def compute_bboxes(
    elements: list[etree._Element],
) -> tuple[list[Bbox], list[int]]:
    """요소 리스트의 bbox를 계산한다.

    Returns:
        (bboxes, valid_indices) — valid_indices 는 bbox 계산에 성공한
        원본 리스트 인덱스. 실패한 요소는 제외된다.
    """
    bboxes: list[Bbox] = []
    valid_indices: list[int] = []
    for idx, elem in enumerate(elements):
        bb = _bbox_for_element(elem)
        if bb is None:
            continue
        # 유효성: NaN / inf / 빈 상자 제거
        if not all(np.isfinite(v) for v in bb.as_list()):
            continue
        bboxes.append(bb)
        valid_indices.append(idx)
    return bboxes, valid_indices


# ---------------------------------------------------------------------------
# 3. 클러스터링
# ---------------------------------------------------------------------------


def cluster_paths(bboxes: list[Bbox], view_box: Bbox) -> list[int]:
    """DBSCAN 으로 클러스터 라벨 리스트를 반환한다.

    파라미터:
        eps = viewBox 대각선 길이의 5%
        min_samples = 1  (단일 요소도 독립 클러스터로 인정)

    각 요소를 bbox 중심점 (cx, cy) 로 표현해 유클리드 거리로 클러스터링한다.
    min_samples=1 이므로 노이즈(-1)는 발생하지 않는다.
    """
    if not bboxes:
        return []

    diag = float(np.hypot(view_box.width, view_box.height))
    eps = diag * 0.05
    if eps <= 0:
        eps = 1.0

    coords = np.array([[b.cx, b.cy] for b in bboxes], dtype=float)
    labels = DBSCAN(eps=eps, min_samples=1).fit_predict(coords)
    return labels.tolist()


# ---------------------------------------------------------------------------
# 4. 부품별 SVG 작성
# ---------------------------------------------------------------------------


def _format_float(v: float) -> str:
    # 불필요한 꼬리 0 제거
    s = f"{v:.4f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def write_part_svg(
    cluster_elements: list[etree._Element],
    cluster_bbox: Bbox,
    defs_element: etree._Element | None,
    out_path: Path,
    part_id: int,
) -> PartInfo:
    """클러스터에 속한 요소들로 새 SVG 문서를 생성한다."""
    # 여유 패딩 (대각선의 2%)
    pad = max(0.5, np.hypot(cluster_bbox.width, cluster_bbox.height) * 0.02)
    vb_x = cluster_bbox.minx - pad
    vb_y = cluster_bbox.miny - pad
    vb_w = cluster_bbox.width + pad * 2
    vb_h = cluster_bbox.height + pad * 2

    # 최소 크기 보장 (너무 작으면 렌더 불가)
    vb_w = max(vb_w, 1.0)
    vb_h = max(vb_h, 1.0)

    nsmap = {None: SVG_NS, "xlink": XLINK_NS}
    new_root = etree.Element(f"{{{SVG_NS}}}svg", nsmap=nsmap)
    new_root.set("version", "1.1")
    new_root.set(
        "viewBox",
        f"{_format_float(vb_x)} {_format_float(vb_y)} "
        f"{_format_float(vb_w)} {_format_float(vb_h)}",
    )

    # 원본 defs 그대로 복사 (스타일 보존)
    if defs_element is not None:
        new_defs = etree.fromstring(etree.tostring(defs_element))
        new_root.append(new_defs)

    # 각 요소 복사본 추가 — 부모 체인/변환은 무시 (원본에도 transform 이 없다고 가정)
    # Illustrator 평면 SVG 는 보통 transform 이 없다.
    for elem in cluster_elements:
        new_root.append(etree.fromstring(etree.tostring(elem)))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tree = etree.ElementTree(new_root)
    tree.write(
        str(out_path),
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )

    return PartInfo(
        id=part_id,
        filename=out_path.name,
        bbox=[round(v, 4) for v in cluster_bbox.as_list()],
        path_count=len(cluster_elements),
    )


# ---------------------------------------------------------------------------
# 5. 파이프라인 래퍼
# ---------------------------------------------------------------------------


def _derive_file_prefix(input_path: Path) -> str:
    """파일명에서 ``#N`` 토큰을 추출해 prefix로 쓴다.

    예) ``#4_미적분2 그림.svg`` → ``#4``. 없으면 stem 사용.
    """
    stem = input_path.stem
    m = re.match(r"(#\d+)", stem)
    if m:
        return m.group(1)
    # 숫자 prefix 없으면 stem 첫 토큰
    return re.split(r"[_\s]", stem, maxsplit=1)[0] or "part"


def split_svg(input_path: Path, output_dir: Path) -> SplitResult:
    """전체 분할 파이프라인.

    Args:
        input_path: 입력 SVG 경로
        output_dir: 부품 SVG 를 저장할 디렉토리

    Returns:
        SplitResult (source / parts / total_parts / skipped / warnings)
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = SplitResult(source=str(input_path))

    svg_data = parse_svg(input_path)
    total_elements = len(svg_data.elements)
    if total_elements == 0:
        result.warnings.append("그리기 요소가 없다")
        _write_meta(output_dir, input_path, result)
        return result

    bboxes, valid_indices = compute_bboxes(svg_data.elements)
    skipped = total_elements - len(valid_indices)
    result.skipped = skipped
    if skipped > 0:
        result.warnings.append(
            f"{skipped}개 요소의 bbox 계산 실패 — 스킵"
        )

    if not bboxes:
        result.warnings.append("유효한 bbox 가 없다 — 분할 중단")
        _write_meta(output_dir, input_path, result)
        return result

    labels = cluster_paths(bboxes, svg_data.view_box)

    # 라벨별 요소 묶기 (라벨은 -1 없음, min_samples=1 이므로)
    groups: dict[int, list[int]] = {}
    for local_idx, lbl in enumerate(labels):
        groups.setdefault(lbl, []).append(local_idx)

    # 라벨을 좌→우, 위→아래 순으로 정렬(사람이 보기 편하게)
    def _sort_key(item: tuple[int, list[int]]) -> tuple[float, float]:
        _, indices = item
        sub = [bboxes[i] for i in indices]
        union = Bbox.union(sub)
        return (union.miny, union.minx)

    sorted_groups = sorted(groups.items(), key=_sort_key)

    prefix = _derive_file_prefix(input_path)

    # 기존 부품 파일 정리 (같은 prefix만)
    for old in output_dir.glob(f"{prefix}_*.svg"):
        try:
            old.unlink()
        except OSError:
            pass

    parts: list[PartInfo] = []
    for new_id, (_lbl, local_indices) in enumerate(sorted_groups, start=1):
        cluster_elements = [
            svg_data.elements[valid_indices[li]] for li in local_indices
        ]
        cluster_bboxes = [bboxes[li] for li in local_indices]
        cluster_bbox = Bbox.union(cluster_bboxes)

        filename = f"{prefix}_{new_id:03d}.svg"
        out_path = output_dir / filename
        info = write_part_svg(
            cluster_elements=cluster_elements,
            cluster_bbox=cluster_bbox,
            defs_element=svg_data.defs_element,
            out_path=out_path,
            part_id=new_id,
        )
        parts.append(info)

    result.parts = parts
    result.total_parts = len(parts)

    _write_meta(output_dir, input_path, result)
    return result


def _write_meta(output_dir: Path, input_path: Path, result: SplitResult) -> None:
    meta = {
        "source": str(input_path).replace("\\", "/"),
        "total_parts": result.total_parts,
        "skipped": result.skipped,
        "warnings": result.warnings,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parts": [asdict(p) for p in result.parts],
    }
    meta_path = output_dir / "parts_meta.json"
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(
            "사용법: python -m backend.services.svg_splitter "
            "<input.svg> <output_dir>",
            file=sys.stderr,
        )
        return 2
    input_path = Path(argv[1])
    output_dir = Path(argv[2])
    result = split_svg(input_path, output_dir)
    # Windows 콘솔(cp949) 호환을 위해 stdout 재설정 시도
    try:  # pragma: no cover — 환경 의존
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    print(
        f"완료 - 부품 {result.total_parts}개, 스킵 {result.skipped}개, "
        f"출력 {output_dir}"
    )
    for w in result.warnings:
        print(f"  경고: {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
