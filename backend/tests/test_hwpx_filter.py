"""HWPX 문제 번호 필터 테스트."""
import sys
from pathlib import Path

# backend 폴더를 import path에 추가
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import pytest
from services.hwpx_service import (
    read_hwpx, split_problems, filter_hwpx_by_numbers,
)

SAMPLE = Path(__file__).resolve().parent.parent.parent / "유사문항_1775116804527.hwpx"


@pytest.fixture
def sample_bytes():
    if not SAMPLE.exists():
        pytest.skip(f"샘플 HWPX 없음: {SAMPLE}")
    return SAMPLE.read_bytes()


def test_filter_keeps_specified_numbers(sample_bytes):
    """keep_numbers에 있는 문제만 남아야 한다."""
    # 샘플에 원래 몇 개 문제가 있는지 확인
    original_text = read_hwpx(sample_bytes)
    original_problems = split_problems(original_text)
    assert len(original_problems) >= 2, "테스트용 샘플은 최소 2문제 이상 필요"

    # 첫 번째 문제 번호만 남기기
    first_num = original_problems[0]["number"]
    filtered_bytes = filter_hwpx_by_numbers(sample_bytes, {first_num})

    # 필터링된 결과에는 해당 문제만 남아있어야 함
    filtered_text = read_hwpx(filtered_bytes)
    filtered_problems = split_problems(filtered_text)
    assert len(filtered_problems) == 1
    assert filtered_problems[0]["number"] == first_num


def test_filter_empty_set_returns_valid_hwpx(sample_bytes):
    """빈 집합이면 문제 없는 HWPX를 반환 (에러 없이)."""
    result = filter_hwpx_by_numbers(sample_bytes, set())
    # 열 수 있어야 함
    text = read_hwpx(result)
    problems = split_problems(text)
    # 문제가 0개일 수도, split_problems의 fallback으로 1개일 수도 있음
    # 핵심은 예외 없이 처리됨
    assert isinstance(problems, list)


def test_filter_multiple_numbers(sample_bytes):
    """여러 번호 유지."""
    original_text = read_hwpx(sample_bytes)
    original_problems = split_problems(original_text)
    if len(original_problems) < 2:
        pytest.skip("2문제 이상 필요")

    nums = {p["number"] for p in original_problems[:2]}
    filtered_bytes = filter_hwpx_by_numbers(sample_bytes, nums)

    filtered_problems = split_problems(read_hwpx(filtered_bytes))
    assert {p["number"] for p in filtered_problems} == nums


def test_filter_preserves_zip_structure(sample_bytes):
    """ZIP 구조 유지 — mimetype, META-INF 등 필수 파일이 남아있어야."""
    import zipfile, io
    filtered_bytes = filter_hwpx_by_numbers(sample_bytes, {1})
    with zipfile.ZipFile(io.BytesIO(filtered_bytes), 'r') as z:
        names = z.namelist()
        assert 'mimetype' in names
        assert 'Contents/section0.xml' in names
        assert 'META-INF/container.xml' in names
