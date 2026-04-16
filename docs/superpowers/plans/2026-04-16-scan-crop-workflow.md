# 스캔 크롭 워크플로우 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 스캔탭을 AI bbox 감지 + 사용자 크롭 수정 + 문제별 처리 워크플로우로 완전히 교체한다.

**Architecture:** 백엔드에 `/api/scan-detect`(PDF→이미지+Gemini bbox 감지)와 `/api/scan-crop-process`(SSE 스트리밍, bbox 크롭→Claude 처리) 2개 엔드포인트를 추가한다. 프론트엔드는 6단계 상태 머신(`upload→detecting→editing→selecting→processing→done`)으로 TabScan.jsx를 재작성하며, CropEditor.jsx(bbox 편집 UI)와 ScanResultCard.jsx(아코디언 결과 카드)를 신규 생성한다.

**Tech Stack:** FastAPI SSE(StreamingResponse), pymupdf(PDF→PNG), Pillow(이미지 크롭), Gemini API(bbox 감지), React useState/useRef(bbox 드래그 편집)

---

## 파일 구조

| 파일 | 작업 |
|------|------|
| `backend/requirements.txt` | pymupdf, Pillow 추가 |
| `backend/Dockerfile` | libgl1 시스템 패키지 추가 (Pillow 의존) |
| `backend/services/gemini_service.py` | `detect_problem_bboxes()` 추가 |
| `backend/main.py` | `crop_image()` 헬퍼, `ScanCropRequest` 모델, `/api/scan-detect`, `/api/scan-crop-process` 엔드포인트 추가 |
| `frontend/src/components/CropEditor.jsx` | 신규 생성 |
| `frontend/src/components/ScanResultCard.jsx` | 신규 생성 |
| `frontend/src/components/TabScan.jsx` | 전체 재작성 |

---

## Task 1: 백엔드 의존성 추가

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/Dockerfile`

- [ ] **Step 1: requirements.txt에 pymupdf, Pillow 추가**

`backend/requirements.txt`를 아래로 교체:
```
fastapi>=0.115.0
uvicorn>=0.30.6
python-multipart>=0.0.9
anthropic>=0.40.0
python-dotenv>=1.0.1
pymupdf>=1.24.0
Pillow>=10.0.0
```

- [ ] **Step 2: Dockerfile에 libgl1 추가**

`backend/Dockerfile`의 apt-get 라인을 아래로 교체:
```dockerfile
RUN apt-get update && \
    apt-get install -y --no-install-recommends fonts-nanum fontconfig libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/* && \
    fc-cache -fv
```

- [ ] **Step 3: 커밋**

```bash
git add backend/requirements.txt backend/Dockerfile
git commit -m "chore: add pymupdf and Pillow dependencies"
```

---

## Task 2: Gemini bbox 감지 함수

**Files:**
- Modify: `backend/services/gemini_service.py`

- [ ] **Step 1: `detect_problem_bboxes()` 함수를 파일 끝에 추가**

```python
def detect_problem_bboxes(image_base64: str, media_type: str) -> list:
    """수학 문제지 이미지에서 각 문제 영역의 bounding box를 비율 좌표로 반환.

    Returns:
        list: [{"x": 0.05, "y": 0.03, "w": 0.90, "h": 0.18}, ...]
              좌표는 이미지 크기 대비 비율값(0.0 ~ 1.0)
              x, y는 박스 왼쪽 상단 모서리
    """
    prompt = """이 수학 문제지 이미지에서 각 문제의 영역을 감지하세요.
반드시 아래 JSON 배열 형식으로만 응답하세요.

[
  {"x": 0.05, "y": 0.03, "w": 0.90, "h": 0.18},
  {"x": 0.05, "y": 0.24, "w": 0.90, "h": 0.22}
]

규칙:
- 좌표는 이미지 전체 크기 대비 비율값(0.0 ~ 1.0)
- x, y는 박스의 왼쪽 상단 모서리 위치
- w는 박스 너비, h는 박스 높이
- 문제 번호, 지문, 조건, 보기를 모두 포함하는 넉넉한 영역으로 잡기
- 문제가 없으면 빈 배열 [] 반환
- JSON 배열만 출력, 다른 텍스트 없이"""

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": media_type, "data": image_base64}},
                {"text": prompt},
            ]
        }]
    }

    result = _call_gemini(GEMINI_MODEL_ANALYZE, payload)
    text = result["candidates"][0]["content"]["parts"][0]["text"]

    try:
        json_match = text
        if "```" in text:
            import re
            m = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
            if m:
                json_match = m.group(1)
        bboxes = json.loads(json_match)
        if not isinstance(bboxes, list):
            return []
        return bboxes
    except (json.JSONDecodeError, KeyError):
        logger.warning(f"bbox 감지 JSON 파싱 실패: {text[:200]}")
        return []
```

- [ ] **Step 2: 커밋**

```bash
git add backend/services/gemini_service.py
git commit -m "feat: add detect_problem_bboxes() to gemini_service"
```

---

## Task 3: `/api/scan-detect` 엔드포인트

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: 파일 상단 import에 추가**

`backend/main.py` 상단의 import 블록에 아래 두 줄 추가:
```python
import fitz  # pymupdf
from PIL import Image
```

그리고 gemini_service import 라인을 아래로 교체:
```python
from services.gemini_service import (
    analyze_graph, recognize_handwriting,
    ocr_scan_general, ocr_scan_student_paper,
    detect_problem_bboxes,
)
```

- [ ] **Step 2: `crop_image()` 헬퍼 함수 추가**

`_cleanup_store()` 함수 바로 위에 추가:
```python
def _pdf_to_images(pdf_bytes: bytes) -> list:
    """PDF를 페이지별 PNG base64 이미지 리스트로 변환.
    Returns: [{"image_base64": str, "media_type": "image/png"}, ...]
    """
    import io as _io
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        png_bytes = pix.tobytes("png")
        b64 = base64.b64encode(png_bytes).decode()
        pages.append({"image_base64": b64, "media_type": "image/png"})
    doc.close()
    return pages


def _crop_image(image_base64: str, media_type: str, x: float, y: float, w: float, h: float) -> tuple:
    """bbox 비율 좌표로 이미지를 크롭하여 (base64, media_type) 반환."""
    import io as _io
    img_bytes = base64.b64decode(image_base64)
    img = Image.open(_io.BytesIO(img_bytes))
    iw, ih = img.size
    left = int(x * iw)
    top = int(y * ih)
    right = int((x + w) * iw)
    bottom = int((y + h) * ih)
    # 경계 클리핑
    left, top = max(0, left), max(0, top)
    right, bottom = min(iw, right), min(ih, bottom)
    cropped = img.crop((left, top, right, bottom))
    buf = _io.BytesIO()
    cropped.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode(), "image/png"
```

- [ ] **Step 3: `/api/scan-detect` 엔드포인트 추가**

`/api/scan-process` 엔드포인트 바로 위에 추가:
```python
@app.post("/api/scan-detect")
async def scan_detect(
    file: UploadFile = File(...),
):
    """이미지 또는 PDF → 페이지별 이미지 변환 + Gemini bbox 감지."""
    logger.info(f"스캔 감지 시작: {file.filename}, {file.content_type}")
    data = await file.read()
    content_type = file.content_type or "image/jpeg"

    # PDF → 페이지 이미지 변환
    if content_type == "application/pdf":
        page_images = _pdf_to_images(data)
    else:
        b64 = base64.b64encode(data).decode()
        page_images = [{"image_base64": b64, "media_type": content_type}]

    # 각 페이지에서 bbox 감지
    pages = []
    for i, pg in enumerate(page_images):
        raw_bboxes = detect_problem_bboxes(pg["image_base64"], pg["media_type"])
        bboxes = [
            {
                "id": f"p{i}_b{j}",
                "x": bb.get("x", 0),
                "y": bb.get("y", 0),
                "w": bb.get("w", 0),
                "h": bb.get("h", 0),
                "label": f"문제 {len(pages) + j + 1}",
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
```

- [ ] **Step 4: 커밋**

```bash
git add backend/main.py
git commit -m "feat: add /api/scan-detect endpoint with PDF-to-image and bbox detection"
```

---

## Task 4: `/api/scan-crop-process` SSE 엔드포인트

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: `ScanCropRequest` Pydantic 모델 추가**

기존 `ScanVariantRequest` 클래스 바로 아래에 추가:
```python
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
    bboxes: list = []


class ScanCropRequest(BaseModel):
    pages: List[PageItem]
    confirmed_bboxes: List[BboxItem]
    output_mode: str = "type_only"
    variant_count: int = 1
    model: str = "sonnet"
    grade: str = "none"
```

- [ ] **Step 2: StreamingResponse import 확인**

`backend/main.py` 상단에 아래가 있는지 확인, 없으면 추가:
```python
import json as json_module
from fastapi.responses import StreamingResponse
```

- [ ] **Step 3: `/api/scan-crop-process` 엔드포인트 추가**

`/api/scan-generate-variants` 엔드포인트 바로 뒤에 추가:
```python
@app.post("/api/scan-crop-process")
async def scan_crop_process(req: ScanCropRequest):
    """확정된 bbox로 문제 하나씩 처리, SSE 스트리밍 응답."""

    async def event_stream():
        selected = [b for b in req.confirmed_bboxes if b.selected]
        page_map = {p.page_index: p for p in req.pages}
        all_results = []

        for i, bbox in enumerate(selected):
            problem_id = bbox.id
            label = bbox.label or f"문제 {i + 1}"
            logger.info(f"처리 시작: {label} ({problem_id})")

            yield f"data: {json_module.dumps({'type': 'progress', 'problem_id': problem_id, 'label': label, 'status': 'processing'}, ensure_ascii=False)}\n\n"

            try:
                page = page_map.get(bbox.page_index)
                if not page:
                    raise ValueError(f"페이지 {bbox.page_index}를 찾을 수 없습니다.")

                cropped_b64, cropped_type = _crop_image(
                    page.image_base64, page.media_type,
                    bbox.x, bbox.y, bbox.w, bbox.h
                )

                ocr_data = ocr_scan_general(cropped_b64, cropped_type)
                result = await claude_service.process_scan(
                    ocr_data, "general", req.variant_count,
                    req.model, req.grade, req.output_mode
                )

                entry = {
                    "problem_id": problem_id,
                    "label": label,
                    "result": result["text"],
                    "graphs": result.get("graphs", []),
                    "ocr_data": result["ocr_data"],
                    "output_mode": req.output_mode,
                    "usage": result["usage"],
                }
                all_results.append(entry)
                logger.info(f"처리 완료: {label}")

                yield f"data: {json_module.dumps({'type': 'result', **entry}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"처리 에러 ({label}): {e}")
                yield f"data: {json_module.dumps({'type': 'error', 'problem_id': problem_id, 'label': label, 'error': str(e)}, ensure_ascii=False)}\n\n"

        # 전체 완료 후 히스토리 저장
        if all_results:
            history_service.save_history({
                "type": "scan_crop",
                "output_mode": req.output_mode,
                "model": req.model,
                "results": all_results,
                "total": len(all_results),
            })

        yield f"data: {json_module.dumps({'type': 'done', 'total': len(selected)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 4: 커밋**

```bash
git add backend/main.py
git commit -m "feat: add /api/scan-crop-process SSE endpoint"
```

---

## Task 5: CropEditor.jsx 신규 생성

**Files:**
- Create: `frontend/src/components/CropEditor.jsx`

- [ ] **Step 1: CropEditor.jsx 파일 생성**

`frontend/src/components/CropEditor.jsx`를 아래 내용으로 생성:

```jsx
import { useState, useRef, useCallback, useEffect } from 'react'

// 다크/브라이트 테마 색상
// 브라이트(B3): bg #F4F5F7, sidebar #E8EAEF, accent #0EA5E9
// 다크(D3): bg #22252E, sidebar #2A2D38, accent #8B5CF6

const HANDLE_SIZE = 9  // px, bbox 핸들 크기

/**
 * CropEditor
 * props:
 *   pages: [{page_index, image_base64, media_type, bboxes: [{id,x,y,w,h,label}]}]
 *   onConfirm: (confirmedBboxes) => void
 *     confirmedBboxes: [{id, page_index, x, y, w, h, label, selected}]
 */
export default function CropEditor({ pages, onConfirm }) {
  const [currentPage, setCurrentPage] = useState(0)
  const [tool, setTool] = useState('select')  // 'select' | 'add'
  const [selectedId, setSelectedId] = useState(null)

  // 전체 bbox 상태: {[id]: {id, page_index, x, y, w, h, label, selected}}
  const [bboxMap, setBboxMap] = useState(() => {
    const map = {}
    pages.forEach(pg => {
      pg.bboxes.forEach(bb => {
        map[bb.id] = { ...bb, page_index: pg.page_index, selected: true }
      })
    })
    return map
  })

  const imgRef = useRef(null)
  const containerRef = useRef(null)
  const dragState = useRef(null)  // { type, id, startX, startY, origBbox, isNewBox, newId }

  const page = pages[currentPage]
  const pageItems = Object.values(bboxMap).filter(b => b.page_index === currentPage)
  const allItems = Object.values(bboxMap)

  // 렌더링 크기 → 비율 변환 헬퍼
  const toRatio = useCallback((px, py) => {
    const rect = imgRef.current?.getBoundingClientRect()
    if (!rect) return { rx: 0, ry: 0 }
    return { rx: (px - rect.left) / rect.width, ry: (py - rect.top) / rect.height }
  }, [])

  // 마우스 다운: 박스 선택/이동 또는 새 박스 그리기
  const onMouseDown = useCallback((e, bboxId = null, handleDir = null) => {
    e.preventDefault()
    e.stopPropagation()
    const { rx, ry } = toRatio(e.clientX, e.clientY)

    if (tool === 'add' && !bboxId) {
      // 새 박스 그리기 시작
      const newId = `p${currentPage}_b${Date.now()}`
      dragState.current = { type: 'create', newId, startX: rx, startY: ry }
      setBboxMap(prev => ({
        ...prev,
        [newId]: { id: newId, page_index: currentPage, x: rx, y: ry, w: 0, h: 0, label: `문제 ${allItems.length + 1}`, selected: true }
      }))
      setSelectedId(newId)
      return
    }

    if (bboxId) {
      setSelectedId(bboxId)
      const orig = bboxMap[bboxId]
      if (handleDir) {
        dragState.current = { type: 'resize', id: bboxId, handleDir, startX: rx, startY: ry, origBbox: { ...orig } }
      } else {
        dragState.current = { type: 'move', id: bboxId, startX: rx, startY: ry, origBbox: { ...orig } }
      }
    } else {
      setSelectedId(null)
    }
  }, [tool, currentPage, bboxMap, allItems.length, toRatio])

  const onMouseMove = useCallback((e) => {
    if (!dragState.current) return
    const { rx, ry } = toRatio(e.clientX, e.clientY)
    const ds = dragState.current

    if (ds.type === 'move') {
      const dx = rx - ds.startX, dy = ry - ds.startY
      setBboxMap(prev => ({
        ...prev,
        [ds.id]: {
          ...prev[ds.id],
          x: Math.max(0, Math.min(1 - ds.origBbox.w, ds.origBbox.x + dx)),
          y: Math.max(0, Math.min(1 - ds.origBbox.h, ds.origBbox.y + dy)),
        }
      }))
    } else if (ds.type === 'resize') {
      const ob = ds.origBbox
      let { x, y, w, h } = ob
      const dx = rx - ds.startX, dy = ry - ds.startY
      const dir = ds.handleDir
      if (dir.includes('e')) w = Math.max(0.02, ob.w + dx)
      if (dir.includes('s')) h = Math.max(0.02, ob.h + dy)
      if (dir.includes('w')) { x = Math.min(ob.x + ob.w - 0.02, ob.x + dx); w = ob.w - dx }
      if (dir.includes('n')) { y = Math.min(ob.y + ob.h - 0.02, ob.y + dy); h = ob.h - dy }
      setBboxMap(prev => ({ ...prev, [ds.id]: { ...prev[ds.id], x: Math.max(0, x), y: Math.max(0, y), w: Math.min(1 - x, Math.max(0.02, w)), h: Math.min(1 - y, Math.max(0.02, h)) } }))
    } else if (ds.type === 'create') {
      const x = Math.min(ds.startX, rx), y = Math.min(ds.startY, ry)
      const w = Math.abs(rx - ds.startX), h = Math.abs(ry - ds.startY)
      setBboxMap(prev => ({ ...prev, [ds.newId]: { ...prev[ds.newId], x, y, w, h } }))
    }
  }, [toRatio])

  const onMouseUp = useCallback(() => {
    const ds = dragState.current
    if (ds?.type === 'create') {
      // 너무 작으면 제거
      const bb = bboxMap[ds.newId]
      if (bb && (bb.w < 0.02 || bb.h < 0.02)) {
        setBboxMap(prev => { const next = { ...prev }; delete next[ds.newId]; return next })
        setSelectedId(null)
      }
    }
    dragState.current = null
  }, [bboxMap])

  // Delete 키로 선택된 박스 삭제
  useEffect(() => {
    const onKey = (e) => {
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedId) {
        setBboxMap(prev => { const next = { ...prev }; delete next[selectedId]; return next })
        setSelectedId(null)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selectedId])

  const deleteSelected = () => {
    if (!selectedId) return
    setBboxMap(prev => { const next = { ...prev }; delete next[selectedId]; return next })
    setSelectedId(null)
  }

  const toggleSelection = (id) => {
    setBboxMap(prev => ({ ...prev, [id]: { ...prev[id], selected: !prev[id].selected } }))
  }

  const selectAll = (v) => {
    setBboxMap(prev => Object.fromEntries(Object.entries(prev).map(([k, b]) => [k, { ...b, selected: v }])))
  }

  const handleConfirm = () => {
    onConfirm(Object.values(bboxMap))
  }

  const goToPage = (idx) => {
    const clamped = Math.max(0, Math.min(pages.length - 1, idx))
    setCurrentPage(clamped)
    setSelectedId(null)
  }

  const isDark = document.documentElement.classList.contains('dark')
  const colors = isDark
    ? { bg: '#22252E', toolbar: '#2A2D38', border: '#353844', page: '#1E2028', sidebar: '#2A2D38', accent: '#8B5CF6', text: '#E2E4F0', muted: '#5A5E70' }
    : { bg: '#F4F5F7', toolbar: '#E8EAEF', border: '#DDE1E9', page: '#FFFFFF', sidebar: '#E8EAEF', accent: '#0EA5E9', text: '#374151', muted: '#9AA0B0' }

  return (
    <div style={{ border: `1px solid ${colors.border}`, borderRadius: 12, overflow: 'hidden', background: colors.bg }}>
      {/* 툴바 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 16px', background: colors.toolbar, borderBottom: `1px solid ${colors.border}`, flexWrap: 'wrap' }}>
        {/* 도구 버튼 */}
        <div style={{ display: 'flex', gap: 6 }}>
          {[
            { key: 'select', label: '🖱 선택/이동' },
            { key: 'add', label: '➕ 박스 추가' },
          ].map(t => (
            <button key={t.key} onClick={() => setTool(t.key)}
              style={{ padding: '5px 12px', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer', border: `1px solid ${tool === t.key ? colors.accent : colors.border}`, background: tool === t.key ? `${colors.accent}22` : colors.toolbar, color: tool === t.key ? colors.accent : colors.muted }}>
              {t.label}
            </button>
          ))}
          <button onClick={deleteSelected} disabled={!selectedId}
            style={{ padding: '5px 12px', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: selectedId ? 'pointer' : 'not-allowed', border: '1px solid #f87171', background: 'transparent', color: '#f87171', opacity: selectedId ? 1 : 0.4 }}>
            🗑 삭제
          </button>
        </div>
        <div style={{ width: 1, height: 22, background: colors.border, margin: '0 4px' }} />
        {/* 페이지 네비 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: colors.muted }}>
          {[
            { label: '|◀ 처음', action: () => goToPage(0) },
            { label: '◀ 이전', action: () => goToPage(currentPage - 1) },
          ].map(b => (
            <button key={b.label} onClick={b.action}
              style={{ padding: '4px 10px', borderRadius: 5, fontSize: 11, fontWeight: 600, cursor: 'pointer', border: `1px solid ${colors.border}`, background: colors.toolbar, color: colors.muted }}>
              {b.label}
            </button>
          ))}
          <input
            type="number" min={1} max={pages.length}
            value={currentPage + 1}
            onChange={e => goToPage(Number(e.target.value) - 1)}
            style={{ width: 44, textAlign: 'center', background: colors.bg, border: `1px solid ${colors.border}`, borderRadius: 5, color: colors.text, fontSize: 12, padding: '3px 4px' }}
          />
          <span>/ {pages.length}</span>
          {[
            { label: '다음 ▶', action: () => goToPage(currentPage + 1) },
            { label: '마지막 ▶|', action: () => goToPage(pages.length - 1) },
          ].map(b => (
            <button key={b.label} onClick={b.action}
              style={{ padding: '4px 10px', borderRadius: 5, fontSize: 11, fontWeight: 600, cursor: 'pointer', border: `1px solid ${colors.border}`, background: colors.toolbar, color: colors.muted }}>
              {b.label}
            </button>
          ))}
        </div>
      </div>

      {/* 본문 */}
      <div style={{ display: 'flex', height: 620 }}>
        {/* 페이지 뷰어 */}
        <div ref={containerRef} style={{ flex: 1.3, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px 12px', background: isDark ? '#080A12' : '#ECEEF2' }}
          onMouseMove={onMouseMove} onMouseUp={onMouseUp} onMouseLeave={onMouseUp}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <button onClick={() => goToPage(currentPage - 1)} disabled={currentPage === 0}
              style={{ width: 38, height: 38, borderRadius: '50%', border: `1px solid ${colors.border}`, background: colors.sidebar, color: colors.muted, cursor: currentPage === 0 ? 'not-allowed' : 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: currentPage === 0 ? 0.4 : 1 }}>
              ◀
            </button>
            <div>
              {/* 페이지 이미지 + bbox 오버레이 */}
              <div style={{ position: 'relative', display: 'inline-block', cursor: tool === 'add' ? 'crosshair' : 'default' }}
                onMouseDown={(e) => onMouseDown(e)}>
                <img ref={imgRef}
                  src={`data:${page.media_type};base64,${page.image_base64}`}
                  alt={`페이지 ${currentPage + 1}`}
                  style={{ display: 'block', maxWidth: 420, maxHeight: 594, width: 'auto', height: 'auto', borderRadius: 6, border: `1px solid ${colors.border}`, userSelect: 'none', pointerEvents: 'none' }}
                  draggable={false}
                />
                {/* bbox 오버레이 */}
                {pageItems.map(bb => {
                  const isSel = bb.id === selectedId
                  return (
                    <div key={bb.id}
                      onMouseDown={(e) => onMouseDown(e, bb.id)}
                      style={{ position: 'absolute', left: `${bb.x * 100}%`, top: `${bb.y * 100}%`, width: `${bb.w * 100}%`, height: `${bb.h * 100}%`, border: `2px solid ${isSel ? '#f59e0b' : colors.accent}`, borderRadius: 3, background: isSel ? 'rgba(245,158,11,0.08)' : `${colors.accent}14`, cursor: tool === 'select' ? 'move' : 'default', boxSizing: 'border-box' }}>
                      {/* 라벨 */}
                      <div style={{ position: 'absolute', top: -20, left: 0, background: isSel ? '#f59e0b' : colors.accent, color: isSel ? '#0D0F1A' : 'white', fontSize: 10, padding: '1px 7px', borderRadius: 4, whiteSpace: 'nowrap' }}>
                        {bb.label}
                      </div>
                      {/* 리사이즈 핸들 (선택됐을 때만) */}
                      {isSel && [
                        { dir: 'nw', style: { top: -5, left: -5, cursor: 'nw-resize' } },
                        { dir: 'ne', style: { top: -5, right: -5, cursor: 'ne-resize' } },
                        { dir: 'sw', style: { bottom: -5, left: -5, cursor: 'sw-resize' } },
                        { dir: 'se', style: { bottom: -5, right: -5, cursor: 'se-resize' } },
                        { dir: 'n', style: { top: -5, left: 'calc(50% - 4px)', cursor: 'n-resize' } },
                        { dir: 's', style: { bottom: -5, left: 'calc(50% - 4px)', cursor: 's-resize' } },
                        { dir: 'w', style: { left: -5, top: 'calc(50% - 4px)', cursor: 'w-resize' } },
                        { dir: 'e', style: { right: -5, top: 'calc(50% - 4px)', cursor: 'e-resize' } },
                      ].map(h => (
                        <div key={h.dir} onMouseDown={(e) => { e.stopPropagation(); onMouseDown(e, bb.id, h.dir) }}
                          style={{ position: 'absolute', width: HANDLE_SIZE, height: HANDLE_SIZE, background: 'white', border: `2px solid #f59e0b`, borderRadius: 2, ...h.style }} />
                      ))}
                    </div>
                  )
                })}
              </div>
              <div style={{ textAlign: 'center', fontSize: 12, color: colors.muted, marginTop: 10 }}>
                {currentPage + 1} / {pages.length} 페이지
              </div>
            </div>
            <button onClick={() => goToPage(currentPage + 1)} disabled={currentPage === pages.length - 1}
              style={{ width: 38, height: 38, borderRadius: '50%', border: `1px solid ${colors.border}`, background: colors.sidebar, color: colors.muted, cursor: currentPage === pages.length - 1 ? 'not-allowed' : 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: currentPage === pages.length - 1 ? 0.4 : 1 }}>
              ▶
            </button>
          </div>
        </div>

        {/* 사이드바 */}
        <div style={{ flex: 1, borderLeft: `1px solid ${colors.border}`, display: 'flex', flexDirection: 'column', background: colors.bg }}>
          <div style={{ padding: '12px 16px', background: colors.sidebar, borderBottom: `1px solid ${colors.border}`, fontSize: 12, fontWeight: 700, color: colors.muted, textTransform: 'uppercase', letterSpacing: '0.05em', display: 'flex', alignItems: 'center' }}>
            감지 문제 목록
            <span style={{ marginLeft: 'auto', background: `${colors.accent}22`, color: colors.accent, padding: '2px 9px', borderRadius: 20, fontSize: 11, fontWeight: 700 }}>
              {allItems.length}개
            </span>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
            {/* 현재 페이지 문제 */}
            {pageItems.length > 0 && (
              <>
                <div style={{ fontSize: 10, fontWeight: 700, color: colors.accent, marginBottom: 4, paddingLeft: 4 }}>● 현재 페이지</div>
                {pageItems.map(bb => (
                  <div key={bb.id} onClick={() => setSelectedId(bb.id)}
                    style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 7, marginBottom: 4, cursor: 'pointer', border: `1px solid ${bb.id === selectedId ? '#f59e0b44' : 'transparent'}`, background: bb.id === selectedId ? '#f59e0b11' : 'transparent', fontSize: 12, color: colors.text }}>
                    <input type="checkbox" checked={bb.selected} onChange={() => toggleSelection(bb.id)} onClick={e => e.stopPropagation()} />
                    <div style={{ width: 10, height: 10, borderRadius: 3, background: colors.accent, flexShrink: 0 }} />
                    <span>{bb.label}</span>
                    <span style={{ marginLeft: 'auto', fontSize: 10, color: colors.muted, background: colors.sidebar, padding: '1px 6px', borderRadius: 10 }}>{currentPage + 1}p</span>
                  </div>
                ))}
              </>
            )}
            {/* 다른 페이지 문제 */}
            {allItems.filter(b => b.page_index !== currentPage).length > 0 && (
              <>
                <div style={{ fontSize: 10, fontWeight: 700, color: colors.muted, margin: '12px 0 4px', paddingLeft: 4 }}>다른 페이지</div>
                {allItems.filter(b => b.page_index !== currentPage).map(bb => (
                  <div key={bb.id} onClick={() => { goToPage(bb.page_index); setSelectedId(bb.id) }}
                    style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 7, marginBottom: 4, cursor: 'pointer', border: `1px solid ${colors.border}`, fontSize: 12, color: colors.muted }}>
                    <input type="checkbox" checked={bb.selected} onChange={() => toggleSelection(bb.id)} onClick={e => e.stopPropagation()} />
                    <div style={{ width: 10, height: 10, borderRadius: 3, background: colors.muted, flexShrink: 0 }} />
                    <span>{bb.label}</span>
                    <span style={{ marginLeft: 'auto', fontSize: 10, color: colors.muted, background: colors.sidebar, padding: '1px 6px', borderRadius: 10 }}>{bb.page_index + 1}p</span>
                  </div>
                ))}
              </>
            )}
            {allItems.length === 0 && (
              <div style={{ textAlign: 'center', color: colors.muted, fontSize: 12, paddingTop: 20 }}>
                <div style={{ fontSize: 24, marginBottom: 8 }}>🔍</div>
                <p>문제를 감지하지 못했습니다.</p>
                <p style={{ marginTop: 4 }}>"박스 추가" 도구로 직접 그려주세요.</p>
              </div>
            )}
            {/* 전체 선택/해제 */}
            <div style={{ display: 'flex', gap: 6, marginTop: 12, paddingTop: 12, borderTop: `1px solid ${colors.border}` }}>
              <button onClick={() => selectAll(true)} style={{ flex: 1, padding: '4px 0', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer', border: `1px solid ${colors.border}`, background: colors.sidebar, color: colors.muted }}>전체 선택</button>
              <button onClick={() => selectAll(false)} style={{ flex: 1, padding: '4px 0', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer', border: `1px solid ${colors.border}`, background: colors.sidebar, color: colors.muted }}>전체 해제</button>
            </div>
          </div>
          <div style={{ padding: 12, borderTop: `1px solid ${colors.border}` }}>
            <div style={{ fontSize: 11, color: colors.muted, marginBottom: 8 }}>
              {allItems.filter(b => b.selected).length}개 선택됨
            </div>
            <button onClick={handleConfirm} disabled={allItems.filter(b => b.selected).length === 0}
              style={{ width: '100%', padding: '10px 0', borderRadius: 8, fontWeight: 600, fontSize: 13, color: 'white', background: `linear-gradient(to right, ${colors.accent}, ${isDark ? '#6D28D9' : '#0284C7'})`, border: 'none', cursor: allItems.filter(b => b.selected).length === 0 ? 'not-allowed' : 'pointer', opacity: allItems.filter(b => b.selected).length === 0 ? 0.4 : 1 }}>
              크롭 확정 → 처리 방식 선택
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/src/components/CropEditor.jsx
git commit -m "feat: add CropEditor component with bbox drag editing"
```

---

## Task 6: ScanResultCard.jsx 신규 생성

**Files:**
- Create: `frontend/src/components/ScanResultCard.jsx`

- [ ] **Step 1: ScanResultCard.jsx 파일 생성**

```jsx
import { useState } from 'react'
import SolutionDisplay from './SolutionDisplay'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001'

/**
 * ScanResultCard
 * props:
 *   problemId: string
 *   label: string
 *   status: 'pending' | 'processing' | 'done' | 'error'
 *   result: string | null
 *   graphs: array
 *   ocrData: object | null
 *   outputMode: string
 *   error: string | null
 *   model: string
 *   grade: string
 */
export default function ScanResultCard({ problemId, label, status, result, graphs, ocrData, outputMode, error, model, grade }) {
  const [open, setOpen] = useState(true)
  const [extraMode, setExtraMode] = useState(null)  // null | 'solution' | 'variant'
  const [extraResult, setExtraResult] = useState(null)
  const [extraGraphs, setExtraGraphs] = useState([])
  const [extraLoading, setExtraLoading] = useState(false)
  const [extraError, setExtraError] = useState(null)

  const handleExtra = async (mode) => {
    if (!ocrData) return
    setExtraMode(mode)
    setExtraLoading(true)
    setExtraError(null)
    try {
      const res = await fetch(`${API}/api/scan-generate-variants`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ocr_data: ocrData,
          scan_mode: 'general',
          variant_count: 1,
          model,
          grade,
          output_mode: mode === 'solution' ? 'type_with_solution' : 'variant',
        }),
      })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '실패') }
      const data = await res.json()
      setExtraResult(data.result)
      setExtraGraphs(data.graphs || [])
    } catch (e) {
      setExtraError(e.message)
    } finally {
      setExtraLoading(false)
    }
  }

  const statusBadge = {
    pending: { label: '대기 중', color: '#6B7280', bg: '#6B728022' },
    processing: { label: '처리 중...', color: '#F59E0B', bg: '#F59E0B22' },
    done: { label: '완료', color: '#22C55E', bg: '#22C55E22' },
    error: { label: '오류', color: '#EF4444', bg: '#EF444422' },
  }[status] || { label: status, color: '#6B7280', bg: '#6B728022' }

  return (
    <div className="rounded-xl border border-gray-200 dark:border-[#353844] overflow-hidden">
      {/* 헤더 */}
      <div
        onClick={() => status === 'done' && setOpen(o => !o)}
        className="flex items-center gap-3 px-4 py-3 bg-gray-50 dark:bg-[#2A2D38] cursor-pointer select-none"
      >
        <span className="font-semibold text-sm text-gray-800 dark:text-[#E2E4F0]">{label}</span>
        <span style={{ background: statusBadge.bg, color: statusBadge.color }} className="text-xs font-semibold px-2 py-0.5 rounded-full">
          {statusBadge.label}
          {status === 'processing' && (
            <svg className="inline animate-spin h-3 w-3 ml-1" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
          )}
        </span>
        {status === 'done' && outputMode === 'type_only' && !extraResult && (
          <div className="ml-auto flex gap-2">
            <button
              onClick={e => { e.stopPropagation(); handleExtra('solution') }}
              disabled={extraLoading}
              className="text-xs px-3 py-1 rounded-lg border border-gray-200 dark:border-[#353844] text-gray-600 dark:text-[#A0A4B8] hover:bg-gray-100 dark:hover:bg-[#353844] disabled:opacity-40"
            >
              {extraLoading && extraMode === 'solution' ? '생성 중...' : '+ 해설 추가'}
            </button>
            <button
              onClick={e => { e.stopPropagation(); handleExtra('variant') }}
              disabled={extraLoading}
              className="text-xs px-3 py-1 rounded-lg border border-gray-200 dark:border-[#353844] text-gray-600 dark:text-[#A0A4B8] hover:bg-gray-100 dark:hover:bg-[#353844] disabled:opacity-40"
            >
              {extraLoading && extraMode === 'variant' ? '생성 중...' : '+ 유사문항'}
            </button>
          </div>
        )}
        {status === 'done' && (
          <svg className={`w-4 h-4 transition-transform text-gray-400 dark:text-[#5A5E70] ${open ? '' : 'rotate-180'} ${status === 'done' && outputMode === 'type_only' ? '' : 'ml-auto'}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </div>

      {/* 본문 */}
      {open && status === 'done' && result && (
        <div className="p-4 bg-white dark:bg-[#22252E]">
          <SolutionDisplay solution={result} graphs={graphs} title={label} />
          {extraError && (
            <div className="mt-3 p-2 text-xs text-red-500 bg-red-50 dark:bg-red-500/10 rounded-lg">{extraError}</div>
          )}
          {extraResult && (
            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-[#353844]">
              <SolutionDisplay solution={extraResult} graphs={extraGraphs} title={extraMode === 'solution' ? '해설' : '유사문항'} />
            </div>
          )}
        </div>
      )}
      {status === 'error' && error && (
        <div className="px-4 py-3 text-sm text-red-500 dark:text-red-400 bg-red-50 dark:bg-red-500/5">
          {error}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/src/components/ScanResultCard.jsx
git commit -m "feat: add ScanResultCard accordion component"
```

---

## Task 7: TabScan.jsx 전체 재작성

**Files:**
- Modify: `frontend/src/components/TabScan.jsx`

- [ ] **Step 1: TabScan.jsx 전체를 아래 코드로 교체**

```jsx
import { useState, useCallback } from 'react'
import CropEditor from './CropEditor'
import ScanResultCard from './ScanResultCard'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001'

const OUTPUT_MODES = [
  { value: 'type_only', label: '타이핑만', desc: '원본 문제를 HWP 형식으로' },
  { value: 'type_with_solution', label: '타이핑+해설', desc: '문제 타이핑 + 해설 생성' },
  { value: 'variant', label: '유사문항 생성', desc: 'OCR + 유사문항까지' },
]

export default function TabScan({ grade, model }) {
  const [step, setStep] = useState('upload')  // upload | detecting | editing | selecting | processing | done
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [detectData, setDetectData] = useState(null)   // /api/scan-detect 응답
  const [confirmedBboxes, setConfirmedBboxes] = useState([])
  const [outputMode, setOutputMode] = useState('type_only')
  const [variantCount, setVariantCount] = useState(1)
  const [cards, setCards] = useState([])               // [{problemId, label, status, result, graphs, ocrData, outputMode, error}]
  const [error, setError] = useState(null)
  const [hwpxUrl, setHwpxUrl] = useState(null)

  const handleFile = useCallback((f) => {
    if (!f) return
    if (!f.type.startsWith('image/') && f.type !== 'application/pdf') return
    setFile(f)
    setStep('upload')
    setDetectData(null)
    setCards([])
    setError(null)
    setHwpxUrl(null)
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault(); setDragging(false)
    handleFile(e.dataTransfer.files[0])
  }, [handleFile])

  const handlePaste = useCallback((e) => {
    for (const item of e.clipboardData?.items || []) {
      if (item.type.startsWith('image/')) { handleFile(item.getAsFile()); break }
    }
  }, [handleFile])

  // 1단계 → 2단계: 파일 업로드 후 AI 감지
  const handleDetect = async () => {
    if (!file) return
    setStep('detecting')
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch(`${API}/api/scan-detect`, { method: 'POST', body: fd })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '감지 실패') }
      const data = await res.json()
      setDetectData(data)
      setStep('editing')
    } catch (e) {
      setError(e.message)
      setStep('upload')
    }
  }

  // 2단계 → 3단계: 크롭 확정
  const handleConfirm = (confirmedBboxes) => {
    setConfirmedBboxes(confirmedBboxes)
    setStep('selecting')
  }

  // 3단계 → 4단계: 처리 시작 (SSE)
  const handleProcess = async () => {
    const selected = confirmedBboxes.filter(b => b.selected)
    if (selected.length === 0) return

    // 초기 카드 생성 (pending)
    setCards(selected.map(bb => ({
      problemId: bb.id, label: bb.label, status: 'pending',
      result: null, graphs: [], ocrData: null, outputMode, error: null,
    })))
    setStep('processing')
    setError(null)

    try {
      const res = await fetch(`${API}/api/scan-crop-process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pages: detectData.pages,
          confirmed_bboxes: confirmedBboxes,
          output_mode: outputMode,
          variant_count: variantCount,
          model,
          grade,
        }),
      })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '처리 실패') }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()  // 마지막 불완전한 줄 보류

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'progress') {
              setCards(prev => prev.map(c => c.problemId === event.problem_id ? { ...c, status: 'processing' } : c))
            } else if (event.type === 'result') {
              setCards(prev => prev.map(c => c.problemId === event.problem_id ? {
                ...c, status: 'done', result: event.result, graphs: event.graphs || [],
                ocrData: event.ocr_data, outputMode: event.output_mode,
              } : c))
            } else if (event.type === 'error') {
              setCards(prev => prev.map(c => c.problemId === event.problem_id ? { ...c, status: 'error', error: event.error } : c))
            } else if (event.type === 'done') {
              setStep('done')
            }
          } catch { /* JSON 파싱 실패 무시 */ }
        }
      }
    } catch (e) {
      setError(e.message)
    }
  }

  // 전체 HWPX 다운로드
  const handleHwpxDownload = async () => {
    const doneCards = cards.filter(c => c.status === 'done' && c.result)
    if (doneCards.length === 0) return
    try {
      // 전체 결과를 하나의 텍스트로 합쳐서 HWPX 생성
      const combinedResult = doneCards.map(c => c.result).join('\n\n')
      const res = await fetch(`${API}/api/hwpx-solve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: combinedResult }),
      })
      if (!res.ok) throw new Error('HWPX 생성 실패')
      // TODO: 백엔드에 /api/text-to-hwpx 엔드포인트 필요시 추가
      // 현재는 브라우저에서 텍스트 파일로 다운로드
      const blob = new Blob([combinedResult], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'scan_result.txt'; a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div onPaste={handlePaste} tabIndex={0} className="outline-none space-y-4">

      {/* ── 1단계: 업로드 ── */}
      {(step === 'upload' || step === 'detecting') && (
        <>
          <div className="bg-white dark:bg-[#22252E] rounded-xl border border-gray-200 dark:border-[#353844] p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-700 dark:text-[#E2E4F0] mb-4">스캔 이미지 업로드</h2>
            <div
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => document.getElementById('scan-file-input').click()}
              className={`relative border-2 border-dashed rounded-xl cursor-pointer transition-all ${dragging ? 'border-sky-500 bg-sky-50 dark:bg-sky-500/10' : 'border-gray-300 dark:border-[#353844] hover:border-sky-400 dark:hover:border-violet-500 hover:bg-gray-50 dark:hover:bg-violet-500/5'} ${file ? 'p-2' : 'p-10'}`}
            >
              <input id="scan-file-input" type="file" accept="image/*,application/pdf" className="hidden"
                onChange={e => handleFile(e.target.files[0])} />
              {file ? (
                <div className="flex items-center gap-3 p-3">
                  <div className="text-3xl">{file.type === 'application/pdf' ? '📄' : '🖼'}</div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-700 dark:text-[#E2E4F0]">{file.name}</p>
                    <p className="text-xs text-gray-400 dark:text-[#5A5E70]">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
                  </div>
                  <button onClick={e => { e.stopPropagation(); setFile(null) }}
                    className="bg-red-500 text-white rounded-full w-6 h-6 text-xs flex items-center justify-center hover:bg-red-600">×</button>
                </div>
              ) : (
                <div className="text-center text-gray-400 dark:text-[#5A5E70]">
                  <div className="text-4xl mb-2">📷</div>
                  <p className="text-sm font-medium">클릭하거나 이미지/PDF를 드래그하세요</p>
                  <p className="text-xs mt-1">붙여넣기(Ctrl+V)도 가능합니다 · JPG, PNG, PDF 지원</p>
                </div>
              )}
            </div>
          </div>

          <button onClick={handleDetect} disabled={!file || step === 'detecting'}
            className="w-full py-3 rounded-xl font-semibold text-white bg-gradient-to-r from-sky-500 to-blue-600 dark:from-violet-600 dark:to-purple-700 hover:from-sky-400 hover:to-blue-500 disabled:opacity-40 disabled:cursor-not-allowed shadow-md transition-all">
            {step === 'detecting' ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
                AI가 문제 영역을 감지하는 중...
              </span>
            ) : '✦ 분석 시작'}
          </button>
        </>
      )}

      {/* ── 2단계: 크롭 수정 ── */}
      {step === 'editing' && detectData && (
        <>
          <div className="flex items-center gap-3 mb-2">
            <button onClick={() => setStep('upload')} className="text-sm text-gray-500 dark:text-[#5A5E70] hover:underline">← 다시 업로드</button>
            <h2 className="text-base font-semibold text-gray-700 dark:text-[#E2E4F0]">문제 영역 수정</h2>
          </div>
          <CropEditor pages={detectData.pages} onConfirm={handleConfirm} />
        </>
      )}

      {/* ── 3단계: 출력 방식 선택 ── */}
      {step === 'selecting' && (
        <div className="bg-white dark:bg-[#22252E] rounded-xl border border-gray-200 dark:border-[#353844] p-6 shadow-sm space-y-5">
          <div className="flex items-center gap-3">
            <button onClick={() => setStep('editing')} className="text-sm text-gray-500 dark:text-[#5A5E70] hover:underline">← 크롭 수정</button>
            <h2 className="text-base font-semibold text-gray-700 dark:text-[#E2E4F0]">처리 방식 선택</h2>
          </div>
          <p className="text-sm text-gray-500 dark:text-[#5A5E70]">{confirmedBboxes.filter(b => b.selected).length}개 문제에 일괄 적용됩니다.</p>

          <div className="flex gap-3 flex-wrap">
            {OUTPUT_MODES.map(om => (
              <button key={om.value} onClick={() => setOutputMode(om.value)}
                className={`px-4 py-3 rounded-xl text-sm border transition-colors ${outputMode === om.value ? 'border-sky-500 dark:border-violet-500 bg-sky-50 dark:bg-violet-500/10 text-sky-700 dark:text-violet-300 font-semibold' : 'border-gray-200 dark:border-[#353844] text-gray-600 dark:text-[#5A5E70] hover:bg-gray-50 dark:hover:bg-[#2A2D38]'}`}>
                <div className="font-semibold">{om.label}</div>
                <div className="text-xs opacity-70 mt-0.5">{om.desc}</div>
              </button>
            ))}
          </div>

          {outputMode === 'variant' && (
            <div>
              <p className="text-xs font-semibold text-gray-500 dark:text-[#5A5E70] uppercase tracking-wide mb-2">유사문항 수</p>
              <div className="flex gap-2">
                {[1, 2].map(n => (
                  <button key={n} onClick={() => setVariantCount(n)}
                    className={`px-4 py-2 rounded-lg text-sm border transition-colors ${variantCount === n ? 'border-sky-500 dark:border-violet-500 bg-sky-50 dark:bg-violet-500/10 text-sky-700 dark:text-violet-300 font-semibold' : 'border-gray-200 dark:border-[#353844] text-gray-600 dark:text-[#5A5E70]'}`}>
                    {n}개
                  </button>
                ))}
              </div>
            </div>
          )}

          <button onClick={handleProcess}
            className="w-full py-3 rounded-xl font-semibold text-white bg-gradient-to-r from-sky-500 to-blue-600 dark:from-violet-600 dark:to-purple-700 shadow-md hover:opacity-90 transition-all">
            ✦ 처리 시작 ({confirmedBboxes.filter(b => b.selected).length}개 문제)
          </button>
        </div>
      )}

      {/* 에러 */}
      {error && (
        <div className="p-3 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-700 dark:text-red-400 rounded-xl text-sm">
          {error}
        </div>
      )}

      {/* ── 4단계: 처리 결과 ── */}
      {(step === 'processing' || step === 'done') && cards.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-gray-700 dark:text-[#E2E4F0]">처리 결과</h2>
            {step === 'done' && (
              <div className="flex gap-2">
                <button onClick={() => { setStep('upload'); setFile(null); setCards([]) }}
                  className="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-[#353844] text-gray-600 dark:text-[#5A5E70] hover:bg-gray-50 dark:hover:bg-[#2A2D38]">
                  처음부터
                </button>
                <button onClick={handleHwpxDownload}
                  className="text-sm px-3 py-1.5 rounded-lg font-semibold text-white bg-gradient-to-r from-sky-500 to-blue-600 dark:from-violet-600 dark:to-purple-700">
                  📥 전체 다운로드
                </button>
              </div>
            )}
          </div>
          {cards.map(card => (
            <ScanResultCard key={card.problemId} {...card} model={model} grade={grade} />
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/src/components/TabScan.jsx
git commit -m "feat: rewrite TabScan with crop workflow state machine"
```

---

## Task 4.5: ScanVariantRequest output_mode 수정 + /api/text-to-hwpx 엔드포인트

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: ScanVariantRequest에 output_mode 필드 추가**

`backend/main.py`의 `ScanVariantRequest` 클래스를 아래로 교체:
```python
class ScanVariantRequest(BaseModel):
    ocr_data: dict
    scan_mode: str = "general"
    variant_count: int = 1
    model: str = "sonnet"
    grade: str = "none"
    output_mode: str = "variant"  # 추가
```

그리고 `scan_generate_variants` 함수 내 `process_scan` 호출을 아래로 교체:
```python
result = await claude_service.process_scan(
    req.ocr_data, req.scan_mode, req.variant_count, req.model, req.grade, output_mode=req.output_mode
)
```

히스토리 저장 부분의 `"output_mode": "variant"` 도 아래로 교체:
```python
"output_mode": req.output_mode,
```

- [ ] **Step 2: `/api/text-to-hwpx` 엔드포인트 추가**

`scan_generate_variants` 엔드포인트 바로 뒤에 추가:
```python
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
```

- [ ] **Step 3: TabScan.jsx의 handleHwpxDownload 수정**

`frontend/src/components/TabScan.jsx`의 `handleHwpxDownload` 함수를 아래로 교체:
```javascript
const handleHwpxDownload = async () => {
  const doneCards = cards.filter(c => c.status === 'done' && c.result)
  if (doneCards.length === 0) return
  try {
    const res = await fetch(`${API}/api/text-to-hwpx`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        texts: doneCards.map(c => c.result),
        filename: 'scan_result',
      }),
    })
    if (!res.ok) throw new Error('HWPX 생성 실패')
    const data = await res.json()
    window.location.href = `${API}/api/hwpx-download/${data.download_id}`
  } catch (e) {
    setError(e.message)
  }
}
```

- [ ] **Step 4: 커밋**

```bash
git add backend/main.py frontend/src/components/TabScan.jsx
git commit -m "feat: fix scan-generate-variants output_mode + add text-to-hwpx endpoint"
```

---

## Task 8: Docker 빌드 + 통합 테스트

**Files:**
- No code changes — Docker rebuild only

- [ ] **Step 1: Docker 컨테이너 재빌드 및 재시작**

```bash
cd "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution"
docker compose build && docker compose up -d
```

- [ ] **Step 2: 백엔드 헬스체크**

```bash
curl http://localhost:8001/api/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 3: 수동 통합 테스트**

브라우저에서 `http://localhost:5173` 접속 후 스캔 탭에서 아래 시나리오 확인:

1. **이미지 업로드 → 분석 시작**: 로딩 후 크롭 수정 화면 표시
2. **bbox 편집**: 박스 이동, 크기 조절, 삭제, 새 박스 추가
3. **크롭 확정 → 출력 방식 선택**: 타이핑만 선택 후 처리 시작
4. **결과 카드**: 문제별 아코디언 카드, "+ 해설 추가" 버튼 동작 확인
5. **PDF 업로드**: 여러 페이지 PDF에서 페이지 네비게이션 동작 확인
6. **Gemini bbox 없음 케이스**: 수식이 없는 이미지 업로드 시 "감지 못 했습니다" 안내 확인

- [ ] **Step 4: 최종 커밋**

```bash
git add .
git commit -m "feat: complete scan crop workflow — AI bbox detection + editor + streaming results"
```
