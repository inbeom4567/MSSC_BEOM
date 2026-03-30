import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class HwpConverter:
    """한글 수식 매핑 사전 조회 서비스.

    Claude 프롬프트가 직접 한글 수식 코드를 출력하므로,
    이 클래스는 매핑 사전 정보 조회 및 수식 규칙 참조 용도로 사용됩니다.
    """

    def __init__(self):
        mapping_path = DATA_DIR / "hwp_math_mapping.json"
        with open(mapping_path, "r", encoding="utf-8") as f:
            self.mapping = json.load(f)
        self.global_rules = self.mapping.get("global_rules", {})

    def get_mapping_info(self) -> dict:
        """매핑 사전 메타 정보를 반환합니다."""
        return self.mapping.get("meta", {})

    def get_global_rules(self) -> dict:
        """수식 작성 글로벌 규칙을 반환합니다."""
        return self.global_rules

    def lookup(self, category: str) -> list | dict | None:
        """특정 카테고리의 매핑 목록을 조회합니다."""
        return self.mapping.get("mappings", {}).get(category)
