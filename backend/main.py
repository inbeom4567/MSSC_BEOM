import logging
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import base64
import io
from typing import List, Optional
from pathlib import Path

from services.claude_service import ClaudeService
from services import history_service
from services.hwpx_service import read_hwpx, create_hwpx, split_problems
from services.gemini_service import (
    analyze_graph, recognize_handwriting,
    ocr_scan_general, ocr_scan_student_paper,
    detect_problem_bboxes,
)
import asyncio
import fitz  # pymupdf
from PIL import Image
import time
from fastapi.responses import Response, StreamingResponse
import json as json_module
import uuid
import shutil

# 임시 HWPX 파일 저장 (TTL 1시간)
_hwpx_store = {}  # {id: {"data": bytes, "created_at": float}}


def _pdf_to_images(pdf_bytes: bytes) -> list:
    """PDF를 페이지별 PNG base64 이미지 리스트로 변환.
    Returns: [{"image_base64": str, "media_type": "image/png"}, ...]
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        pages = []
        for page in doc:
            pix = page.get_pixmap(dpi=150)
            png_bytes = pix.tobytes("png")
            b64 = base64.b64encode(png_bytes).decode()
            pages.append({"image_base64": b64, "media_type": "image/png"})
        return pages
    finally:
        doc.close()


def _crop_image(image_base64: str, media_type: str, x: float, y: float, w: float, h: float) -> tuple:
    """bbox 비율 좌표로 이미지를 크롭하여 (base64, media_type) 반환."""
    img_bytes = base64.b64decode(image_base64)
    img = Image.open(io.BytesIO(img_bytes))
    iw, ih = img.size
    left = int(x * iw)
    top = int(y * ih)
    right = int((x + w) * iw)
    bottom = int((y + h) * ih)
    # 경계 클리핑
    left, top = max(0, left), max(0, top)
    right, bottom = min(iw, right), min(ih, bottom)
    # 빈 crop 방지
    if right <= left or bottom <= top:
        raise ValueError(f"Invalid bbox: empty crop area ({left},{top},{right},{bottom}). Check bbox coordinates.")
    cropped = img.crop((left, top, right, bottom))
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode(), "image/png"


def _cleanup_store():
    """1시간 이상 된 항목 삭제."""
    cutoff = time.time() - 3600
    expired = [k for k, v in _hwpx_store.items() if v["created_at"] < cutoff]
    for k in expired:
        del _hwpx_store[k]


def _store_hwpx(hwpx_bytes: bytes) -> dict:
    """HWPX 바이트를 저장하고 download_id 반환."""
    _cleanup_store()
    download_id = str(uuid.uuid4())[:8]
    _hwpx_store[download_id] = {"data": hwpx_bytes, "created_at": time.time()}
    return {"download_id": download_id}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# HWP 변환기 가용성 사전 확인 (서버 시작 시 1회)
_hwp_converter_available = False
try:
    import win32com.client  # noqa: F401
    _hwp_converter_available = True
except ImportError:
    pass

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


class RefineRequest(BaseModel):
    original_result: str
    instruction: str
    model: str = "sonnet"


class BboxItem(BaseModel):
    id: str
    page_index: int
    x: float
    y: float
    w: float
    h: float
    label: str = ""
    selected: bool = True


class PageItem(BaseModel):
    page_index: int
    image_base64: str
    media_type: str = "image/png"
    bboxes: List = Field(default_factory=list)


class ScanCropRequest(BaseModel):
    pages: List[PageItem]
    confirmed_bboxes: List[BboxItem]
    output_mode: str = "type_only"
    variant_count: int = 1
    model: str = "sonnet"
    grade: str = "none"
    is_student_paper: bool = False


@app.get("/api/system-info")
async def system_info():
    return {"hwp_converter_available": _hwp_converter_available}


@app.post("/api/hwpx-convert")
async def hwpx_convert(file: UploadFile = File(...)):
    if not _hwp_converter_available:
        raise HTTPException(status_code=400, detail="HWP 변환기를 사용할 수 없습니다. 한글 프로그램이 설치된 Windows 환경에서만 지원됩니다.")
    import tempfile, win32com.client
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ('.hwp',):
        raise HTTPException(status_code=400, detail="HWP 파일만 변환 가능합니다.")
    tmp_dir = tempfile.mkdtemp()
    try:
        src = Path(tmp_dir) / file.filename
        with open(src, 'wb') as f:
            shutil.copyfileobj(file.file, f)
        dst = src.with_suffix('.hwpx')
        hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
        hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        hwp.Open(str(src), "HWP", "forceopen:true")
        hwp.SaveAs(str(dst), "HWPX")
        hwp.Quit()
        if not dst.exists():
            raise HTTPException(status_code=500, detail="HWP → HWPX 변환 실패")
        hwpx_bytes = dst.read_bytes()
        filename = dst.name
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    from fastapi.responses import Response
    return Response(
        content=hwpx_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.get("/api/hwpx-download/{download_id}")
async def download_hwpx(download_id: str):
    """저장된 HWPX 파일 직접 다운로드."""
    entry = _hwpx_store.pop(download_id, None)
    hwpx_bytes = entry["data"] if entry else None
    if not hwpx_bytes:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return Response(
        content=hwpx_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename=result_{download_id}.hwpx"},
    )


@app.post("/api/generate")
async def generate_variant(
    files: List[UploadFile] = File(...),
    variant_type: str = "idea",
    difficulty: str = "similar",
    model: str = "sonnet",
    custom_prompt: str = "",
    grade: str = "none",
):
    logger.info(f"유사문항 생성: type={variant_type}, difficulty={difficulty}, model={model}, grade={grade}, custom={custom_prompt[:30] if custom_prompt else 'none'}")
    images = _parse_files(await _read_files(files))

    try:
        data = await claude_service.generate_variant(images, variant_type, difficulty, model, custom_prompt, grade)
        logger.info(f"유사문항 생성 완료: {data['usage']['total_tokens']} tokens")

        entry_id = history_service.save_history({
            "type": "generate",
            "variant_type": variant_type,
            "difficulty": difficulty,
            "model": model,
            "custom_prompt": custom_prompt,
            "result": data["text"],
            "usage": data["usage"],
        })

        return {"result": data["text"], "graphs": data.get("graphs", []), "usage": data["usage"], "history_id": entry_id}
    except Exception as e:
        logger.error(f"유사문항 생성 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/solve-variant")
async def solve_variant(files: List[UploadFile] = File(...), model: str = "sonnet", grade: str = "none", custom_prompt: str = ""):
    logger.info(f"변형문항 풀이 요청: model={model}")
    images = _parse_files(await _read_files(files))

    try:
        data = await claude_service.solve_variant(images, model, custom_prompt, grade)
        logger.info(f"변형문항 풀이 완료: {data['usage']['total_tokens']} tokens")

        entry_id = history_service.save_history({
            "type": "solve",
            "model": model,
            "result": data["text"],
            "usage": data["usage"],
        })

        return {"result": data["text"], "graphs": data.get("graphs", []), "usage": data["usage"], "history_id": entry_id}
    except Exception as e:
        logger.error(f"변형문항 풀이 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/refine")
async def refine_result(req: RefineRequest):
    """생성된 결과를 수정 요청"""
    logger.info(f"수정 요청: {req.instruction[:50]}...")

    try:
        data = await claude_service.refine(req.original_result, req.instruction, req.model)
        logger.info(f"수정 완료: {data['usage']['total_tokens']} tokens")

        entry_id = history_service.save_history({
            "type": "refine",
            "model": req.model,
            "custom_prompt": req.instruction,
            "result": data["text"],
            "usage": data["usage"],
        })

        return {"result": data["text"], "graphs": data.get("graphs", []), "usage": data["usage"], "history_id": entry_id}
    except Exception as e:
        logger.error(f"수정 에러: {e}")
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


@app.post("/api/hwpx-analyze")
async def hwpx_analyze(file: UploadFile = File(...)):
    """HWPX 파일을 분석하여 문제 수와 미리보기 반환"""
    try:
        file_bytes = await file.read()
        text_content = read_hwpx(file_bytes)
        problems = split_problems(text_content)

        previews = []
        for p in problems:
            # 문제 부분만 추출 (해설 제외)
            problem_text = p['text']
            if '-문제-' in problem_text:
                problem_part = problem_text.split('-해설-')[0].replace('-문제-', '').strip()
            else:
                problem_part = problem_text[:100]
            previews.append({
                "number": p['number'],
                "preview": problem_part[:120] + ('...' if len(problem_part) > 120 else ''),
            })

        return {
            "problem_count": len(problems),
            "problems": previews,
            "raw_text": text_content,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hwpx-generate")
async def hwpx_generate(
    file: UploadFile = File(...),
    variant_type: str = "idea",
    difficulty: str = "similar",
    model: str = "sonnet",
    custom_prompt: str = "",
    grade: str = "none",
):
    """HWPX 파일로 유사문항 생성"""
    logger.info(f"HWPX 유사문항 생성: type={variant_type}, difficulty={difficulty}, model={model}")

    try:
        file_bytes = await file.read()
        text_content = read_hwpx(file_bytes)
        logger.info(f"HWPX 파싱 완료: {len(text_content)}자")

        data = await claude_service.generate_variant_from_text(text_content, variant_type, difficulty, model, custom_prompt, grade)
        logger.info(f"HWPX 유사문항 생성 완료: {data['usage']['total_tokens']} tokens")

        # HWPX 출력 파일 생성
        hwpx_bytes = create_hwpx(data["text"], file_bytes)

        entry_id = history_service.save_history({
            "type": "hwpx_generate",
            "variant_type": variant_type,
            "difficulty": difficulty,
            "model": model,
            "custom_prompt": custom_prompt,
            "result": data["text"],
            "usage": data["usage"],
        })

        return {
            "result": data["text"],
            "graphs": data.get("graphs", []),
            "usage": data["usage"],
            "history_id": entry_id,
            **_store_hwpx(hwpx_bytes),
        }
    except Exception as e:
        logger.error(f"HWPX 유사문항 생성 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hwpx-solve")
async def hwpx_solve(
    file: UploadFile = File(...),
    model: str = "sonnet",
    grade: str = "none",
):
    """HWPX 파일로 변형문항 해설 작성 (문제+해설+유사문제 포함)"""
    logger.info(f"HWPX 변형문항 해설: model={model}")

    try:
        file_bytes = await file.read()
        text_content = read_hwpx(file_bytes)
        logger.info(f"HWPX 파싱 완료: {len(text_content)}자")

        data = await claude_service.solve_variant_from_text(text_content, model, grade)
        logger.info(f"HWPX 변형문항 해설 완료: {data['usage']['total_tokens']} tokens")

        hwpx_bytes = create_hwpx(data["text"], file_bytes)

        entry_id = history_service.save_history({
            "type": "hwpx_solve",
            "model": model,
            "result": data["text"],
            "usage": data["usage"],
        })

        return {
            "result": data["text"],
            "graphs": data.get("graphs", []),
            "usage": data["usage"],
            "history_id": entry_id,
            **_store_hwpx(hwpx_bytes),
        }
    except Exception as e:
        logger.error(f"HWPX 변형문항 해설 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hwpx-batch")
async def hwpx_batch(
    file: UploadFile = File(...),
    variant_type: str = "idea",
    difficulty: str = "similar",
    model: str = "sonnet",
    custom_prompt: str = "",
    selected_numbers: str = "",  # "1,2,3" 또는 "" (전체)
    grade: str = "none",
):
    """HWPX 파일에서 선택된 문제들의 유사문항 생성"""
    logger.info(f"HWPX 일괄 처리: type={variant_type}, difficulty={difficulty}, model={model}, selected={selected_numbers}")

    try:
        file_bytes = await file.read()
        text_content = read_hwpx(file_bytes)
        problems = split_problems(text_content)
        logger.info(f"HWPX 파싱 완료: {len(problems)}개 문제 감지")

        # 선택된 문제만 필터링
        if selected_numbers:
            selected = set(int(n.strip()) for n in selected_numbers.split(',') if n.strip())
            problems = [p for p in problems if p['number'] in selected]
            logger.info(f"선택된 문제: {selected}, 처리할 문제: {len(problems)}개")

        total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0, "cost_krw": 0, "model": ""}

        # 병렬 처리: 선택된 문제들을 동시에 Claude API 호출
        logger.info(f"  {len(problems)}개 문제 병렬 처리 시작...")
        tasks = [
            claude_service.generate_variant_from_text(
                prob["text"], variant_type, difficulty, model, custom_prompt, grade
            )
            for prob in problems
        ]
        all_data = await asyncio.gather(*tasks)

        results = []
        for prob, data in zip(problems, all_data):
            results.append({
                "number": prob["number"],
                "result": data["text"],
                "graphs": data.get("graphs", []),
                "usage": data["usage"],
            })
            for key in ["input_tokens", "output_tokens", "total_tokens"]:
                total_usage[key] += data["usage"][key]
            total_usage["cost_usd"] += data["usage"]["cost_usd"]
            total_usage["cost_krw"] += data["usage"]["cost_krw"]
            total_usage["model"] = data["usage"]["model"]

        # 결과를 하나의 텍스트로 합침
        combined_text = ""
        for r in results:
            combined_text += f"-{r['number']}번-\n{r['result']}\n\n"

        hwpx_bytes = create_hwpx(combined_text.strip(), file_bytes)

        entry_id = history_service.save_history({
            "type": "hwpx_batch",
            "variant_type": variant_type,
            "difficulty": difficulty,
            "model": model,
            "custom_prompt": custom_prompt,
            "result": combined_text.strip(),
            "usage": total_usage,
        })

        logger.info(f"일괄 처리 완료: {len(results)}개, 총 {total_usage['total_tokens']} tokens")

        return {
            "results": results,
            "combined_text": combined_text.strip(),
            "usage": total_usage,
            "history_id": entry_id,
            **_store_hwpx(hwpx_bytes),
            "problem_count": len(results),
        }
    except Exception as e:
        logger.error(f"HWPX 일괄 처리 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan-detect")
async def scan_detect(file: UploadFile = File(...)):
    """이미지 또는 PDF → 페이지별 이미지 변환 + Gemini bbox 감지."""
    logger.info(f"스캔 감지 시작: {file.filename}, {file.content_type}")
    try:
        data = await file.read()
        content_type = file.content_type or "image/jpeg"
        is_pdf = content_type == "application/pdf" or (file.filename or "").lower().endswith(".pdf")

        if is_pdf:
            page_images = _pdf_to_images(data)
        else:
            b64 = base64.b64encode(data).decode()
            page_images = [{"image_base64": b64, "media_type": content_type}]

        async def _detect_one(i: int, pg: dict):
            raw = await asyncio.to_thread(
                detect_problem_bboxes, pg["image_base64"], pg["media_type"]
            )
            return i, pg, raw

        detect_results = await asyncio.gather(
            *[_detect_one(i, pg) for i, pg in enumerate(page_images)]
        )
        detect_results = sorted(detect_results, key=lambda x: x[0])

        pages = []
        for i, pg, raw_bboxes in detect_results:
            total_so_far = sum(len(p["bboxes"]) for p in pages)
            bboxes = [
                {
                    "id": f"p{i}_b{j}",
                    "x": bb.get("x", 0),
                    "y": bb.get("y", 0),
                    "w": bb.get("w", 0),
                    "h": bb.get("h", 0),
                    "label": f"문제 {total_so_far + j + 1}",
                }
                for j, bb in enumerate(raw_bboxes)
            ]
            pages.append({
                "page_index": i,
                "image_base64": pg["image_base64"],
                "media_type": pg["media_type"],
                "bboxes": bboxes,
            })
            logger.info(f"페이지 {i+1}: {len(bboxes)}개 bbox 감지")

        total_bboxes = sum(len(p["bboxes"]) for p in pages)
        logger.info(f"감지 완료: {len(pages)}페이지, 총 {total_bboxes}개 문제")
        return {"pages": pages, "total_pages": len(pages)}
    except Exception as e:
        logger.error(f"스캔 감지 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan-process")
async def scan_process(
    files: List[UploadFile] = File(...),
    mode: str = "general",          # "general" | "student"
    output_mode: str = "variant",   # "variant" | "type_only" | "type_with_solution"
    variant_count: int = 1,         # 1 또는 2
    model: str = "sonnet",
    grade: str = "none",
    page_range: str = "",           # 예) "1-3", "2", "" (전체)
):
    """스캔본 처리: OCR → HWP 변환 (+ 해설/유사문항 output_mode에 따라)"""
    logger.info(f"스캔 처리: mode={mode}, output_mode={output_mode}, variants={variant_count}, model={model}")

    if not files:
        raise HTTPException(status_code=400, detail="이미지 또는 PDF를 업로드하세요.")

    try:
        file = files[0]
        data = await file.read()
        img_b64 = base64.b64encode(data).decode("utf-8")
        content_type = file.content_type or "image/jpeg"

        # Gemini OCR
        if mode == "student":
            ocr_data = ocr_scan_student_paper(img_b64, content_type)
        else:
            ocr_data = ocr_scan_general(img_b64, content_type, page_range)

        logger.info(f"OCR 완료: has_solution={ocr_data.get('has_solution', False)}")

        # Claude 처리
        result = await claude_service.process_scan(ocr_data, mode, variant_count, model, grade, output_mode)
        logger.info(f"스캔 처리 완료: {result['usage']['total_tokens']} tokens")

        entry_id = history_service.save_history({
            "type": "scan",
            "mode": mode,
            "output_mode": output_mode,
            "model": model,
            "result": result["text"],
            "usage": result["usage"],
            "ocr_data": ocr_data,
        })

        return {
            "result": result["text"],
            "graphs": result.get("graphs", []),
            "usage": result["usage"],
            "ocr_data": result["ocr_data"],
            "output_mode": output_mode,
            "history_id": entry_id,
        }
    except Exception as e:
        logger.error(f"스캔 처리 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan-crop-process")
async def scan_crop_process(req: ScanCropRequest):
    """확정된 bbox로 문제 병렬 처리, SSE 스트리밍 응답."""
    _semaphore = asyncio.Semaphore(3)

    async def _process_one(bbox, i: int, page_map: dict):
        label = bbox.label or f"문제 {i + 1}"
        try:
            async with _semaphore:
                page = page_map.get(bbox.page_index)
                if not page:
                    raise ValueError(f"페이지 {bbox.page_index}를 찾을 수 없습니다.")

                cropped_b64, cropped_type = await asyncio.to_thread(
                    _crop_image,
                    page.image_base64, page.media_type,
                    bbox.x, bbox.y, bbox.w, bbox.h,
                )

                if req.is_student_paper:
                    ocr_data = await asyncio.to_thread(
                        ocr_scan_student_paper, cropped_b64, cropped_type
                    )
                    scan_mode = "student"
                else:
                    ocr_data = await asyncio.to_thread(
                        ocr_scan_general, cropped_b64, cropped_type
                    )
                    scan_mode = "general"

                result = await asyncio.wait_for(
                    claude_service.process_scan(
                        ocr_data, scan_mode, req.variant_count,
                        req.model, req.grade, req.output_mode,
                    ),
                    timeout=300.0,
                )

            return {
                "type": "result",
                "problem_id": bbox.id,
                "label": label,
                "result": result["text"],
                "graphs": result.get("graphs", []),
                "ocr_data": result.get("ocr_data", {}),
                "output_mode": req.output_mode,
                "usage": result["usage"],
            }
        except Exception as e:
            logger.error(f"처리 에러 ({label}): {e}")
            return {
                "type": "error",
                "problem_id": bbox.id,
                "label": label,
                "error": str(e),
            }

    async def event_stream():
        selected = [b for b in req.confirmed_bboxes if b.selected]
        page_map = {p.page_index: p for p in req.pages}
        all_results = []

        for i, bbox in enumerate(selected):
            label = bbox.label or f"문제 {i + 1}"
            yield f"data: {json_module.dumps({'type': 'progress', 'problem_id': bbox.id, 'label': label, 'status': 'processing'}, ensure_ascii=False)}\n\n"

        tasks = [
            asyncio.create_task(_process_one(bbox, i, page_map))
            for i, bbox in enumerate(selected)
        ]

        for future in asyncio.as_completed(tasks):
            entry = await future
            if entry["type"] == "result":
                all_results.append(entry)
                logger.info(f"처리 완료: {entry['label']}")
            yield f"data: {json_module.dumps(entry, ensure_ascii=False)}\n\n"

        if all_results:
            history_service.save_history({
                "type": "scan_crop",
                "output_mode": req.output_mode,
                "model": req.model,
                "results": all_results,
                "total": len(all_results),
            })

        yield f"data: {json_module.dumps({'type': 'done', 'total': len(selected)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class ScanVariantRequest(BaseModel):
    ocr_data: dict
    scan_mode: str = "general"
    variant_count: int = 1
    model: str = "sonnet"
    grade: str = "none"
    output_mode: str = "variant"


@app.post("/api/scan-generate-variants")
async def scan_generate_variants(req: ScanVariantRequest):
    """OCR 데이터를 받아 유사문항/해설 생성."""
    logger.info(f"스캔 유사문항 생성: mode={req.scan_mode}, variants={req.variant_count}, model={req.model}, output_mode={req.output_mode}")
    try:
        result = await claude_service.process_scan(
            req.ocr_data, req.scan_mode, req.variant_count, req.model, req.grade,
            output_mode=req.output_mode,
        )
        logger.info(f"스캔 유사문항 생성 완료: {result['usage']['total_tokens']} tokens")

        entry_id = history_service.save_history({
            "type": "scan_variant",
            "mode": req.scan_mode,
            "model": req.model,
            "output_mode": req.output_mode,
            "result": result["text"],
            "usage": result["usage"],
            "ocr_data": req.ocr_data,
        })

        return {
            "result": result["text"],
            "graphs": result.get("graphs", []),
            "usage": result["usage"],
            "ocr_data": result.get("ocr_data", {}),
            "output_mode": req.output_mode,
            "history_id": entry_id,
        }
    except Exception as e:
        logger.error(f"스캔 유사문항 생성 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class TextToHwpxRequest(BaseModel):
    texts: List[str]  # 각 문제별 결과 텍스트 리스트
    filename: str = "scan_result"


@app.post("/api/text-to-hwpx")
async def text_to_hwpx(req: TextToHwpxRequest):
    """여러 개의 텍스트 결과를 하나의 HWPX 파일로 변환."""
    try:
        combined = "\n\n".join(req.texts)
        hwpx_bytes = create_hwpx(combined)
        store_info = _store_hwpx(hwpx_bytes)
        return {
            "download_id": store_info["download_id"],
            "filename": f"{req.filename}.hwpx",
        }
    except Exception as e:
        logger.error(f"HWPX 변환 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/analyze-image")
async def analyze_image_endpoint(file: UploadFile = File(...)):
    """원본 문제 이미지에서 그래프/그림을 분석하여 구조화된 데이터 반환"""
    logger.info(f"이미지 분석 요청: {file.filename}")
    try:
        data = await file.read()
        img_b64 = base64.b64encode(data).decode("utf-8")
        result = analyze_graph(img_b64, file.content_type)
        return {"analysis": result}
    except Exception as e:
        logger.error(f"이미지 분석 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/recognize-handwriting")
async def recognize_handwriting_endpoint(file: UploadFile = File(...)):
    """손필기 이미지에서 수식/텍스트 인식"""
    logger.info(f"손필기 인식 요청: {file.filename}")
    try:
        data = await file.read()
        img_b64 = base64.b64encode(data).decode("utf-8")
        result = recognize_handwriting(img_b64, file.content_type)
        return {"recognition": result}
    except Exception as e:
        logger.error(f"손필기 인식 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
