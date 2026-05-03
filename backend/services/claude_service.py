import os
import json
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from services.graph_service import process_graphs_in_text

load_dotenv()

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

ADVISOR_MODEL = "claude-opus-4-7"

# 토큰당 가격 (USD per 1M tokens)
PRICING = {
    "claude-sonnet-4-20250514": {"input": 3, "output": 15},
    "claude-sonnet-4-6": {"input": 3, "output": 15},
    "claude-opus-4-20250514": {"input": 15, "output": 75},
    "claude-opus-4-6": {"input": 15, "output": 75},
    "claude-opus-4-7": {"input": 15, "output": 75},
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


def _extract_text(message) -> str:
    """advisor tool 응답에서 텍스트 블록만 추출"""
    return "".join(
        block.text for block in message.content
        if getattr(block, "type", "") == "text" and hasattr(block, "text")
    )


def _make_usage_with_advisor(message, executor_model_id: str) -> dict:
    """Advisor 비용 포함 사용량 계산"""
    exec_input = message.usage.input_tokens
    exec_output = message.usage.output_tokens
    exec_cost = _calc_cost(executor_model_id, exec_input, exec_output)

    adv_input = adv_output = 0
    adv_cost = 0.0
    iterations = getattr(message.usage, "iterations", None)
    if iterations:
        for it in iterations:
            if getattr(it, "type", "") == "advisor_message":
                ai = getattr(it, "input_tokens", 0)
                ao = getattr(it, "output_tokens", 0)
                adv_input += ai
                adv_output += ao
                adv_cost += _calc_cost(ADVISOR_MODEL, ai, ao)

    total_usd = exec_cost + adv_cost
    return {
        "input_tokens": exec_input + adv_input,
        "output_tokens": exec_output + adv_output,
        "total_tokens": exec_input + exec_output + adv_input + adv_output,
        "cost_usd": round(total_usd, 4),
        "cost_krw": round(total_usd * 1450, 0),
        "model": executor_model_id,
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
        self.curriculum = self._load_curriculum()
        self.solve_prompt = self._build_prompt("solve_prompt.txt")
        self.variant_solve_prompt = self._build_prompt("variant_solve_prompt.txt")

    def _load_curriculum(self) -> dict:
        """교육과정 매핑 데이터 로드"""
        curriculum_path = DATA_DIR / "curriculum.json"
        with open(curriculum_path, "r", encoding="utf-8") as f:
            return json.load(f).get("grades", {})

    def _get_grade_prompt(self, grade: str) -> str:
        """학년에 맞는 교육과정 제약 프롬프트 생성"""
        if not grade or grade == "none":
            return ""
        info = self.curriculum.get(grade)
        if not info:
            return ""
        lines = [f"\n\n★★★ 학년 제약: {info['label']} ({info.get('subject', '수학')}) ★★★"]
        lines.append(f"이 학생은 {info['description']} 과정을 배우고 있습니다.")
        if info.get("allowed"):
            lines.append(f"사용 가능한 개념: {', '.join(info['allowed'])}")
        if info.get("forbidden"):
            lines.append(f"절대 사용 금지 개념: {', '.join(info['forbidden'])}")
            lines.append(f"위 금지 개념은 아직 배우지 않았으므로 풀이에 절대 사용하지 마세요.")
        lines.append(f"반드시 {info['label']} 수준에서 이해할 수 있는 풀이만 작성하세요.")
        return "\n".join(lines)

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
        """프롬프트 텍스트 + 매핑 사전 예시 + few-shot 예시를 결합"""
        base = _load_prompt(filename)
        try:
            fewshot = _load_prompt("fewshot_examples.txt")
        except FileNotFoundError:
            fewshot = ""
        return base + self.mapping_ref + ("\n\n" + fewshot if fewshot else "")

    async def _call_with_advisor(self, model_id: str, max_tokens: int, system: str, messages: list) -> tuple[str, dict]:
        """Advisor Tool(Opus)로 전략 조언 받으며 생성 (베타). 실패 시 일반 호출로 폴백."""
        try:
            message = await self.client.beta.messages.create(
                model=model_id,
                max_tokens=max_tokens,
                betas=["advisor-tool-2026-03-01"],
                tools=[{"type": "advisor_20260301", "name": "advisor", "model": ADVISOR_MODEL}],
                system=system,
                messages=messages,
            )
            return _extract_text(message), _make_usage_with_advisor(message, model_id)
        except Exception:
            message = await self.client.messages.create(
                model=model_id,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            )
            return message.content[0].text, _make_usage_info(message, model_id)

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
        """2차 검증: 계산 독립 재검산 + 문제-풀이 일치 + 형식 정리."""
        cleanup_prompt = (
            "아래는 유사문항과 해설 초안입니다. 다음을 순서대로 수행하세요.\n\n"
            "【검증 1: 계산 재검산】\n"
            "해설의 각 계산 단계를 처음부터 독립적으로 다시 계산하세요.\n"
            "오류가 있으면 올바른 값으로 수정하세요. 수식 코드도 함께 수정하세요.\n\n"
            "【검증 2: 문제-풀이 일관성】\n"
            "문제에서 제시한 숫자·조건과 풀이에서 사용한 값이 일치하는지 확인하세요.\n"
            "불일치하면 풀이 계산 결과를 기준으로 문제의 숫자/조건을 수정하세요.\n\n"
            "【검증 3: 정답 확인】\n"
            "풀이 마지막에 도달한 값과 -정답- 태그의 값이 일치하는지 확인하세요.\n"
            "불일치하면 풀이 계산 결과로 정답 태그를 수정하세요.\n\n"
            "【검증 4: 형식 정리】\n"
            "내부 사고 과정(잠깐, 다시 확인, 수정, STEP, 검증, ##, **, ✓ 등)을 제거하세요.\n\n"
            "★★★ 절대 규칙 ★★★\n"
            "- 수식은 반드시 대괄호 [수식코드] 형태 유지. $수식$ 또는 LaTeX 형식 금지.\n"
            "- 출력 형식: -유사문항- / -정답- / -해설- 태그만 사용. 다른 텍스트 금지.\n\n"
            "--- 원본 ---\n"
            f"{raw_text}"
        )

        message = await self.client.messages.create(
            model=model_id,
            max_tokens=8192,
            system=(
                "당신은 고등학교 수학 검토 전문가입니다. "
                "계산을 직접 재수행하여 오류를 찾고, 올바른 값으로 수정합니다. "
                "수식 대괄호 [ ] 형식을 절대 변경하지 마세요."
            ),
            messages=[{"role": "user", "content": cleanup_prompt}],
        )
        return message.content[0].text, _make_usage_info(message, model_id)

    async def _verify_solve_output(self, raw_text: str, model_id: str) -> tuple[str, dict]:
        """변형문항 풀이 검증: 계산 재검산 + 정답 확인 + 형식 정리."""
        verify_prompt = (
            "아래는 변형문항 풀이 초안입니다. 다음을 수행하세요.\n\n"
            "【검증 1: 계산 재검산】\n"
            "풀이의 각 계산 단계를 처음부터 독립적으로 다시 계산하세요.\n"
            "오류가 있으면 올바른 값으로 수정하세요.\n\n"
            "【검증 2: 정답 확인】\n"
            "풀이의 최종 결과와 -정답- 태그가 일치하는지 확인하세요.\n"
            "불일치하면 계산 결과를 기준으로 정답 태그를 수정하세요.\n\n"
            "【검증 3: 형식 정리】\n"
            "내부 사고 과정(잠깐, 수정, STEP, ##, **, ✓ 등)을 제거하세요.\n\n"
            "★★★ 절대 규칙 ★★★\n"
            "- 수식은 반드시 대괄호 [수식코드] 형태 유지. $수식$ 또는 LaTeX 형식 금지.\n"
            "- 출력 형식: -풀이- / -정답- 태그만 사용. 다른 텍스트 금지.\n\n"
            "--- 원본 ---\n"
            f"{raw_text}"
        )

        message = await self.client.messages.create(
            model=model_id,
            max_tokens=8192,
            system=(
                "당신은 고등학교 수학 검토 전문가입니다. "
                "계산을 직접 재수행하여 오류를 찾고, 올바른 값으로 수정합니다. "
                "수식 대괄호 [ ] 형식을 절대 변경하지 마세요."
            ),
            messages=[{"role": "user", "content": verify_prompt}],
        )
        return message.content[0].text, _make_usage_info(message, model_id)

    async def generate_variant(self, images: list[dict], variant_type: str, difficulty: str, model: str = "sonnet", custom_prompt: str = "", grade: str = "none", engine: str = "png") -> dict:
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

        grade_prompt = self._get_grade_prompt(grade)
        system_prompt = self.solve_prompt + grade_prompt

        content.append({"type": "text", "text": user_text})

        raw_text, usage1 = await self._call_with_advisor(
            model_id, 8192, system_prompt,
            [{"role": "user", "content": content}],
        )

        # 2차 검증 (계산 재검산 + 형식 정리)
        cleaned_text, usage2 = await self._cleanup_output(raw_text, model_id)
        processed_text, graphs = process_graphs_in_text(cleaned_text, engine=engine)

        total_usage = _merge_usage(usage1, usage2)
        return {"text": processed_text, "graphs": graphs, "usage": total_usage}

    async def solve_variant(self, images: list[dict], model: str = "sonnet", custom_prompt: str = "", grade: str = "none", engine: str = "png") -> dict:
        """변형문항 풀이 생성"""
        content = self._make_image_content(images)
        model_id = self._get_model(model)

        user_text = (
            "첫 번째 이미지는 원본 문제, 두 번째는 원본 해설, 세 번째는 변형문항입니다. "
            "원본 문제와 해설은 정확합니다. "
            "세 번째 이미지의 변형문항을 그대로 두고, 풀이만 작성해주세요. "
            "변형문항의 내용을 절대 수정하지 마세요. 문제는 그대로, 풀이만 쓰는 겁니다. "
            "원본 해설의 풀이 형식(단계별 계산, 수식 표기)을 참고하되, "
            "변형문항이 묻는 것에 맞게 풀이를 작성하세요. "
            "예: 원본이 '옳은 것은?'이고 변형이 '옳지 않은 것은?'이면, 각 보기를 검토한 뒤 틀린 것을 찾는 풀이를 써야 합니다."
        )
        if custom_prompt:
            user_text += f"\n\n★ 추가 지시사항: {custom_prompt}"

        content.append({"type": "text", "text": user_text})

        grade_prompt = self._get_grade_prompt(grade)
        system_prompt = self.variant_solve_prompt + grade_prompt

        raw_text, usage1 = await self._call_with_advisor(
            model_id, 8192, system_prompt,
            [{"role": "user", "content": content}],
        )

        # 2차 검증 (계산 재검산 + 정답 확인)
        verified_text, usage2 = await self._verify_solve_output(raw_text, model_id)
        processed_text, graphs = process_graphs_in_text(verified_text, engine=engine)

        total_usage = _merge_usage(usage1, usage2)
        return {
            "text": processed_text,
            "graphs": graphs,
            "usage": total_usage,
        }

    async def generate_variant_from_text(self, text_content: str, variant_type: str, difficulty: str, model: str = "sonnet", custom_prompt: str = "", grade: str = "none", engine: str = "png") -> dict:
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

        grade_prompt = self._get_grade_prompt(grade)
        system_prompt = self.solve_prompt + grade_prompt

        raw_text, usage1 = await self._call_with_advisor(
            model_id, 8192, system_prompt,
            [{"role": "user", "content": user_text}],
        )

        # 2차 검증
        cleaned_text, usage2 = await self._cleanup_output(raw_text, model_id)
        processed_text, graphs = process_graphs_in_text(cleaned_text, engine=engine)

        total_usage = _merge_usage(usage1, usage2)
        return {"text": processed_text, "graphs": graphs, "usage": total_usage}

    async def solve_variant_from_text(self, text_content: str, model: str = "sonnet", grade: str = "none", engine: str = "png") -> dict:
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

        grade_prompt = self._get_grade_prompt(grade)
        system_prompt = self.variant_solve_prompt + grade_prompt

        raw_text, usage1 = await self._call_with_advisor(
            model_id, 8192, system_prompt,
            [{"role": "user", "content": user_text}],
        )

        # 2차 검증
        verified_text, usage2 = await self._verify_solve_output(raw_text, model_id)
        processed_text, graphs = process_graphs_in_text(verified_text, engine=engine)

        total_usage = _merge_usage(usage1, usage2)
        return {
            "text": processed_text,
            "graphs": graphs,
            "usage": total_usage,
        }

    async def refine(self, original_result: str, instruction: str, model: str = "sonnet", engine: str = "png") -> dict:
        """생성된 결과를 수정"""
        model_id = self._get_model(model)

        text, usage = await self._call_with_advisor(
            model_id, 8192, self.solve_prompt,
            [
                {"role": "user", "content": "아래 유사문항과 풀이를 생성했습니다:\n\n" + original_result},
                {"role": "assistant", "content": "네, 확인했습니다."},
                {"role": "user", "content": f"다음 지시에 따라 위 문제와 풀이를 수정해주세요:\n\n{instruction}\n\n수정된 전체 결과를 다시 출력해주세요. 기존 출력 형식(-유사문항-, -풀이-)을 유지하세요."},
            ],
        )
        processed_text, graphs = process_graphs_in_text(text, engine=engine)
        return {
            "text": processed_text,
            "graphs": graphs,
            "usage": usage,
        }

    async def process_scan(self, ocr_data: dict, mode: str, variant_count: int, model: str, grade: str, output_mode: str = "variant", engine: str = "png") -> dict:
        """스캔본 처리: LaTeX OCR → HWP 변환 + 해설 작성(필요시) + 유사문항 생성.
        output_mode: "variant" | "type_only" | "type_with_solution"

        ocr_data:
          일반 모드: {"problem", "solution", "has_solution", "problem_number"}
          학생 모드: {"printed", "handwriting", "has_solution", "solution", "student_answer"}
        """
        model_id = self._get_model(model)
        grade_prompt = self._get_grade_prompt(grade)

        if mode == "student":
            problem_text = ocr_data.get("printed", "")
            handwriting_text = ocr_data.get("handwriting", "")
            has_solution = ocr_data.get("has_solution", False)
            solution_text = ocr_data.get("solution") or ""
            student_answer = ocr_data.get("student_answer", "")

            ocr_summary = f"【인쇄된 문제】\n{problem_text}"
            if handwriting_text:
                ocr_summary += f"\n\n【학생 손필기】\n{handwriting_text}"
            if student_answer:
                ocr_summary += f"\n\n【학생 최종 답】\n{student_answer}"
        else:
            problem_text = ocr_data.get("problem", "")
            has_solution = ocr_data.get("has_solution", False)
            solution_text = ocr_data.get("solution") or ""
            problem_number = ocr_data.get("problem_number", "")

            ocr_summary = f"【문제】\n{problem_text}"
            if problem_number:
                ocr_summary = f"【문제 번호】{problem_number}\n" + ocr_summary
            if has_solution and solution_text:
                ocr_summary += f"\n\n【해설】\n{solution_text}"

        needs_solution = not has_solution or not solution_text.strip()

        user_text = (
            f"아래는 스캔 이미지에서 추출한 수학 문제입니다 (수식은 LaTeX 형식).\n\n"
            f"{ocr_summary}\n\n"
            f"다음을 수행하세요:\n\n"
            f"1. 【HWP 변환】 문제 텍스트의 모든 수식을 한글 수식입력기 코드(대괄호 형식)로 변환하세요.\n"
            f"   - LaTeX \\begin{{cases}}...\\end{{cases}} → 반드시 HWP `cases {{ 값1 && 조건1 # 값2 && 조건2 }}` 형식으로 변환. `matrix{{}}{{}}` 사용 절대 금지.\n"
        )

        if output_mode == "type_only":
            # 타이핑만: HWP 변환만 (해설/유사문항 없음)
            if has_solution and solution_text.strip():
                user_text += f"2. 【해설 변환】 제공된 해설의 수식도 한글 수식입력기 코드로 변환하세요.\n"
            user_text += (
                f"\n출력 형식 (반드시 이 태그만 사용):\n"
                f"-문제-\n(HWP 형식으로 변환된 문제)\n\n"
            )
            if has_solution and solution_text.strip():
                user_text += f"-해설-\n(HWP 형식으로 변환된 해설)\n\n-정답-\n(정답)\n\n"
        elif output_mode == "type_with_solution":
            # 타이핑+해설: HWP 변환 + 해설 작성 (유사문항 없음)
            if needs_solution:
                user_text += (
                    f"2. 【해설 작성】 위 문제의 풀이와 정답을 작성하세요. "
                    f"단계별로 계산 과정을 상세히 보여주세요.\n"
                )
            else:
                user_text += f"2. 【해설 변환】 제공된 해설의 수식도 한글 수식입력기 코드로 변환하세요.\n"
            user_text += (
                f"\n출력 형식 (반드시 이 태그만 사용):\n"
                f"-문제-\n(HWP 형식으로 변환된 문제)\n\n"
                f"-해설-\n(해설 내용)\n\n"
                f"-정답-\n(정답)\n\n"
            )
        else:
            # variant (기본): HWP 변환 + 해설 + 유사문항
            if needs_solution:
                user_text += (
                    f"2. 【해설 작성】 위 문제의 풀이와 정답을 작성하세요. "
                    f"단계별로 계산 과정을 상세히 보여주세요.\n"
                )
                variant_step = "3"
            else:
                user_text += f"2. 【해설 변환】 제공된 해설의 수식도 한글 수식입력기 코드로 변환하세요.\n"
                variant_step = "3"

            user_text += (
                f"{variant_step}. 【유사문항 생성】 이 문제를 기반으로 유사문항 {variant_count}개를 생성하세요. "
                f"각 유사문항마다 풀이와 정답도 포함하세요.\n\n"
            )
            user_text += (
                f"출력 형식 (반드시 이 태그만 사용):\n"
                f"-문제-\n(HWP 형식으로 변환된 문제)\n\n"
                f"-해설-\n(해설 내용)\n\n"
                f"-정답-\n(정답)\n\n"
            )
            for i in range(1, variant_count + 1):
                user_text += (
                    f"-유사문항{i}-\n(유사문항 {i} 내용)\n\n"
                    f"-유사해설{i}-\n(유사문항 {i} 해설)\n\n"
                    f"-유사정답{i}-\n(유사문항 {i} 정답)\n\n"
                )

        if output_mode in ("type_only", "type_with_solution"):
            mode_guard = (
                "⚠️ 현재 작업 모드: HWP 변환 전용\n"
                "- 유사문항 생성 절대 금지\n"
                "- 아래 사용자 메시지의 출력 형식 태그만 사용할 것\n"
                "- 지정된 태그 외 추가 내용 절대 출력 금지\n\n"
            )
            system_prompt = mode_guard + self.solve_prompt + grade_prompt
        else:
            system_prompt = self.solve_prompt + grade_prompt

        raw_text, usage1 = await self._call_with_advisor(
            model_id, 8192, system_prompt,
            [{"role": "user", "content": user_text}],
        )

        # 검증 패스
        cleaned_text, usage2 = await self._cleanup_scan_output(raw_text, model_id, variant_count)
        processed_text, graphs = process_graphs_in_text(cleaned_text, engine=engine)

        total_usage = _merge_usage(usage1, usage2)
        return {
            "text": processed_text,
            "graphs": graphs,
            "usage": total_usage,
            "ocr_data": ocr_data,
            "mode": mode,
        }

    async def _cleanup_scan_output(self, raw_text: str, model_id: str, variant_count: int) -> tuple[str, dict]:
        """스캔 처리 결과 검증: 계산 재검산 + 형식 정리."""
        tags = "-문제-, -해설-, -정답-"
        for i in range(1, variant_count + 1):
            tags += f", -유사문항{i}-, -유사해설{i}-, -유사정답{i}-"

        verify_prompt = (
            f"아래는 스캔 문제 처리 결과입니다. 다음을 수행하세요:\n\n"
            f"1. 각 해설의 계산을 독립적으로 재검산하여 오류가 있으면 수정\n"
            f"2. 정답 태그와 해설의 최종 답이 일치하는지 확인\n"
            f"3. 내부 사고 과정(STEP, ##, **, ✓ 등) 제거\n"
            f"4. 수식 대괄호 [ ] 형식 유지 (절대 $...$ LaTeX로 바꾸지 말 것)\n\n"
            f"출력 형식: {tags} 태그만 사용.\n\n"
            f"--- 원본 ---\n{raw_text}"
        )

        message = await self.client.messages.create(
            model=model_id,
            max_tokens=8192,
            system="당신은 고등학교 수학 검토 전문가입니다. 계산을 재수행하여 오류를 수정합니다. 수식 [ ] 형식을 절대 변경하지 마세요.",
            messages=[{"role": "user", "content": verify_prompt}],
        )
        return message.content[0].text, _make_usage_info(message, model_id)

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
