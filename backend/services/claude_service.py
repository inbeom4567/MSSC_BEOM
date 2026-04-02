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


def _merge_usage(u1: dict, u2: dict) -> dict:
    return {
        "input_tokens": u1["input_tokens"] + u2["input_tokens"],
        "output_tokens": u1["output_tokens"] + u2["output_tokens"],
        "total_tokens": u1["total_tokens"] + u2["total_tokens"],
        "cost_usd": round(u1["cost_usd"] + u2["cost_usd"], 4),
        "cost_krw": round(u1["cost_krw"] + u2["cost_krw"], 0),
        "model": u1["model"],
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

    async def _cleanup_output(self, raw_text: str, model_id: str) -> tuple[str, dict]:
        """2차 정제: 내부 사고 과정 제거, 문제-풀이 일치 검증, 최종본 출력."""
        cleanup_prompt = (
            "아래는 유사문항 생성 결과입니다. 다음 작업을 수행하세요:\n\n"
            "1. 내부 사고 과정(잠깐, 다시 확인, 수정하겠습니다, STEP, 검증, ##, **, ✓ 등)을 모두 제거\n"
            "2. 문제 본문과 풀이에서 사용하는 숫자/조건이 일치하는지 확인. 불일치하면 풀이 기준으로 문제를 수정\n"
            "3. 풀이의 최종 답과 -정답- 태그의 답이 일치하는지 확인\n"
            "4. 깔끔하게 정리된 최종본만 출력\n\n"
            "출력 형식: -유사문항- / -정답- / -해설- 태그만 사용. 다른 텍스트 금지.\n\n"
            "--- 원본 ---\n"
            f"{raw_text}"
        )

        message = await self.client.messages.create(
            model=model_id,
            max_tokens=4096,
            system="당신은 수학 문서 편집자입니다. 주어진 텍스트에서 불필요한 내용을 제거하고 깔끔하게 정리하세요. 수식 대괄호 규칙을 그대로 유지하세요.",
            messages=[{"role": "user", "content": cleanup_prompt}],
        )
        return message.content[0].text, _make_usage_info(message, model_id)

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
        raw_text = message.content[0].text
        usage1 = _make_usage_info(message, model_id)

        # 2차 정제
        cleaned_text, usage2 = await self._cleanup_output(raw_text, model_id)
        processed_text, graphs = process_graphs_in_text(cleaned_text)

        total_usage = _merge_usage(usage1, usage2)
        return {"text": processed_text, "graphs": graphs, "usage": total_usage}

    async def solve_variant(self, images: list[dict], model: str = "sonnet") -> dict:
        """변형문항 풀이 생성"""
        content = self._make_image_content(images)
        model_id = self._get_model(model)
        content.append({
            "type": "text",
            "text": "첫 번째 이미지는 원본 문제, 두 번째는 원본 해설, 세 번째는 변형문항입니다. "
                    "원본 문제와 해설은 정확합니다. "
                    "세 번째 이미지의 변형문항을 그대로 두고, 풀이만 작성해주세요. "
                    "변형문항의 내용을 절대 수정하지 마세요. 문제는 그대로, 풀이만 쓰는 겁니다. "
                    "원본 해설의 풀이 형식(단계별 계산, 수식 표기)을 참고하되, "
                    "변형문항이 묻는 것에 맞게 풀이를 작성하세요. "
                    "예: 원본이 '옳은 것은?'이고 변형이 '옳지 않은 것은?'이면, 각 보기를 검토한 뒤 틀린 것을 찾는 풀이를 써야 합니다.",
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

    async def generate_variant_from_text(self, text_content: str, variant_type: str, difficulty: str, model: str = "sonnet", custom_prompt: str = "") -> dict:
        """HWPX에서 추출한 텍스트로 유사문항 생성"""
        model_id = self._get_model(model)

        type_desc = "숫자와 조건의 값만 변경하는 숫자 변형" if variant_type == "number" else "문제의 구조나 아이디어를 변경하는 아이디어 변형"
        diff_desc = {"easier": "원본보다 쉬운", "similar": "원본과 비슷한", "harder": "원본보다 어려운"}.get(difficulty, "원본과 비슷한")

        user_text = (
            f"아래는 한글 파일에서 추출한 원본 문제와 해설입니다.\n"
            f"원본 문제와 해설은 정확합니다.\n"
            f"{diff_desc} 난이도로 {type_desc}을 해주세요.\n"
            f"유사문항을 만들고 원본 해설과 동일한 풀이 흐름으로 해설해주세요.\n\n"
            f"{text_content}"
        )
        if custom_prompt:
            user_text += f"\n\n★ 추가 지시사항: {custom_prompt}"

        message = await self.client.messages.create(
            model=model_id,
            max_tokens=4096,
            system=self.solve_prompt,
            messages=[{"role": "user", "content": user_text}],
        )
        raw_text = message.content[0].text
        usage1 = _make_usage_info(message, model_id)

        # 2차 정제
        cleaned_text, usage2 = await self._cleanup_output(raw_text, model_id)
        processed_text, graphs = process_graphs_in_text(cleaned_text)

        total_usage = _merge_usage(usage1, usage2)
        return {"text": processed_text, "graphs": graphs, "usage": total_usage}

    async def solve_variant_from_text(self, text_content: str, model: str = "sonnet") -> dict:
        """HWPX에서 추출한 텍스트로 변형문항 해설 작성"""
        model_id = self._get_model(model)

        user_text = (
            f"아래는 한글 파일에서 추출한 원본 문제, 원본 해설, 유사문제입니다.\n"
            f"원본 문제와 해설은 정확합니다.\n"
            f"유사문제를 그대로 두고, 해설만 작성해주세요.\n"
            f"유사문제의 내용을 절대 수정하지 마세요.\n"
            f"원본 해설의 풀이 흐름과 형식을 그대로 따라서 해설을 작성해주세요.\n"
            f"단, 유사문제가 묻는 것에 맞게 해설을 작성하세요.\n\n"
            f"{text_content}"
        )

        message = await self.client.messages.create(
            model=model_id,
            max_tokens=4096,
            system=self.variant_solve_prompt,
            messages=[{"role": "user", "content": user_text}],
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
