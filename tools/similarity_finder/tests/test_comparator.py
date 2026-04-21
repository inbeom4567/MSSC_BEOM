"""comparator 단위 테스트."""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (comparator 임포트용)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from tools.similarity_finder.comparator import build_user_message


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
