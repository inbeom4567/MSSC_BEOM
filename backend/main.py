import logging
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
from typing import List
from pathlib import Path

from services.claude_service import ClaudeService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

app = FastAPI(title="수학 유사문항 생성기")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

claude_service = ClaudeService()


class GenerateRequest(BaseModel):
    problem_base64: str
    problem_media_type: str
    solution_base64: str
    solution_media_type: str
    variant_type: str = "idea"       # "number" | "idea"
    difficulty: str = "similar"      # "easier" | "similar" | "harder"


class VariantSolveRequest(BaseModel):
    problem_base64: str
    problem_media_type: str
    solution_base64: str
    solution_media_type: str
    variant_base64: str
    variant_media_type: str


class PromptFeedbackRequest(BaseModel):
    feedback: str


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/verify")
async def verify_problem(files: List[UploadFile] = File(...)):
    """원본 문제+해설 검증만 수행"""
    logger.info(f"검증 요청: 이미지 {len(files)}개")
    images = _parse_files(await _read_files(files))

    result = await claude_service.verify(images)
    logger.info("검증 완료")
    return {"result": result}


@app.post("/api/generate")
async def generate_variant(files: List[UploadFile] = File(...), variant_type: str = "idea", difficulty: str = "similar"):
    """유사문항 생성 (검증 후)"""
    logger.info(f"유사문항 생성 요청: type={variant_type}, difficulty={difficulty}")
    images = _parse_files(await _read_files(files))

    result = await claude_service.generate_variant(images, variant_type, difficulty)
    logger.info("유사문항 생성 완료")
    return {"result": result}


@app.post("/api/solve-variant")
async def solve_variant(files: List[UploadFile] = File(...)):
    """변형문항 풀이 생성 (이미지 3개: 문제+해설+변형문항)"""
    logger.info(f"변형문항 풀이 요청: 이미지 {len(files)}개")
    images = _parse_files(await _read_files(files))

    result = await claude_service.solve_variant(images)
    logger.info("변형문항 풀이 완료")
    return {"result": result}


@app.post("/api/prompt-feedback")
async def update_prompt(req: PromptFeedbackRequest):
    """프롬프트에 피드백 규칙 추가"""
    logger.info(f"프롬프트 피드백: {req.feedback[:50]}...")

    result = await claude_service.process_feedback(req.feedback)

    # solve_prompt.txt에 규칙 추가
    prompt_path = PROMPTS_DIR / "solve_prompt.txt"
    current = prompt_path.read_text(encoding="utf-8")

    # 마지막 강조 섹션 앞에 규칙 삽입
    marker = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n## ★ 다시 한번 강조"
    if marker in current:
        new_rule = f"\n### 사용자 피드백 규칙:\n{result}\n\n"
        updated = current.replace(marker, new_rule + marker)
    else:
        updated = current + f"\n\n### 사용자 피드백 규칙:\n{result}\n"

    prompt_path.write_text(updated, encoding="utf-8")

    # variant_solve_prompt.txt에도 동일 추가
    variant_path = PROMPTS_DIR / "variant_solve_prompt.txt"
    if variant_path.exists():
        v_current = variant_path.read_text(encoding="utf-8")
        v_marker = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n## ★ 다시 한번 강조"
        if v_marker in v_current:
            v_updated = v_current.replace(v_marker, new_rule + v_marker)
        else:
            v_updated = v_current + f"\n\n### 사용자 피드백 규칙:\n{result}\n"
        variant_path.write_text(v_updated, encoding="utf-8")

    # 프롬프트 다시 로드
    claude_service.reload_prompts()

    logger.info("프롬프트 업데이트 완료")
    return {"result": result, "message": "프롬프트에 규칙이 추가되었습니다."}


@app.get("/api/prompt")
async def get_prompt():
    """현재 프롬프트 내용 조회"""
    prompt_path = PROMPTS_DIR / "solve_prompt.txt"
    return {"prompt": prompt_path.read_text(encoding="utf-8")}


async def _read_files(files: List[UploadFile]) -> list:
    result = []
    for f in files:
        data = await f.read()
        result.append({"data": data, "content_type": f.content_type, "filename": f.filename})
    return result


def _parse_files(files: list) -> list:
    import base64
    images = []
    for f in files:
        images.append({
            "base64": base64.b64encode(f["data"]).decode("utf-8"),
            "media_type": f["content_type"],
        })
    return images
