# 스캔 크롭 워크플로우 디자인 스펙

**날짜:** 2026-04-16  
**상태:** 승인됨  
**대상 파일:** `frontend/src/components/TabScan.jsx` (전체 교체)

---

## 개요

기존 스캔탭(단일 파일 업로드 → 즉시 OCR)을 AI 문제 영역 감지 + 사용자 크롭 수정 워크플로우로 완전히 교체한다. 이미지와 PDF 모두 동일하게 동작한다.

---

## 전체 플로우 (방식 A — 한 번에 전체 감지)

```
1단계: 업로드
  이미지 또는 PDF 드래그/클릭/붙여넣기 → "분석 시작" 클릭

2단계: AI 감지 + 크롭 수정
  백엔드: PDF → 페이지 이미지 변환(pymupdf) + Gemini bbox 감지 (전체 일괄)
  프론트: 단일 페이지 뷰어 + 화살표/페이지 네비게이션 + 우측 문제 목록 사이드바
  사용자: 박스 이동/크기조절/삭제/추가 후 "크롭 확정"

3단계: 출력 방식 선택
  전체 문제에 일괄 적용
  선택지: 타이핑만 | 타이핑+해설 | 유사문항 생성

4단계: 처리 + 결과
  문제를 하나씩 순서대로 처리 (SSE 스트리밍)
  각 결과: 아코디언 카드로 표시
  타이핑만인 경우: 카드에 "+ 해설 추가" / "+ 유사문항" 버튼 제공
  완료 후: 전체 HWPX 파일 다운로드 버튼
```

---

## 백엔드

### 신규 엔드포인트 1: `POST /api/scan-detect`

**입력 (multipart/form-data):**
- `file`: 이미지 또는 PDF
- `model`: `"sonnet"` | `"opus"`

**처리:**
1. PDF인 경우 pymupdf로 페이지별 PNG 변환
2. 각 페이지 이미지를 `gemini_service.detect_problem_bboxes()`로 감지
3. 페이지 이미지를 base64로 인코딩

**응답 (JSON):**
```json
{
  "pages": [
    {
      "page_index": 0,
      "image_base64": "...",
      "media_type": "image/png",
      "bboxes": [
        {"id": "p0_b0", "x": 0.05, "y": 0.04, "w": 0.90, "h": 0.18, "label": "문제 1"}
      ]
    }
  ],
  "total_pages": 3
}
```

> bbox 좌표는 페이지 이미지 크기 대비 **비율값(0~1)**으로 반환. 프론트에서 실제 렌더링 크기에 맞게 변환.

---

### 신규 엔드포인트 2: `POST /api/scan-crop-process` (SSE)

**입력 (JSON):**
```json
{
  "pages": [...],           // /api/scan-detect 응답 그대로
  "confirmed_bboxes": [     // 사용자가 수정한 최종 bbox 목록
    {"id": "p0_b0", "page_index": 0, "x": 0.05, "y": 0.04, "w": 0.90, "h": 0.18, "label": "문제 1", "selected": true}
  ],
  "output_mode": "type_only",  // "type_only" | "type_with_solution" | "variant"
  "variant_count": 1,
  "model": "sonnet",
  "grade": "high1"
}
```

**처리:**
- `selected: true`인 bbox만 처리
- bbox 좌표로 페이지 이미지를 크롭 → Claude `process_scan()` 호출
- 문제 하나 완료될 때마다 SSE 이벤트 전송

**SSE 이벤트 형식:**
```
data: {"type": "progress", "problem_id": "p0_b0", "label": "문제 1", "status": "processing"}
data: {"type": "result", "problem_id": "p0_b0", "label": "문제 1", "result": "...", "ocr_data": {...}, "output_mode": "type_only"}
data: {"type": "done", "total": 4}
```

---

### 신규 서비스 함수: `gemini_service.detect_problem_bboxes()`

**입력:** 페이지 이미지 base64, media_type  
**출력:**
```json
[
  {"x": 0.05, "y": 0.04, "w": 0.90, "h": 0.18},
  {"x": 0.05, "y": 0.25, "w": 0.90, "h": 0.22}
]
```

Gemini 프롬프트: 이미지에서 각 수학 문제 영역의 bounding box를 비율 좌표로 JSON 반환 요청.

---

### 기존 서비스 재사용

- `claude_service.process_scan()`: 크롭된 이미지 OCR + 처리 (변경 없음)
- `hwpx_service.create_hwpx()`: 전체 결과 → HWPX 변환 (변경 없음)
- `history_service`: 완료된 전체 결과 히스토리 저장

---

## 프론트엔드

### TabScan.jsx — 단계별 상태 머신

```javascript
step: 'upload' | 'detecting' | 'editing' | 'selecting' | 'processing' | 'done'
```

각 step에 따라 다른 UI 렌더링. 뒤로가기 버튼으로 이전 단계 이동 가능 (upload/editing 단계까지).

---

### 신규 컴포넌트: CropEditor.jsx

**역할:** 단일 페이지 뷰어 + bbox 편집 UI

**레이아웃:**
- 상단 툴바: 선택/이동 | 박스 추가 | 삭제 | 처음/이전/페이지입력/다음/마지막 네비
- 중앙: 페이지 이미지 (A4 비율, 좌우 화살표)
- 우측 사이드바: 감지된 문제 목록, 현재 페이지/다른 페이지 구분, 전체선택/해제, "크롭 확정" 버튼

**bbox 편집 기능:**
- 드래그: 박스 이동
- 모서리 드래그: 크기 조절 (8방향 핸들)
- Delete 키 / 삭제 버튼: 선택된 박스 삭제
- 빈 영역 드래그: 신규 박스 생성

**테마:**
- 브라이트 모드: B3 (라이트 그레이 `#F4F5F7`, 스카이블루 `#0EA5E9`)
- 다크 모드: D3 (소프트 다크 `#22252E`, 퍼플 `#8B5CF6`)

---

### 신규 컴포넌트: ScanResultCard.jsx

**역할:** 문제별 아코디언 결과 카드

**상태별 표시:**
- 대기 중: 회색 배지
- 처리 중: 노란 배지 + 스피너
- 완료: 초록 배지 + 결과 텍스트 (SolutionDisplay 재사용)

**추가 액션 버튼 (output_mode === 'type_only'인 경우):**
- `+ 해설 추가`: 해당 문제 ocr_data로 기존 `/api/scan-generate-variants` 호출 (output_mode: "type_with_solution")
- `+ 유사문항`: 해당 문제 ocr_data로 기존 `/api/scan-generate-variants` 호출 (output_mode: "variant")

**결과 영역 하단:**
- 전체 HWPX 다운로드 버튼 (모든 문제 처리 완료 후 활성화)

---

## 처리 안 되는 케이스 (에러 처리)

| 상황 | 처리 |
|------|------|
| Gemini가 bbox를 하나도 못 찾은 경우 | "문제를 감지하지 못했습니다. 직접 박스를 추가해 주세요." 안내 후 편집 단계로 이동 |
| 특정 문제 처리 실패 | 해당 카드에 에러 표시, 나머지 문제는 계속 처리 |
| 타임아웃 (대용량 PDF) | 30초 경과 시 경고 표시, 계속 대기 여부 선택 |
| 파일 크기 초과 | 업로드 시점에 20MB 제한 안내 |

---

## 변경되는 파일 목록

| 파일 | 변경 내용 |
|------|----------|
| `frontend/src/components/TabScan.jsx` | 전체 재작성 |
| `frontend/src/components/CropEditor.jsx` | 신규 생성 |
| `frontend/src/components/ScanResultCard.jsx` | 신규 생성 |
| `backend/main.py` | `/api/scan-detect`, `/api/scan-crop-process` 엔드포인트 추가 |
| `backend/services/gemini_service.py` | `detect_problem_bboxes()` 함수 추가 |

**변경 없는 파일:**
- `claude_service.py`, `hwpx_service.py`, `history_service.py`, `graph_service.py`
- 기존 다른 탭 컴포넌트들
