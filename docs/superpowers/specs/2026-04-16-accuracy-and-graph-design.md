# 설계 문서: 풀이 정확도 향상 + 그래프 품질 개선

**날짜:** 2026-04-16  
**상태:** 승인됨

---

## 1. 배경 및 목표

### 문제
- Claude가 생성하는 유사문항 풀이에서 계산 실수, 논리 비약, 문제-풀이 불일치, 최종 답 오류 등 복합적인 정확도 문제가 발생함
- Matplotlib으로 생성된 그래프가 수능/교과서 스타일과 맞지 않아 실제 사용 불가 수준임 (스타일 문제가 주원인)

### 목표
1. 풀이 정확도를 높이기 위해 Few-shot 예시 + 경량 검증 루프를 병행 도입
2. Matplotlib 그래프를 Claude가 직접 생성하는 SVG 방식으로 교체

---

## 2. 풀이 정확도 개선

### 2-1. 프롬프트 강화

**파일:** `backend/prompts/solve_prompt.txt`, `backend/prompts/variant_solve_prompt.txt`

추가할 규칙:
1. **답 먼저 설계 강화** — 풀이 작성 전 최종 답을 내부 계산으로 확정 (기존 규칙 강화)
2. **중간값 명시 강제** — 각 STEP에서 계산한 중간 결과값을 반드시 수식으로 명시
3. **역검증 규칙** — 마지막 STEP에서 답을 문제 조건에 대입해 성립 여부 확인 후 출력

### 2-2. Few-shot 예시 추가

**파일:** `backend/prompts/fewshot_examples.txt` (신규)

- 수학 교사가 검수한 올바른 풀이 예시 2~3개 포함
- 문제 유형별로 구성 (수열, 함수, 확률 등)
- `claude_service.py`의 `_build_prompt()` 메서드에서 시스템 프롬프트에 자동 결합
- 예시 형식은 기존 출력 형식(STEP, 한글 수식 등)과 동일하게 작성

### 2-3. 경량 검증 루프

**파일:** `backend/services/claude_service.py`, `backend/prompts/verify_prompt.txt` (신규)

**흐름:**
```
1차 생성 (generate/solve-variant)
    ↓
verify_solution() 호출 (Claude Sonnet, 짧은 프롬프트)
    ↓
일치: 그대로 반환
불일치: 1회 재생성 (max_retry=1)
    ↓
재생성 후에도 불일치: verified=false 플래그와 함께 반환
```

**verify_prompt.txt 내용 방향:**
- "아래 문제와 풀이를 보고, 최종 답이 올바른지 확인하라. OK 또는 FAIL과 간단한 이유만 출력하라."
- 전체 풀이 재출력 금지

**API 응답 변경:**
- `/api/generate`, `/api/solve-variant` 응답에 `"verified": true/false` 필드 추가
- 프론트엔드에서 `verified=false`일 때 경고 배지 표시

**비용/속도:**
- 검증 호출은 입력 토큰 최소화 (문제 + 최종 답만 전달)
- 재생성은 오류 건에만 발생 → 평균 응답 시간 영향 미미

---

## 3. 그래프 품질 개선 (SVG 방식)

### 3-1. Matplotlib 제거

- `graph_service.py`의 Matplotlib 렌더링 로직 제거
- `backend/data/graph_style_profile.json` 사용 중단

### 3-2. SVG 직접 생성 파이프라인

**태그 문법 (기존 유지, 내용 변경):**
```
-그래프-
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="400" height="400">
  <!-- 수능 스타일 그래프 SVG 코드 -->
</svg>
-그래프끝-
```

**graph_service.py 변경:**
- `-그래프-` 태그 내 SVG 코드 추출
- SVG를 그대로 프론트엔드에 전달 (PNG 변환 불필요)
- 유효하지 않은 SVG일 경우 에러 메시지로 대체

**프롬프트 변경 (`solve_prompt.txt`):**
- 수능 스타일 SVG 규격 명시 (축 화살표, 라벨 위치, 점근선 점선, 포인트 표기 등)
- Few-shot SVG 예시 1~2개 포함 (간단한 함수 그래프)

### 3-3. 프론트엔드 변경

**파일:** `frontend/src/components/SolutionDisplay.jsx` (또는 관련 렌더링 컴포넌트)

- 기존: 서버에서 받은 PNG URL을 `<img>` 태그로 표시
- 변경: 서버에서 받은 SVG 문자열을 `dangerouslySetInnerHTML` 또는 직접 파싱하여 렌더링
- SVG는 벡터라 확대해도 선명함

### 3-4. 리스크 및 완화 방안

| 리스크 | 완화 방안 |
|--------|----------|
| Claude가 복잡한 SVG를 잘못 생성 | Few-shot 예시 품질 관리, 간단한 그래프부터 적용 |
| SVG 파싱 실패 | fallback: "그래프를 생성할 수 없습니다" 메시지 표시 |
| XSS 위험 (SVG 직접 렌더링) | SVG sanitization 라이브러리(DOMPurify) 적용 |

---

## 4. 구현 범위 요약

| 항목 | 파일 | 작업 |
|------|------|------|
| 프롬프트 강화 | `solve_prompt.txt`, `variant_solve_prompt.txt` | 규칙 3개 추가 |
| Few-shot 예시 | `fewshot_examples.txt` (신규) | 예시 2~3개 작성 |
| 검증 프롬프트 | `verify_prompt.txt` (신규) | 검증 지시 작성 |
| 검증 루프 | `claude_service.py` | `verify_solution()` 메서드 추가 |
| API 응답 | `main.py` | `verified` 필드 추가 |
| 그래프 서비스 | `graph_service.py` | Matplotlib 제거, SVG 추출로 변경 |
| 프론트엔드 | `SolutionDisplay.jsx` | SVG 렌더링, 경고 배지 추가 |

---

## 5. 제외 범위

- 모델 파인튜닝 (Anthropic API 미지원)
- RAG 기반 문제 DB 구축 (복잡도 대비 효과 불확실)
- Extended Thinking 도입 (비용/속도 부담, 향후 고려)
- Plotly/Bokeh 등 다른 Python 그래프 라이브러리
