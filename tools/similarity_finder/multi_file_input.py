"""문제집 복수 파일 선택 + HWP 자동 변환 통합 입력 모듈.

기존 main.py의 _pick_problems()는 단일 파일만 받는다.
본 모듈은 Tkinter filedialog.askopenfilenames로 복수 파일을 받고,
HWP가 섞여 있으면 converter를 거쳐 임시 HWPX로 변환한 뒤 통합 처리 큐를 반환한다.

## 설계 철학
- 순수 로직(select_files_and_prepare)과 GUI 의존성을 분리 → 단위 테스트 용이.
- HWP 변환은 "실행 시점"에 1회만 → 유사문제 검색 파이프라인은 HWPX만 알면 됨.
- 변환 실패 파일은 스킵하고 에러 수집 → 일부 실패가 전체 중단을 유발하지 않도록.

## 호출 예 (GUI 측)
    queue, errors = select_files_and_prepare(parent=root)
    for entry in queue:
        problems_bytes = entry.hwpx_path.read_bytes()
        # ... 기존 read_hwpx → split_problems → comparator.compare 파이프라인
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from tools.similarity_finder import converter


@dataclass
class PreparedEntry:
    """처리 큐의 한 항목.

    Attributes:
        source_path: 사용자가 선택한 원본 파일 경로 (.hwp 또는 .hwpx).
        hwpx_path: 실제로 파이프라인에 투입될 HWPX 경로.
                   원본이 HWPX면 source_path와 동일, HWP면 변환된 임시 파일.
        converted: HWP→HWPX 변환이 일어났는지 (임시 파일 정리 여부 판단용).
    """
    source_path: Path
    hwpx_path: Path
    converted: bool


@dataclass
class PrepareError:
    """준비 단계에서 실패한 파일."""
    source_path: Path
    message: str


def split_by_extension(paths: Sequence[Path]) -> tuple[list[Path], list[Path], list[Path]]:
    """경로 목록을 (hwpx, hwp, 기타)로 분리."""
    hwpx_list: list[Path] = []
    hwp_list: list[Path] = []
    other_list: list[Path] = []
    for p in paths:
        ext = p.suffix.lower()
        if ext == ".hwpx":
            hwpx_list.append(p)
        elif ext == ".hwp":
            hwp_list.append(p)
        else:
            other_list.append(p)
    return hwpx_list, hwp_list, other_list


def prepare_entries(
    paths: Sequence[Path],
    progress_cb=None,
) -> tuple[list[PreparedEntry], list[PrepareError]]:
    """경로 목록을 받아 PreparedEntry 큐와 에러 목록을 반환.

    Args:
        paths: 사용자가 선택한 파일 경로 리스트.
        progress_cb: ``(idx, total, message)`` 콜백. GUI 상태바 업데이트용.

    Returns:
        (queue, errors) 튜플.
    """
    hwpx_list, hwp_list, other_list = split_by_extension([Path(p) for p in paths])

    queue: list[PreparedEntry] = []
    errors: list[PrepareError] = []

    # 1) HWPX는 그대로 큐에 추가
    for p in hwpx_list:
        queue.append(PreparedEntry(source_path=p, hwpx_path=p, converted=False))

    # 2) HWP는 converter로 변환
    total = len(hwp_list)
    for idx, p in enumerate(hwp_list, 1):
        if progress_cb:
            progress_cb(idx, total, f"HWP 변환 중 ({idx}/{total}): {p.name}")
        result = converter.hwp_to_tempfile(p)
        if result.ok and result.hwpx_path is not None:
            queue.append(PreparedEntry(source_path=p, hwpx_path=result.hwpx_path, converted=True))
        else:
            errors.append(PrepareError(source_path=p, message=result.message))

    # 3) 지원하지 않는 확장자는 에러 수집
    for p in other_list:
        errors.append(PrepareError(
            source_path=p,
            message=f"지원하지 않는 확장자: {p.suffix} ({p.name})",
        ))

    return queue, errors


def select_files_and_prepare(parent=None, progress_cb=None):
    """Tkinter 파일 다이얼로그로 복수 파일을 받아 준비 큐를 반환.

    Args:
        parent: Tk 루트 윈도우 (모달 부모용). None이면 기본 루트.
        progress_cb: 변환 진행 콜백.

    Returns:
        (queue, errors) 튜플. 사용자가 다이얼로그를 취소하면 ([], []) 반환.
    """
    # 지연 import — 테스트 환경에서 Tk 초기화 없이 prepare_entries만 써도 되도록.
    from tkinter import filedialog

    paths = filedialog.askopenfilenames(
        parent=parent,
        title="문제집 파일 선택 (여러 개 가능)",
        filetypes=[
            ("한글 문서", "*.hwp *.hwpx"),
            ("HWPX 파일", "*.hwpx"),
            ("HWP 파일", "*.hwp"),
            ("모든 파일", "*.*"),
        ],
    )
    if not paths:
        return [], []

    return prepare_entries([Path(p) for p in paths], progress_cb=progress_cb)


def cleanup(entries: Sequence[PreparedEntry]) -> None:
    """변환으로 생성된 임시 HWPX 파일들을 정리.

    TODO: 유사문제 검색이 끝난 뒤 main.py에서 호출.
    임시 디렉터리(converter.hwp_to_tempfile이 mkdtemp로 생성)도 함께 제거해야 함.
    """
    import shutil
    for entry in entries:
        if not entry.converted:
            continue
        try:
            tmp_dir = entry.hwpx_path.parent
            if tmp_dir.name.startswith("similarity_finder_hwp_"):
                shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass  # best-effort cleanup
