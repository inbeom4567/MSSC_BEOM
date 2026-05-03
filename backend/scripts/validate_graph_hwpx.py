"""hwpx 파일 안에 그래프 이미지가 올바르게 임베딩됐는지 검증.

SOT 문서: docs/그래프_렌더_규칙.md 규칙 9 자동 검증 체크리스트의 실행 가능판.

CLI 사용:
    python backend/scripts/validate_graph_hwpx.py 테스트_그림포함_v5.hwpx
    python backend/scripts/validate_graph_hwpx.py file.hwpx --expected 3

라이브러리 사용:
    from scripts.validate_graph_hwpx import verify_hwpx_with_graph
    result = verify_hwpx_with_graph(open(path, 'rb').read())
"""

import argparse
import io
import re
import sys
import zipfile
from pathlib import Path


def verify_hwpx_with_graph(hwpx_bytes: bytes, expected_graph_count: int | None = None) -> dict:
    """hwpx 바이트열을 검사해 그래프 임베딩의 9개 항목을 확인.

    Args:
        hwpx_bytes: 검사할 hwpx 파일 바이트열.
        expected_graph_count: 기대 그래프 수. None이면 BinData/graph*.png 갯수를 자동 채택.

    Returns:
        dict — {ok: bool, graph_count: int, checks: [{name, ok, detail}], errors: [str]}
    """
    checks: list[dict] = []
    errors: list[str] = []

    def add(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": passed, "detail": detail})
        if not passed:
            errors.append(f"{name}: {detail}")

    with zipfile.ZipFile(io.BytesIO(hwpx_bytes), 'r') as z:
        names = z.namelist()

        # 1) BinData에 graph{N}.png 존재
        bin_graphs = sorted([n for n in names if re.match(r'BinData/graph\d+\.png$', n)])
        actual_count = len(bin_graphs)
        if expected_graph_count is None:
            expected_graph_count = actual_count
        add(
            "BinData/graphN.png 존재",
            actual_count == expected_graph_count,
            f"기대 {expected_graph_count}, 실제 {actual_count} ({bin_graphs})",
        )

        # 2) content.hpf 매니페스트 등록
        try:
            hpf = z.read('Contents/content.hpf').decode('utf-8')
        except KeyError:
            add("content.hpf 존재", False, "Contents/content.hpf 없음")
            return _summarize(checks, errors, expected_graph_count)

        for i in range(expected_graph_count):
            ok = (
                f'id="graph{i}"' in hpf
                and f'href="BinData/graph{i}.png"' in hpf
                and 'isEmbeded="1"' in hpf
            )
            add(f"content.hpf graph{i} 매니페스트", ok, "id/href/isEmbeded 중 하나 누락" if not ok else "")

        # 3) section XML 검증
        section_files = sorted([n for n in names if re.match(r'Contents/section\d+\.xml$', n)])
        if not section_files:
            add("section XML 존재", False, "Contents/section*.xml 없음")
            return _summarize(checks, errors, expected_graph_count)

        all_section = "\n".join(z.read(sf).decode('utf-8') for sf in section_files)

        residual = re.findall(r'\[GRAPH:\d+\]', all_section)
        add(
            "[GRAPH:N] 잔여 텍스트 없음",
            not residual,
            f"잔여: {residual}" if residual else "",
        )

        for i in range(expected_graph_count):
            ref_ok = f'binaryItemIDRef="graph{i}"' in all_section
            add(f"section XML hp:pic graph{i} 참조", ref_ok, "binaryItemIDRef 누락" if not ref_ok else "")

        lineseg_ok = '<hp:linesegarray' in all_section
        add(
            "linesegarray 존재 (한글 거부 방지)",
            lineseg_ok,
            "linesegarray 누락 → 한글이 파일을 거부할 수 있음" if not lineseg_ok else "",
        )

        ctrl_pic = re.search(r'<hp:ctrl[^>]*>\s*<hp:pic', all_section)
        add(
            "hp:ctrl 안 hp:pic 잘못된 패턴 없음",
            ctrl_pic is None,
            "hp:ctrl로 감싸진 hp:pic 발견 → 한글 거부 위험" if ctrl_pic else "",
        )

        # 4) PNG 헤더 sanity (각 graphN.png)
        for n in bin_graphs:
            data = z.read(n)
            sig = data[:8]
            ok = sig == b'\x89PNG\r\n\x1a\n'
            add(f"{n} PNG 시그니처", ok, f"앞 8바이트: {sig!r}" if not ok else "")

    return _summarize(checks, errors, expected_graph_count)


def _summarize(checks, errors, graph_count) -> dict:
    return {
        "ok": not errors,
        "graph_count": graph_count,
        "checks": checks,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="hwpx 그래프 임베딩 검증 (SOT 규칙 9)")
    parser.add_argument("path", help="검사할 hwpx 파일 경로")
    parser.add_argument(
        "--expected",
        type=int,
        default=None,
        help="기대 그래프 수 (생략 시 BinData에서 자동 카운트)",
    )
    args = parser.parse_args()

    p = Path(args.path)
    if not p.exists():
        print(f"[에러] 파일이 없습니다: {p}", file=sys.stderr)
        return 2

    result = verify_hwpx_with_graph(p.read_bytes(), expected_graph_count=args.expected)

    print(f"=== {p.name} (그래프 {result['graph_count']}개) ===")
    for c in result["checks"]:
        mark = "[OK]  " if c["ok"] else "[FAIL]"
        line = f"  {mark} {c['name']}"
        if c["detail"]:
            line += f" -- {c['detail']}"
        print(line)
    print()
    if result["ok"]:
        print(f"전체 결과: PASS ({len(result['checks'])}개 항목 모두 통과)")
        return 0
    print(f"전체 결과: FAIL ({len(result['errors'])}개 결함)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
