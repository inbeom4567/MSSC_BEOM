import os
import json
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from services.graph_service import process_graphs_in_text

load_dotenv()

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# 토큰당 가격 (USD per 1M tokens)
PRICING = {
    "claude-sonnet-4-20250514": {"input": 3, "output": 15},
    "claude-opus-4-20250514": {"input": 15, "output": 75},
}


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = PRICING.get(model, {"input": 3, "output": 15})
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000


def _make_usage_info(message, model: str) -> dict:
    input_t = message.usage.input_tokens
    output_t = message.usage.output_tokens
    cost_usd = _calc_cost(model, input_t, output_t)
    return {
        "input_tokens": input_t,
        "output_tokens": output_t,
        "total_tokens": input_t + output_t,
        "cost_usd": round(cost_usd, 4),
        "cost_krw": round(cost_usd * 1450, 0),  # 대략적 환율
        "model": model,
    }


class ClaudeService:
    MODELS = {
        "sonnet": "claude-sonnet-4-20250514",
        "opus": "claude-opus-4-20250514",
    }

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.mapping_ref = self._load_mapping_reference()
        self.solve_prompt = self._build_prompt("solve_prompt.txt")
        self.variant_solve_prompt = self._build_prompt("variant_solve_prompt.txt")

    def _load_mapping_reference(self) -> str:
        """hwp_math_mapping.json에서 수식 변환 예시를 텍스트로 추출"""
        mapping_path = DATA_DIR / "hwp_math_mapping.json"
        with open(mapping_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        lines = ["\n\n## 한글 수식 매핑 사전 (정확한 변환 예시)"]
        lines.append("아래 예시를 반드시 참고하여 수식을 변환하세요.\n")

        for category, items in data.get("mappings", {}).items():
            if isinstance(items, list):
                for item in items:
                    lines.append(f"  {item['math']} → {item['hwp']}")
            elif isinstance(items, dict):
                for sub_key, sub_items in items.items():
                    if isinstance(sub_items, list):
                        for item in sub_items:
                            lines.append(f"  {item['math']} → {item['hwp']}")

        # global_rules도 포함
        rules = data.get("global_rules", {})
        lines.append("\n## 글로벌 규칙")
        lines.append(f"  기본 폰트: {rules.get('font_mode', {}).get('default', 'italic')}")
        lines.append(f"  로마체(rm): {rules.get('font_mode', {}).get('roman', '')}")
        lines.append(f"  백틱 공백: {rules.get('spacing', {}).get('backtick', '')}")
        lines.append(f"  키워드 공백: {rules.get('spacing', {}).get('keyword_spacing', '')}")
        lines.append(f"  수식 맨 앞 아래첨자: {rules.get('subscript_at_start', '')}")

        return "\n".join(lines)

    def _build_prompt(self, filename: str) -> str:
        """프롬프트 텍스트 + 매핑 사전 예시를 결합"""
        base = _load_prompt(filename)
        return base + self.mapping_ref

    def reload_prompts(self):
        self.solve_prompt = self._build_prompt("solve_prompt.txt")
        self.variant_solve_prompt = self._build_prompt("variant_solve_prompt.txt")

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

    def _get_model(self, model: str) -> str:
        return self.MODELS.get(model, self.MODELS["sonnet"])

    async def generate_variant(self, images: list[dict], variant_type: str, difficulty: str, model: str = "sonnet", custom_prompt: str = "") -> dict:
        """유사문항 생성 + 풀이"""
        content = self._make_image_content(images)
        model_id = self._get_model(model)

        type_desc = "숫자와 조건의 값만 변경하는 숫자 변형" if variant_type == "number" else "문제의 구조나 아이디어를 변경하는 아이디어 변형"
        diff_desc = {"easier": "원본보다 쉬운", "similar": "원본과 비슷한", "harder": "원본보다 어려운"}.get(difficulty, "원본과 비슷한")

        user_text = (
            f"첫 번째 이미지는 원본 문제, 두 번째는 원본 해설입니다. "
            f"원본 문제와 해설은 정확합니다. "
            f"{diff_desc} 난이도로 {type_desc}을 해주세요. "
            f"유사문항을 만들고 원본 해설과 동일한 풀이 흐름으로 풀이해주세요."
        )
        if custom_prompt:
            user_text += f"\n\n★ 추가 지시사항: {custom_prompt}"

        content.append({"type": "text", "text": user_text})

        message = await self.client.messages.create(
            model=model_id,
            max_tokens=4096,
            system=self.solve_prompt,
            messages=[{"role": "user", "content": content}],
        )
        text = message.content[0].text
        processed_text, graphs = process_graphs_in_text(text)
        return {
            "text": processed_text,
            "graphs": graphs,
            "usage": _make_usage_info(message, model_id),
        }

    async def solve_variant(self, images: list[dict], model: str = "sonnet") -> dict:
        """변형문항 풀이 생성"""
        content = self._make_image_content(images)
        model_id = self._get_model(model)
        content.append({
            "type": "text",
            "text": "첫 번째 이미지는 원본 문제, 두 번째는 원본 해설, 세 번째는 변형문항입니다. "
                    "원본 문제와 해설은 정확합니다. "
                    "원본 해설의 풀이 흐름과 형식을 그대로 따라서 변형문항의 풀이를 작성해주세요.",
        })

        message = await self.client.messages.create(
            model=model_id,
            max_tokens=4096,
            system=self.variant_solve_prompt,
            messages=[{"role": "user", "content": content}],
        )
        text = message.content[0].text
        processed_text, graphs = process_graphs_in_text(text)
        return {
            "text": processed_text,
            "graphs": graphs,
            "usage": _make_usage_info(message, model_id),
        }

    async def refine(self, original_result: str, instruction: str, model: str = "sonnet") -> dict:
        """생성된 결과를 수정"""
        model_id = self._get_model(model)

        message = await self.client.messages.create(
            model=model_id,
            max_tokens=4096,
            system=self.solve_prompt,
            messages=[
                {"role": "user", "content": "아래 유사문항과 풀이를 생성했습니다:\n\n" + original_result},
                {"role": "assistant", "content": "네, 확인했습니다."},
                {"role": "user", "content": f"다음 지시에 따라 위 문제와 풀이를 수정해주세요:\n\n{instruction}\n\n수정된 전체 결과를 다시 출력해주세요. 기존 출력 형식(-유사문항-, -풀이-)을 유지하세요."},
            ],
        )
        text = message.content[0].text
        processed_text, graphs = process_graphs_in_text(text)
        return {
            "text": processed_text,
            "graphs": graphs,
            "usage": _make_usage_info(message, model_id),
        }

    async def process_feedback(self, feedback: str) -> str:
        """사용자 피드백을 프롬프트 규칙으로 변환"""
        message = await self.client.messages.create(
            model=self.MODELS["sonnet"],
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": f"다음 피드백을 한글 수식입력기 프롬프트 규칙으로 변환해주세요. "
                           f"간결한 규칙 형태(× 틀림 / ○ 올바름)로 작성:\n\n{feedback}",
            }],
        )
        return message.content[0].text
