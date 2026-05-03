# Plan: SVG 라이브러리 학습 웹앱 + 차은우 페르소나

Design: `docs/superpowers/specs/2026-04-24-svg-library-trainer-design.md`
Branch: `feature/svg-library-trainer`
Worktree: `.worktrees/svg-library-trainer/`
Mode: Builder
Created: 2026-04-24
Revised: 2026-04-25 (갈량 GO_WITH_FIXES 반영)

## 갈량 피드백 반영 이력 (2026-04-25)

- [상1] Task #4.5 신설 (변환 도구 결정)
- [상2] Task #9를 갈량 초안 + 카리나 커밋 2단계로 분할
- [중3] `@font-face` CSS 생성 담당을 Task #1 → Task #6으로 이동
- [중4] Success Criteria에 "시범=첫 5개 의무, 나머지 선택" 명시
- [중5] Task #8에 차은우 메모리 육안 검증 항목 추가
- [하6] Task #2에 DBSCAN `eps = bbox 대각선 5%` seed 기재
- [하7] Task #5에 "라우터 수정 시 Claude가 직접 서버 재기동" 운영 메모

## Task 개요

Approach B(MathSolution 통합 탭 + Gemini 초안) 구현. 총 9개 Task로 분리. 초반 Task(#1~#4)는 독립 병렬, 중반(#5~#7)은 #1~#4 완료 후, 마지막(#8~#9)은 end-to-end 검증.

의존성 그래프:

```
#1 폰트 등록 ──┐
#2 SVG 분할   ─┼─→ #5 백엔드 API ─→ #6 프론트 탭 ─→ #8 시범 운행 ─→ #9 문서·마감
#3 차은우 프롬프트 ┤
#4 스키마 설계 ──┘                     ↑
                                       #7 Gemini 초안 서비스
```

---

## Task #1 — 폰트 등록 파이프라인

**담당**: 차은우
**위치**: `backend/data/fonts/`, `backend/services/font_service.py` (신규)
**의존**: 없음 (병렬)

체크리스트:
- [ ] 루트 `font/` 폴더를 `backend/data/fonts/`에 복사 (Windows → symlink 아닌 복사)
- [ ] `font_service.py` 작성 — `register_fonts()` 함수로 Matplotlib FontProperties에 HCRBatang·KoPubDotum 등록
- [ ] `/api/fonts/list` 엔드포인트 — 사용 가능 폰트 목록 반환 (파일명·familyName·스타일)
- [ ] `/api/fonts/{name}` 엔드포인트 — TTF/OTF 바이너리 serve (Content-Type: font/ttf or font/otf)
- [ ] backend 기동 시 자동으로 `register_fonts()` 호출 (main.py lifespan)

> 갈량 피드백 반영: `@font-face` CSS 생성은 프론트 영역 → Task #6으로 이동 (카리나 담당).

**DoD**: `curl http://localhost:8001/api/fonts/list` 호출 시 10개 폰트 반환. Matplotlib으로 "한글 테스트" 그림 생성 시 HCRBatang으로 렌더.

---

## Task #2 — SVG 자동 분할 스크립트

**담당**: 차은우
**위치**: `backend/services/svg_splitter.py` (신규)
**의존**: 없음 (병렬)

체크리스트:
- [ ] `svgpathtools`, `scikit-learn`(DBSCAN용) 의존성 추가 (`backend/requirements.txt`)
- [ ] `split_svg(input_path: str, output_dir: str) -> list[PartInfo]` 구현
  - lxml로 `<path>` 전체 파싱
  - 각 path의 bbox 추출
  - DBSCAN 클러스터링 — **seed 파라미터: `eps = 원본 viewBox 대각선 길이의 5%`, `min_samples = 1`** (갈량 피드백 하6 반영)
  - 각 클러스터를 개별 SVG로 재작성 (원본 `<defs>` 스타일 유지, viewBox는 클러스터 bbox에 맞게 재계산)
- [ ] 시범 대상: `SVG/#4_미적분2 그림.svg` (0.4MB, 655 paths)
- [ ] 결과를 `backend/data/svg_library/parts/#4_{index:03d}.svg`로 저장
- [ ] 각 부품별 원본 bbox·path 수를 `parts_meta.json`에 기록
- [ ] CLI 실행: `python -m backend.services.svg_splitter <input> <output_dir>` 지원

**DoD**: `python -m backend.services.svg_splitter SVG/#4_미적분2\ 그림.svg` 실행 시 `parts/` 에 N개 SVG 생성 (N≥10 목표). 각 SVG는 viewBox가 부품에 맞게 재계산됨.

**리스크**: 분할 품질 미확인. 실패 시 Approach C(Illustrator 복사-붙여넣기)로 폴백.

---

## Task #3 — 차은우 시스템 프롬프트

**담당**: 차은우
**위치**: `backend/prompts/eunwoo_system_prompt.txt` (신규)
**의존**: 없음 (병렬)

체크리스트:
- [ ] 페르소나 설정 블록
  - 이름: 차은우
  - 역할: SVG 부품 라벨링 어시스턴트
  - 호칭: "형님" 기본, "주인님" 정식
  - 말투: 조심스러운 존댓말, 단단함, 애교 금지
- [ ] 질문 템플릿 (라벨링 플로우)
  1. "형님, 이 그림 혹시 {초안명} 맞습니까?"
  2. 맞으면 → "해당 단원은 {미적분2 등} 맞습니까? 다른 단원이면 말씀해 주십시오."
  3. 추가 메타데이터 질문 (변형 가능 파라미터, 특징)
- [ ] 출력 형식 지시 (JSON로 응답)
- [ ] 불확실할 때는 "확신이 없습니다만" 식으로 단서 달고 선생님 확인 요청

**DoD**: 프롬프트 파일 완성. Phase 8 시범에서 실제 Gemini 응답이 말투 가이드 준수하는지 검증.

---

## Task #4 — 카탈로그 스키마 설계

**담당**: 차은우
**위치**: `backend/data/svg_library/catalog_schema.json` (신규), `backend/models/svg_part.py` (신규 Pydantic)
**의존**: 없음 (병렬)

체크리스트:
- [ ] Pydantic 모델 `SvgPart` 정의
  - `id: str` (예: "4-001")
  - `filename: str` (상대경로)
  - `name: str` (한글 이름, 예: "지수함수 y=2^x 기본형")
  - `category: str` (단원, 예: "미적분2")
  - `subcategory: str` (예: "지수로그함수")
  - `tags: list[str]` (검색 키워드)
  - `variable_params: list[ParamDef]` (변수화 가능 파라미터 메타)
  - `ai_draft: dict` (Gemini 초안 보관)
  - `verified_by_teacher: bool`
  - `bbox: dict` (원본 좌표)
  - `created_at`, `updated_at`
- [ ] `ParamDef` 서브모델 — name, type(number/position/color), default, description
- [ ] `catalog.json` 최상위 구조 — `{ version, parts: [...], total_count }`
- [ ] `progress.json` 별도 — `{ total, labeled, skipped, in_progress_id }`

**DoD**: 스키마 파일 + Pydantic 모델 완성. 빈 catalog 작성/읽기 테스트 통과.

---

## Task #4.5 — SVG→PNG 변환 도구 결정 (갈량 피드백 상1)

**담당**: 견우(조사·벤치마크) → 차은우(결정·구현)
**위치**: `backend/services/svg_to_png.py` (신규)
**의존**: Task #2 완료 후 (실제 분할된 부품 하나로 벤치마크)

**배경**: Task #5의 `/preview.png` 엔드포인트와 Task #7의 Gemini 입력용 PNG 변환이 공통 함수를 쓰기로 했으나, 도구(Resvg vs Playwright 헤드리스 Chrome)가 미정이었음. 먼저 결정해야 #5·#7 착수 가능.

체크리스트:
- [ ] 견우: 두 도구 비교 조사
  - Resvg (resvg-py 또는 Rust 바이너리): 속도·의존성·폰트 임베딩 방법
  - Playwright: 정확도·설치 비용·느리기
- [ ] 은우: Task #2 결과 부품 1개로 양쪽 변환 실행, PNG 결과 비교 (폰트 렌더링 품질·속도)
- [ ] 결정 근거를 이 Task 섹션에 1문단으로 기록
- [ ] 선택한 도구로 `svg_to_png(svg_text: str, width: int, height: int) -> bytes` 함수 구현
- [ ] `backend/data/fonts/`의 폰트를 변환 시 주입 (특히 HancomEQN 수식체)
- [ ] 단위 테스트: 샘플 SVG → PNG 변환 결과 비어있지 않음, 폭/높이 일치

**DoD**: 도구 선택 완료, 변환 함수 동작. `python -m backend.services.svg_to_png <svg>` CLI 성공.

---

## Task #5 — 백엔드 API 엔드포인트

**담당**: 차은우
**위치**: `backend/api/svg_library.py` (신규), `backend/services/svg_library_service.py` (신규)
**의존**: #1, #2, #4 완료 후

체크리스트:
- [ ] `svg_library_service.py` 작성 — 카탈로그 CRUD (파일 기반 atomic write)
- [ ] `POST /api/svg-library/ingest` — 원본 SVG 경로 받아 Task#2 분할 트리거, progress.json 초기화
- [ ] `GET /api/svg-library/next` — 라벨링 안 된 다음 부품 반환 (SVG 본문 + id + ai_draft)
- [ ] `POST /api/svg-library/label` — 최종 라벨 저장 (catalog.json 업데이트, progress 증가)
- [ ] `POST /api/svg-library/skip` — 건너뛰기 (progress.skipped 증가)
- [ ] `GET /api/svg-library/catalog` — 전체 카탈로그 반환
- [ ] `GET /api/svg-library/progress` — 진행률
- [ ] `GET /api/svg-library/part/{id}/preview.png` — PNG 변환 프리뷰
- [ ] 라우터를 `backend/main.py`에 등록
- [ ] 파일 락 or atomic 쓰기로 동시성 보호

> **운영 메모 (갈량 피드백 하7)**: `--reload` 금지 기조상 라우터 수정 후 서버 반영은 Claude가 직접 재기동. 수동 재시작 요청 대신 `[카리나]`가 `taskkill`→`uvicorn` 재기동 명령을 즉시 실행한다.

**DoD**: `/docs` Swagger에서 전체 엔드포인트 노출. curl로 ingest → next → label 사이클 수동 테스트 성공.

---

## Task #6 — 프론트엔드 SVG 학습 탭

**담당**: 카리나 (frontend 영역) — 은우는 백엔드만, 프론트 통합은 카리나
**위치**: `frontend/src/components/TabSvgTraining.jsx`, `frontend/src/App.jsx` (탭 추가)
**의존**: #5 완료 후

체크리스트:
- [ ] `TabSvgTraining.jsx` — 주요 섹션 4개
  - 상단 ProgressBar (N/M, %)
  - 좌측 SvgViewer (`srcDoc` or inline SVG, `@font-face` 적용)
  - 우측 EunwooChat (차은우 대화 영역, 현재 질문·답변 입력)
  - 하단 LabelForm (AI 초안 표시 + 수정 필드 + 승인 버튼)
- [ ] `@font-face` CSS — `/api/fonts/{name}` 경로로 10종 등록
- [ ] `useSvgTraining()` 커스텀 훅 — next/label/skip API 연동
- [ ] 키보드 단축키: `Enter` = 승인, `Ctrl+S` = 건너뛰기
- [ ] `App.jsx`에 탭 추가: "SVG 학습" (기존 탭 뒤에)
- [ ] 탭 아이콘·색상 기존 스타일 가이드 준수

**DoD**: `npm run dev` → 5173 접속 → "SVG 학습" 탭 진입 → 부품 보임 → 라벨 저장 → 다음 부품으로 진행.

---

## Task #7 — Gemini 초안 서비스

**담당**: 차은우
**위치**: `backend/services/eunwoo_service.py` (신규)
**의존**: #3, #4 완료 후

체크리스트:
- [ ] 기존 `gemini_service.py` 패턴 차용 — `google.genai` 클라이언트 재사용
- [ ] `EunwooService.suggest_label(part_svg: str) -> AiDraft` 구현
  - SVG를 PNG로 변환 (Task#5의 변환 함수 재사용)
  - PNG + 시스템 프롬프트(Task#3) + 스키마(Task#4)를 Gemini에 전달
  - 응답 JSON 파싱 → `AiDraft` 반환
- [ ] 에러 핸들링 — Gemini 실패 시 빈 초안 반환, 로그 남김
- [ ] 캐싱 — 같은 부품 재호출 방지 (파일 기반)
- [ ] Task#5의 `/next` 엔드포인트가 이 서비스를 통해 `ai_draft` 포함해서 반환

**DoD**: #4 단일 부품 SVG 투입 시 Gemini가 "형님, 이건 ○○ 같습니다만 확인 부탁드립니다" 톤의 JSON 반환.

---

## Task #8 — 시범 운행 (End-to-End)

**담당**: 이순신 (검증) + 차은우 (이슈 수정)
**위치**: N/A (수동 테스트)
**의존**: #1~#7 전부 완료 후

체크리스트:
- [ ] **(갈량 피드백 중5) 차은우 메모리 실재 확인** — `feedback_team_personas.md`·`team_roster.md` 둘 다 `[은우]` 태그 + 호칭("형님/주인님") + 담당 영역(SVG 라이브러리) 기재 육안 검증
- [ ] 백엔드 재시작 → 엔드포인트 정상 기동
- [ ] POST `/api/svg-library/ingest` with `SVG/#4_미적분2 그림.svg` → 분할 성공
- [ ] 프론트 "SVG 학습" 탭 접속 → 첫 부품 렌더 (폰트 적용된 원본 수준)
- [ ] 차은우 AI 초안이 말투·스키마 준수
- [ ] 선생님 승인 5개 → catalog.json에 5개 부품 기록 (**시범 의무 범위**)
- [ ] 건너뛰기 1개 → progress.skipped 증가
- [ ] 브라우저 새로고침 → 진행 상태 유지 (멈췄다 재개 검증)
- [ ] PNG 프리뷰 성공 (폰트 반영)
- [ ] 이순신이 `/qa` 스킬로 E2E 시나리오 실행 후 보고

**DoD**: 최소 5개 부품 라벨링 완주 + 자동 저장 정상 + 재개 정상.

**실패 시**: Approach C(Illustrator 복사-붙여넣기) 폴백 모드 설계 후 재도전.

---

## Task #9 — 문서·커밋·진행일지 (갈량 피드백 상2 반영: 2단계 분할)

### #9-A — 문서 초안 작성

**담당**: 갈량 (감사조 직분 — 문서·보고서 초안 작성까지)
**의존**: #8 완료 후

체크리스트:
- [ ] `CLAUDE.md`에 추가할 SVG 라이브러리 파이프라인 섹션 **초안 작성**
- [ ] `기능_명세서.md`에 추가할 "SVG 학습 탭" 섹션 **초안 작성**
- [ ] `진행일지.md`에 추가할 2026-04-24/25 세션 블록 **초안 작성** (차은우 등장, B 방식 채택, 시범 결과, 갈량 리뷰 반영 이력)
- [ ] `project_svg_trainer_progress.md` 업데이트 내용 **초안 작성**
- [ ] 위 초안들을 한 메시지로 정리해 `[카리나]`에게 인계

**DoD**: 4개 문서 초안 완성, 카리나 인계 준비 완료.

### #9-B — 커밋·Ship 실행

**담당**: 카리나 (실무조 — 실제 파일 쓰기·커밋·푸시 직분)
**의존**: #9-A 완료 후

체크리스트:
- [ ] 갈량 초안을 실제 파일에 반영 (`CLAUDE.md`, `기능_명세서.md`, `진행일지.md`, 메모리)
- [ ] 모든 코드·문서 커밋 (Task #1~#8 전체 포함)
- [ ] `/ship` 스킬로 브랜치 PR 준비 (아직 merge 안 함, 시범 운행 재검증 후)

**DoD**: Feature 브랜치에 모든 커밋 정리됨. PR 초안 생성됨(머지는 주인님 승인 대기).

---

## 전체 완료 기준 (Success Criteria 재확인, 갈량 피드백 중4 반영)

> **시범 범위 명시**: 이번 세션의 의무 범위는 **`#4_미적분2` 파일 한 개 + 최소 5개 부품 라벨링**이다. 나머지 4개 SVG 파일 및 N≥10 초과분 라벨링은 선택(시범 성공 후 별도 세션에서 진행). progress.json의 `scope: "trial"` 플래그로 구분.

- [x] 차은우 페르소나 메모리 등록 (2026-04-24 세션에서 완료)
- [ ] `#4_미적분2 그림.svg` 분할 → 부품 N개 생성 (N≥10 목표, **시범 의무는 5개 이상이면 통과**)
- [ ] localhost에서 TabSvgTraining 접근 가능
- [ ] 차은우가 형님/주인님 호칭 + 조심스러운 존댓말로 대화
- [ ] Gemini 초안 → 선생님 승인/수정 → 자동 저장 사이클 완주
- [ ] **의무**: 5개 부품 이상 라벨링 완료 후 catalog.json 검증
- [ ] 라벨링된 부품 → PNG 변환 성공 (폰트 포함)
- [ ] **선택**: 시범 검증 완료 후 나머지 4개 SVG로 확장 가능성 평가 (다음 세션)

---

## 리스크 & 미정 사항

| 리스크 | 완화책 |
|--------|--------|
| SVG 자동 분할 품질 낮음 | Task#2 실패 시 Approach C 폴백 준비 (Illustrator 복사-붙여넣기) |
| Gemini 라벨 초안 품질 낮음 | 선생님 수정 중심 UX로 이미 대비. 초안이 단순 "모르겠습니다"여도 허용 |
| 폰트 렌더링 브라우저/Matplotlib 차이 | PNG 변환을 Playwright 헤드리스 Chrome으로 통일하면 일관성 확보 |
| 선생님 라벨링 시간 소요 | 시범 5개만 해보고 확장 여부 판단 (일괄 요구 X) |
| Matplotlib graph_service 공존 | 초기에는 완전 분리. 장기적 통합은 별도 세션에서 논의 |

---

## 재개 시 참조 경로

- Design: `docs/superpowers/specs/2026-04-24-svg-library-trainer-design.md`
- Plan: `docs/superpowers/plans/2026-04-24-svg-library-trainer.md` (이 문서)
- Worktree: `.worktrees/svg-library-trainer/`
- Branch: `feature/svg-library-trainer`
- Memory: `project_svg_trainer_progress.md`
