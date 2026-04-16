# TODOS

## [ ] hwpToLatex 두 버전 통합

**What:** `HwpCodeBlock.jsx`와 `TabHwpx.jsx`에 각각 다른 `hwpToLatex` 로직 존재.

**Why:** 두 버전이 독립적으로 진화하면 같은 수식에 대해 다른 결과가 나올 수 있음.

**How to apply:** `HwpCodeBlock.hwpToLatex` (이미 export됨)를 기반으로,
TabHwpx에서는 텍스트 레벨 래퍼 함수만 분리:
```js
// utils/hwpTextToLatex.js
import { hwpToLatex } from '../components/HwpCodeBlock'
export function hwpTextToLatex(text) {
  return text.replace(/\[([^\]]+)\]/g, (_, code) => `$${hwpToLatex(code)}$`)
}
```
TabHwpx의 로컬 함수 제거 후 import로 교체.
변환 규칙 병합 시 TabHwpx의 DEG, LRARROW, RARROW, THEREFORE, `+-` 등 추가 규칙을 HwpCodeBlock에 통합해야 함.

**Depends on:** 없음

---

## [ ] 루트 디렉토리 정리

**What:** 루트에 `123.hwpx`, `test_*.hwpx`, 스크린샷, 텍스트 파일 10여 개 산재.

**Why:** 배포 시 불필요한 파일이 git에 포함될 수 있음. 코드베이스 탐색 어려움.

**How to apply:**
1. 테스트 hwpx 파일들 → `backend/test_samples/` 또는 삭제
2. 스크린샷 파일 → 삭제 또는 별도 폴더
3. `.gitignore`에 `*.hwpx` (루트 레벨) 추가 검토

**Depends on:** 없음

---

## [ ] 그래프 프롬프트 — 원점 "O" 명시 규칙

**What:** Gemini/AI 이미지 생성으로 그래프를 그릴 때 원점을 숫자 "0"이 아닌 알파벳 대문자 "O"로 표시해야 함.

**Why:** AI 이미지 생성 모델이 원점 레이블을 기본으로 숫자 0으로 렌더링함. 수학 교과서 표기 기준은 알파벳 O.

**How to apply:** Gemini 그래프 생성 프롬프트(`gemini_service.py` 또는 그래프 관련 프롬프트)에 반드시 포함:
```
"label the origin as the capital letter O, not the numeral zero"
```

**Depends on:** Gemini 이미지 생성 구현 (Phase 2)

---

## [ ] 그래프 편집 UI (향후)

**What:** 그래프가 생성된 후 사용자가 직접 편집할 수 있는 인터랙티브 창. 수식 레이블 크기/위치 조정, 보조선 추가/삭제, 점 추가 등.

**Why:** 생성된 그래프가 완벽하지 않을 때 매번 프롬프트를 수정해 재생성하는 것보다 직접 편집이 훨씬 빠름. 교사가 문제지에 바로 사용할 수 있는 품질로 다듬을 수 있어야 함.

**How to apply:** SVG 기반으로 구현 시 가능한 접근:
- SVG 직접 조작 (포인트 드래그, 레이블 이동)
- fabric.js 또는 konva.js 캔버스 기반 편집기
- 또는 GeoGebra 임베드

**Depends on:** 그래프 생성 안정화 이후
