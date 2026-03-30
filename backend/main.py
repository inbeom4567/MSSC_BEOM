import logging
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
from typing import List
from pathlib import Path

from services.claude_service import ClaudeService
from services import history_service

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


class PromptFeedbackRequest(BaseModel):
    feedback: str


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/generate")
async def generate_variant(files: List[UploadFile] = File(...), variant_type: str = "idea", difficulty: str = "similar", model: str = "sonnet"):
    logger.info(f"유사문항 생성 요청: type={variant_type}, difficulty={difficulty}, model={model}")
    images = _parse_files(await _read_files(files))

    try:
        data = await claude_service.generate_variant(images, variant_type, difficulty, model)
        logger.info(f"유사문항 생성 완료: {data['usage']['total_tokens']} tokens")

        entry_id = history_service.save_history({
            "type": "generate",
            "variant_type": variant_type,
            "difficulty": difficulty,
            "model": model,
            "result": data["text"],
            "usage": data["usage"],
        })

        return {"result": data["text"], "usage": data["usage"], "history_id": entry_id}
    except Exception as e:
        logger.error(f"유사문항 생성 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/solve-variant")
async def solve_variant(files: List[UploadFile] = File(...), model: str = "sonnet"):
    logger.info(f"변형문항 풀이 요청: model={model}")
    images = _parse_files(await _read_files(files))

    try:
        data = await claude_service.solve_variant(images, model)
        logger.info(f"변형문항 풀이 완료: {data['usage']['total_tokens']} tokens")

        entry_id = history_service.save_history({
            "type": "solve",
            "model": model,
            "result": data["text"],
            "usage": data["usage"],
        })

        return {"result": data["text"], "usage": data["usage"], "history_id": entry_id}
    except Exception as e:
        logger.error(f"변형문항 풀이 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
async def get_history():
    return {"items": history_service.get_history_list()}


@app.get("/api/history/{entry_id}")
async def get_history_detail(entry_id: str):
    detail = history_service.get_history_detail(entry_id)
    if not detail:
        raise HTTPException(status_code=404, detail="히스토리를 찾을 수 없습니다.")
    return detail


@app.delete("/api/history/{entry_id}")
async def delete_history(entry_id: str):
    history_service.delete_history(entry_id)
    return {"message": "삭제되었습니다."}


@app.post("/api/prompt-feedback")
async def update_prompt(req: PromptFeedbackRequest):
    logger.info(f"프롬프트 피드백: {req.feedback[:50]}...")
    result = await claude_service.process_feedback(req.feedback)

    for filename in ["solve_prompt.txt", "variant_solve_prompt.txt"]:
        prompt_path = PROMPTS_DIR / filename
        if not prompt_path.exists():
            continue
        current = prompt_path.read_text(encoding="utf-8")
        marker = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n## ★ 다시 한번 강조"
        new_rule = f"\n### 사용자 피드백 규칙:\n{result}\n\n"
        if marker in current:
            updated = current.replace(marker, new_rule + marker)
        else:
            updated = current + f"\n\n### 사용자 피드백 규칙:\n{result}\n"
        prompt_path.write_text(updated, encoding="utf-8")

    claude_service.reload_prompts()
    return {"result": result, "message": "프롬프트에 규칙이 추가되었습니다."}


async def _read_files(files: List[UploadFile]) -> list:
    result = []
    for f in files:
        data = await f.read()
        result.append({"data": data, "content_type": f.content_type, "filename": f.filename})
    return result


def _parse_files(files: list) -> list:
    images = []
    for f in files:
        images.append({
            "base64": base64.b64encode(f["data"]).decode("utf-8"),
            "media_type": f["content_type"],
        })
    return images
