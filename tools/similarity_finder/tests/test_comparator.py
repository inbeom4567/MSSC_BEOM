"""comparator 단위 테스트."""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (comparator 임포트용)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from tools.similarity_finder.comparator import build_user_message, parse_response, chunk_problems, merge_results
import pytest


def test_build_user_message_basic():
    original = "이차함수 f(x) = x^2 - 2x의 최솟값은?"
    problems = [
        {"number": 1, "text": "일차함수 문제"},
        {"number": 3, "text": "이차함수 f(x) = x^2 + 4x의 최솟값은?"},
    ]
    result = build_user_message(original, problems)
    assert "# 원본 문제" in result
    assert "이차함수 f(x) = x^2 - 2x의 최솟값은?" in result
    assert "# 문제집 (총 2문제)" in result
    assert "## 1번" in result
    assert "## 3번" in result
    assert "일차함수 문제" in result


def test_parse_response_valid_json():
    raw = '{"쌍둥이": [{"번호": 12, "이유": "동일 구조"}], "유형유사": [{"번호": 5, "이유": "같은 단원"}]}'
    result = parse_response(raw)
    assert result["쌍둥이"] == [{"번호": 12, "이유": "동일 구조"}]
    assert result["유형유사"] == [{"번호": 5, "이유": "같은 단원"}]


def test_parse_response_with_markdown_fence():
    raw = '```json\n{"쌍둥이": [], "유형유사": []}\n```'
    result = parse_response(raw)
    assert result == {"쌍둥이": [], "유형유사": []}


def test_parse_response_missing_keys_fills_empty():
    raw = '{"쌍둥이": [{"번호": 1, "이유": "."}]}'
    result = parse_response(raw)
    assert result["쌍둥이"] == [{"번호": 1, "이유": "."}]
    assert result["유형유사"] == []


def test_parse_response_invalid_raises():
    with pytest.raises(ValueError):
        parse_response("아무 JSON도 아님")


def test_chunk_problems_under_limit():
    problems = [{"number": i, "text": f"p{i}"} for i in range(50)]
    chunks = chunk_problems(problems, chunk_size=100)
    assert len(chunks) == 1
    assert len(chunks[0]) == 50


def test_chunk_problems_exact_boundary():
    problems = [{"number": i, "text": f"p{i}"} for i in range(200)]
    chunks = chunk_problems(problems, chunk_size=100)
    assert len(chunks) == 2
    assert len(chunks[0]) == 100
    assert len(chunks[1]) == 100


def test_chunk_problems_partial_last():
    problems = [{"number": i, "text": f"p{i}"} for i in range(250)]
    chunks = chunk_problems(problems, chunk_size=100)
    assert [len(c) for c in chunks] == [100, 100, 50]


def test_merge_results_combines_and_dedupes():
    a = {"쌍둥이": [{"번호": 1, "이유": "a"}], "유형유사": [{"번호": 5, "이유": "b"}]}
    b = {"쌍둥이": [{"번호": 2, "이유": "c"}], "유형유사": [{"번호": 5, "이유": "dup"}]}
    merged = merge_results([a, b])
    assert sorted(x["번호"] for x in merged["쌍둥이"]) == [1, 2]
    # 유형유사에 중복 번호(5)는 첫 번째만 유지
    assert [x["번호"] for x in merged["유형유사"]] == [5]
    assert merged["유형유사"][0]["이유"] == "b"
