# Tab Unification Design Spec
**Date:** 2026-04-19  
**Feature:** "유사문항 생성" + "한글 파일" 탭 통합

---

## Problem

현재 두 탭이 같은 목표(유사문항 생성)를 달성하지만 입력 방식만 다름:
- **탭1 (TabCreateVariant)**: 이미지로 문제+해설 입력 → 유사문항 생성
- **탭3 (TabHwpx)**: HWPX 파일에서 문제 선택 → 유사문항 생성

사용자는 매번 어느 탭에 가야 할지 판단해야 하고, 두 탭의 UX가 따로 발전해 왔다. HWP 파일(HWPX 아님) 지원도 없음.

---

## Solution: Approach B — Shell + Subcomponents

### 1차 화면: 입력 방식 선택

`TabCreateVariant`를 **선택 화면 껍데기(shell)**로 바꾼다. 아무것도 선택하지 않은 상태에서는 두 개의 큰 카드 버튼을 보여준다:

```
┌─────────────────────┐  ┌─────────────────────┐
│  📸 이미지로 입력   │  │  📄 한글 파일 입력  │
│                     │  │                     │
│  문제·해설 이미지를 │  │  HWP / HWPX 파일   │
│  직접 업로드        │  │  에서 문제 선택     │
└─────────────────────┘  └─────────────────────┘
```

카드 선택 시 해당 모드의 UI로 전환. 상단 "← 뒤로" 버튼으로 선택 화면 복귀.

### 서브컴포넌트 구조

```
TabCreateVariant.jsx          ← 새 shell (모드 선택 + 라우팅)
├── ImageInputMode.jsx        ← 기존 TabCreateVariant 내용 추출
└── HwpxInputMode.jsx         ← 기존 TabHwpx 내용 rename (HWP지원 추가)
```

**App.jsx**: "한글 파일" 탭 제거. 탭 개수 5개 → 4개.

### HWP → HWPX 자동 변환

- **업로드 시 `.hwp` 감지** → 백엔드 `/api/hwpx-convert` 호출 → HWPX 반환
- **변환기**: `backend/services/hwp_converter.py`의 win32com (`HWPDocument.SaveAs`)
- **가용성 사전 확인**: 서버 시작 시 win32com import 시도, 결과를 `/api/system-info`에 포함
- **미지원 환경**: win32com 없으면 "HWP 변환 불가" 안내 배너, HWPX만 허용

---

## Files Changed

| 파일 | 변경 내용 |
|------|-----------|
| `frontend/src/components/TabCreateVariant.jsx` | shell로 재작성 (모드 선택 화면 + 서브컴포넌트 렌더링) |
| `frontend/src/components/ImageInputMode.jsx` | 신규 — 기존 TabCreateVariant 내용 이동 |
| `frontend/src/components/HwpxInputMode.jsx` | 신규 — 기존 TabHwpx 내용 rename (HWP 지원 추가) |
| `frontend/src/App.jsx` | "한글 파일" 탭 제거, TabHwpx import 제거 |
| `backend/main.py` | `/api/hwpx-convert` 엔드포인트 추가, `/api/system-info` win32com 상태 포함 |

---

## HWP 변환 API

```
POST /api/hwpx-convert
Body: multipart/form-data { file: HWP file }
Response: { hwpx_path: string, filename: string }
```

내부 동작: `hwp_converter.py`의 `convert_hwp_to_hwpx(src, dst)` 호출 → 임시 디렉토리에 HWPX 저장 → 경로 반환.

---

## System Info API (win32com 상태 확인)

```
GET /api/system-info
Response: { hwp_converter_available: boolean, ... }
```

서버 시작 시 1회 확인, 캐시. 프론트엔드는 앱 로드 시 이 값을 조회해서 HWP 업로드 버튼 활성화 여부 결정.

---

## Error Handling

- win32com 없음 → 프론트에서 `.hwp` 파일 선택 시 "이 환경에서는 HWP 변환을 지원하지 않습니다. HWPX 파일로 변환 후 업로드해 주세요." 메시지
- 변환 실패 → "HWP 변환 중 오류가 발생했습니다. 한글에서 다른 이름으로 저장 → HWPX로 저장 후 재시도해 주세요."

---

## Out of Scope

- 탭2 (TabSolveVariant) 통합 — 풀이 탭은 성격이 달라 분리 유지
- "수백 개 문제에서 유사문항 선택" 기능 — 별도 스펙으로 관리
- 탭4/5 변경 없음
