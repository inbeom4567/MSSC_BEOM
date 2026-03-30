import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


class ClaudeService:
    MODEL_FAST = "claude-sonnet-4-20250514"    # 검증용 (저렴)
    MODEL_STRONG = "claude-opus-4-20250514"    # 생성용 (고품질)

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.solve_prompt = _load_prompt("solve_prompt.txt")
        self.variant_solve_prompt = _load_prompt("variant_solve_prompt.txt")

    def reload_prompts(self):
        self.solve_prompt = _load_prompt("solve_prompt.txt")
        self.variant_solve_prompt = _load_prompt("variant_solve_prompt.txt")

    def _make_image_content(self, images: list[dict]) -> list:
        content = []
        for img in images:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img["media_type"],
                    "data": img["base64"],
                },
            })
        return content

    async def verify(self, images: list[dict]) -> str:
        """원본 문제+해설 검증 (Sonnet - 저렴)"""
        content = self._make_image_content(images)
        content.append({
            "type": "text",
            "text": "첫 번째 이미지는 수학 문제, 두 번째는 해설입니다. "
                    "문제와 해설에 수학적 오류가 없는지 검증해주세요. "
                    "오류가 없으면 '오류 없음'이라고만 답하고, "
                    "오류가 있으면 어디가 틀렸는지 간결하게 설명해주세요.",
        })

        message = await self.client.messages.create(
            model=self.MODEL_FAST,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        return message.content[0].text

    async def generate_variant(self, images: list[dict], variant_type: str, difficulty: str) -> str:
        """유사문항 생성 + 풀이 (Opus - 고품질)"""
        content = self._make_image_content(images)

        type_desc = "숫자와 조건의 값만 변경하는 숫자 변형" if variant_type == "number" else "문제의 구조나 아이디어를 변경하는 아이디어 변형"
        diff_desc = {"easier": "원본보다 쉬운", "similar": "원본과 비슷한", "harder": "원본보다 어려운"}.get(difficulty, "원본과 비슷한")

        content.append({
            "type": "text",
            "text": f"첫 번째 이미지는 원본 문제, 두 번째는 원본 해설입니다. "
                    f"{diff_desc} 난이도로 {type_desc}을 해주세요. "
                    f"유사문항을 만들고 원본 해설과 유사한 흐름으로 풀이해주세요.",
        })

        message = await self.client.messages.create(
            model=self.MODEL_STRONG,
            max_tokens=4096,
            system=self.solve_prompt,
            messages=[{"role": "user", "content": content}],
        )
        return message.content[0].text

    async def solve_variant(self, images: list[dict]) -> str:
        """변형문항 풀이 생성 (Opus - 고품질)"""
        content = self._make_image_content(images)
        content.append({
            "type": "text",
            "text": "첫 번째 이미지는 원본 문제, 두 번째는 원본 해설, 세 번째는 변형문항입니다. "
                    "원본 해설의 풀이 흐름과 형식을 최대한 따라서 변형문항의 풀이를 작성해주세요.",
        })

        message = await self.client.messages.create(
            model=self.MODEL_STRONG,
            max_tokens=4096,
            system=self.variant_solve_prompt,
            messages=[{"role": "user", "content": content}],
        )
        return message.content[0].text

    async def process_feedback(self, feedback: str) -> str:
        """사용자 피드백을 프롬프트 규칙으로 변환 (Sonnet - 저렴)"""
        message = await self.client.messages.create(
            model=self.MODEL_FAST,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": f"다음 피드백을 한글 수식입력기 프롬프트 규칙으로 변환해주세요. "
                           f"간결한 규칙 형태(× 틀림 / ○ 올바름)로 작성:\n\n{feedback}",
            }],
        )
        return message.content[0].text
