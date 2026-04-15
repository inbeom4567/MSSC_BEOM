# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

수학 유사문항 생성기 - 고등학교 수학 문제/해설 이미지 또는 HWPX 파일을 입력하면 유사문항과 풀이를 한글 수식입력기 코드로 생성하는 웹앱.

## Commands

```bash
# 백엔드 실행 (--reload 절대 사용 금지! 파일 업로드 시 서버 재시작 유발)
cd backend
python -m uvicorn main:app --port 8001

# 프론트엔드 실행
cd frontend
npm run dev

# 프론트엔드 빌드
cd frontend
npm run build

# 원클릭 실행 (Windows)
start.bat
```

## Architecture

```
Frontend (React+Vite:5173) → Direct HTTP → Backend (FastAPI:8001) → Anthropic Claude API
                                                                  → Google Gemini API
                                                                  → Matplotlib (그래프)
```

- **프론트엔드**: `http://localhost:8001`로 직접 API 호출 (Vite 프록시 미사용)
- **백엔드**: FastAPI, 포트 8001 고정, `--reload` 사용 금지
- **CORS**: `allow_origins=["*"]` (개발환경)
- **환경변수**: `backend/.env`에 `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` 설정 필요

### 핵심 API 엔드포인트

| Endpoint | Method | 기능 |
|----------|--------|------|
| `/api/generate` | POST | 유사문항 생성 (이미지2장 + variant_type + difficulty + model + grade) |
| `/api/solve-variant` | POST | 변형문항 풀이 (이미지3장 + model) |
| `/api/refine` | POST | 생성 결과 수정 (original_result + instruction + model) |
| `/api/hwpx-analyze` | POST | HWPX 파일 분석 → 문제 수/미리보기 반환 |
| `/api/hwpx-generate` | POST | HWPX 파일로 유사문항 생성 → HWPX 다운로드 |
| `/api/hwpx-solve` | POST | HWPX 파일로 변형문항 해설 작성 |
| `/api/hwpx-batch` | POST | HWPX 내 선택 문제 일괄 처리 |
| `/api/hwpx-download/{id}` | GET | 생성된 HWPX 파일 다운로드 (UUID 기반) |
| `/api/analyze-image` | POST | Gemini로 이미지 그래프 분석 |
| `/api/recognize-handwriting` | POST | Gemini로 손필기 인식 |
| `/api/history` | GET | 작업 히스토리 목록 |
| `/api/history/{id}` | GET/DELETE | 히스토리 상세/삭제 |
| `/api/prompt-feedback` | POST | 프롬프트 피드백 → 규칙 자동 추가 |

### 프론트엔드 탭 구조

- **탭1 (TabCreateVariant)**: 원본문제+해설 이미지 → 옵션(숫자/아이디어변형, 난이도, 모델, 학년) → 유사문항 생성
- **탭2 (TabSolveVariant)**: 원본문제+해설+변형문항 이미지 → 원본 해설 스타일로 풀이 작성
- **탭3 (TabHwpx)**: HWPX 파일 업로드 → 문제 선택 → 일괄 유사문항/해설 생성 → HWPX 다운로드
- **탭4 (TabHistory)**: 작업 히스토리 조회/재사용
- **탭5 (TabPromptEdit)**: 사용자 피드백 → 프롬프트에 규칙 자동 추가

### 프롬프트 시스템

- `backend/prompts/solve_prompt.txt`: 유사문항 생성용 시스템 프롬프트
- `backend/prompts/variant_solve_prompt.txt`: 변형문항 풀이용 시스템 프롬프트
- `backend/data/hwp_math_mapping.json`: 수식 매핑 사전 → 프롬프트에 자동 결합됨 (`ClaudeService._load_mapping_reference()`)
- `backend/data/curriculum.json`: 교육과정 데이터 (학년별 단원)
- 프롬프트 파일 수정 시 서버 재시작 불필요 (피드백 API가 `reload_prompts()` 호출)

### 백엔드 서비스 구조

- `claude_service.py`: Anthropic Claude API 호출, 프롬프트 관리, 수식 매핑 결합
- `gemini_service.py`: Google Gemini API 호출 — `analyze_graph()` (그래프 분석), `recognize_handwriting()` (손필기 인식)
- `graph_service.py`: Claude 출력의 `-그래프-` 태그를 Matplotlib PNG로 변환 (`process_graphs_in_text()`)
- `hwpx_service.py`: HWPX 파일 파싱(`read_hwpx()`), 문제 분리(`split_problems()`), HWPX 생성(`create_hwpx()`)
- `history_service.py`: 작업 결과를 로컬 파일에 저장/조회/삭제
- `hwp_converter.py`: HWP 변환 유틸리티

### 그래프 생성 시스템

Claude가 출력에 `-그래프-` / `-그래프끝-` 태그를 포함하면 `graph_service.process_graphs_in_text()`가 Matplotlib로 이미지를 생성.  
태그 내 지원 키: `함수:`, `x범위:`, `y범위:`, `포인트:`, `라벨:`, `점선:`, `점근선:`, `음영:`, `직선:`, `원:`, `격자:`  
그래프 스타일은 `backend/data/graph_style_profile.json`의 프로파일 기반 (수능/교과서 스타일).

### 수식 출력 형식

Claude 출력에서 수식은 `[한글수식코드]` 형태. 프론트엔드 `SolutionDisplay.jsx`가 `[...]`를 파싱하여 클릭 복사 가능한 `[수식]` 버튼으로 렌더링.

## Hooks (자동 문법 검사)

`.claude/settings.json`에 PostToolUse hook이 설정되어 있음:
- Python 파일(.py) 수정/생성 시 자동으로 `py_compile` 실행
- 문법 에러가 있으면 즉시 감지됨

## Critical Rules

- **포트**: 백엔드 8001 (8000 아님, 좀비 프로세스 이슈)
- **--reload 금지**: 파일 업로드 시 서버가 재시작되어 응답이 끊김
- **Python 3.14**: anthropic >= 0.40.0 필요 (이전 버전 호환 안됨)
- **모델**: Sonnet(저렴, 빠름) / Opus(고품질, 비쌈) 선택 가능, 기본값 Sonnet
- **원본 정확성 가정**: 검증 기능 제거됨 — 원본 문제/해설은 정확하다고 가정하고 변형문제만 생성
- **한글 수식 규칙**: 상세 인코딩 규칙은 `/hmr` 스킬 참조
- **Gemini 모델**: `gemini-2.5-flash` 사용, API 키는 `backend/.env`의 `GEMINI_API_KEY`

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
