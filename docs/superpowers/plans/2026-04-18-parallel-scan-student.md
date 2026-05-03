# 스캔 병렬화 + 학생 시험지 손필기 분리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** scan-detect와 scan-crop-process를 병렬화하여 처리 속도 3배 개선, 학생 시험지 모드에서 손필기를 인쇄 텍스트와 분리하여 Claude에 전달

**Architecture:** scan-detect는 asyncio.gather로 PDF 페이지를 동시 처리. scan-crop-process는 asyncio.Semaphore(3)으로 bbox를 최대 3개 동시 처리하고 as_completed로 SSE 스트리밍 유지. 학생 시험지 모드는 ScanCropRequest에 is_student_paper 필드를 추가하고 ocr_scan_student_paper 호출 후 mode="student"로 process_scan에 전달.

**Tech Stack:** Python asyncio (Semaphore, gather, as_completed, to_thread), FastAPI SSE (StreamingResponse), React useState

---

### Task 1: scan-detect 페이지 병렬화

**Files:**
- Modify: `backend/main.py:464-489` (scan_detect 함수 내부)

- [ ] **Step 1: 현재 동작 확인**

`backend/main.py` 464~489줄을 읽어 현재 순차 루프 구조를 확인한다.

- [ ] **Step 2: scan_detect 함수 내부를 병렬화로 교체**

`backend/main.py`의 `scan_detect` 함수에서 `pages = []` 이후 순차 루프 전체를 다음으로 교체한다:

```python
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
```

- [ ] **Step 3: 서버 재시작 후 단일 페이지 이미지로 smoke test**

```bash
cd backend
python -m uvicorn main:app --port 8001
```

브라우저에서 스캔 탭 → 단일 이미지 업로드 → 감지 버튼 클릭 → 정상 bbox 반환 확인

- [ ] **Step 4: 커밋**

```bash
git add backend/main.py
git commit -m "perf: scan-detect 페이지 병렬 감지 (asyncio.gather)"
```

---

### Task 2: ScanCropRequest에 is_student_paper 필드 추가

**Files:**
- Modify: `backend/main.py:129-136` (ScanCropRequest 클래스)

- [ ] **Step 1: ScanCropRequest 모델에 필드 추가**

`backend/main.py`의 `ScanCropRequest` 클래스를 다음으로 교체한다:

```python
class ScanCropRequest(BaseModel):
    pages: List[PageItem]
    confirmed_bboxes: List[BboxItem]
    output_mode: str = "type_only"
    variant_count: int = 1
    model: str = "sonnet"
    grade: str = "none"
    is_student_paper: bool = False
```

- [ ] **Step 2: 커밋**

```bash
git add backend/main.py
git commit -m "feat: ScanCropRequest에 is_student_paper 필드 추가"
```

---

### Task 3: scan-crop-process 병렬화 + 학생 시험지 OCR 분기

**Files:**
- Modify: `backend/main.py:552-617` (scan_crop_process 함수 전체)
- Import 확인: `backend/main.py` 상단 `from services.gemini_service import ... ocr_scan_student_paper` 추가 필요 시

- [ ] **Step 1: gemini_service import에 ocr_scan_student_paper 포함 확인**

`backend/main.py` 상단 import 줄을 확인한다:

```bash
grep -n "ocr_scan_student_paper\|from services.gemini" backend/main.py | head -5
```

없으면 기존 import 줄에 `ocr_scan_student_paper` 추가:

```python
# 기존
from services.gemini_service import (
    analyze_graph, recognize_handwriting,
    ocr_scan_general, ocr_scan_student_paper, detect_problem_bboxes,
)
```

- [ ] **Step 2: scan_crop_process 함수 전체를 교체**

`backend/main.py`의 `scan_crop_process` 함수(`@app.post("/api/scan-crop-process")` 포함)를 다음으로 교체한다:

```python
@app.post("/api/scan-crop-process")
async def scan_crop_process(req: ScanCropRequest):
    """확정된 bbox로 문제 병렬 처리, SSE 스트리밍 응답."""
    _semaphore = asyncio.Semaphore(3)

    async def _process_one(bbox, i: int, page_map: dict):
        label = bbox.label or f"문제 {i + 1}"
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
            "problem_id": bbox.id,
            "label": label,
            "result": result["text"],
            "graphs": result.get("graphs", []),
            "ocr_data": result.get("ocr_data", {}),
            "output_mode": req.output_mode,
            "usage": result["usage"],
        }

    async def event_stream():
        selected = [b for b in req.confirmed_bboxes if b.selected]
        page_map = {p.page_index: p for p in req.pages}
        all_results = []

        # 시작 알림 (전체 동시)
        for i, bbox in enumerate(selected):
            label = bbox.label or f"문제 {i + 1}"
            yield f"data: {json_module.dumps({'type': 'progress', 'problem_id': bbox.id, 'label': label, 'status': 'processing'}, ensure_ascii=False)}\n\n"

        # 병렬 처리 — Semaphore가 동시 최대 3개 제한
        tasks = [
            asyncio.ensure_future(_process_one(bbox, i, page_map))
            for i, bbox in enumerate(selected)
        ]

        for future in asyncio.as_completed(tasks):
            try:
                entry = await future
                all_results.append(entry)
                logger.info(f"처리 완료: {entry['label']}")
                yield f"data: {json_module.dumps({'type': 'result', **entry}, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.error(f"처리 에러: {e}")
                yield f"data: {json_module.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

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
```

- [ ] **Step 3: 서버 재시작 후 2문제 이상 스캔 테스트**

```bash
cd backend
python -m uvicorn main:app --port 8001
```

브라우저 스캔 탭 → 2문제 이상 선택 → 처리 시작 → 두 문제가 거의 동시에 처리됨 확인
(순차: 40초씩 → 병렬: 약 40초에 둘 다 완료)

- [ ] **Step 4: 커밋**

```bash
git add backend/main.py
git commit -m "perf: scan-crop-process Semaphore(3) 병렬화 + student_paper OCR 분기"
```

---

### Task 4: TabScan 프론트엔드 — 학생 시험지 토글 UI

**Files:**
- Modify: `frontend/src/components/TabScan.jsx`

- [ ] **Step 1: useState 추가**

`TabScan.jsx`의 `const [variantCount, setVariantCount] = useState(1)` 바로 아래에 추가:

```jsx
const [isStudentPaper, setIsStudentPaper] = useState(false)
```

- [ ] **Step 2: API 호출 body에 is_student_paper 추가**

`handleProcess` 함수 내부 `JSON.stringify({...})` 객체에 추가:

```jsx
body: JSON.stringify({
  pages: detectData.pages,
  confirmed_bboxes: confirmedBboxes,
  output_mode: outputMode,
  variant_count: variantCount,
  model,
  grade,
  is_student_paper: isStudentPaper,   // 추가
}),
```

- [ ] **Step 3: 3단계 선택 UI에 토글 버튼 추가**

`frontend/src/components/TabScan.jsx`의 유사문항 수 섹션(`{outputMode === 'variant' && ...}`) 바로 아래에 추가:

```jsx
          <div>
            <p className="text-xs font-semibold text-gray-500 dark:text-[#5A5E70] uppercase tracking-wide mb-2">스캔 유형</p>
            <button
              onClick={() => setIsStudentPaper(v => !v)}
              className={`px-4 py-3 rounded-xl text-sm border transition-colors ${isStudentPaper ? 'border-sky-500 dark:border-violet-500 bg-sky-50 dark:bg-violet-500/10 text-sky-700 dark:text-violet-300 font-semibold' : 'border-gray-200 dark:border-[#353844] text-gray-600 dark:text-[#5A5E70] hover:bg-gray-50 dark:hover:bg-[#2A2D38]'}`}
            >
              <div className="font-semibold">학생 시험지 모드</div>
              <div className="text-xs opacity-70 mt-0.5">손필기 제외, 인쇄 문제만 처리</div>
            </button>
          </div>
```

- [ ] **Step 4: 프론트엔드 빌드 확인**

```bash
cd frontend
npm run build
```

Expected: 에러 없이 빌드 완료

- [ ] **Step 5: 브라우저에서 UI 확인**

브라우저 스캔 탭 → 3단계(처리 방식 선택) → "학생 시험지 모드" 버튼이 토글되는지 확인

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/components/TabScan.jsx
git commit -m "feat: 스캔 탭 학생 시험지 모드 토글 UI 추가"
```

---

### Task 5: 통합 테스트

- [ ] **Step 1: 서버 + 프론트엔드 동시 실행**

```bash
# 터미널 1
cd backend && python -m uvicorn main:app --port 8001

# 터미널 2
cd frontend && npm run dev
```

- [ ] **Step 2: 병렬화 속도 확인**

3문제 이상 선택 후 처리 시작 → 개발자 도구 Network 탭에서 SSE 스트림 확인
- 세 문제의 `progress` 이벤트가 거의 동시에 오는지
- `result` 이벤트가 40초 간격이 아닌 ~동시에 오는지

- [ ] **Step 3: 학생 시험지 모드 확인**

학생 필기가 있는 시험지 이미지 → 학생 시험지 모드 ON → 처리 시작
→ 결과에서 학생 손글씨가 포함되지 않고 인쇄된 문제 텍스트만 처리되는지 확인

- [ ] **Step 4: 최종 커밋**

```bash
git add .
git commit -m "test: 병렬화 + 학생 시험지 모드 통합 확인"
```
