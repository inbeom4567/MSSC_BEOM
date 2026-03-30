# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

수학 유사문항 생성기 - 고등학교 수학 문제/해설 이미지를 입력하면 유사문항과 풀이를 한글 수식입력기 코드로 생성하는 웹앱.

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
```

- **프론트엔드**: `http://localhost:8001`로 직접 API 호출 (Vite 프록시 미사용)
- **백엔드**: FastAPI, 포트 8001 고정, `--reload` 사용 금지
- **CORS**: `allow_origins=["*"]` (개발환경)

### 핵심 API 엔드포인트

| Endpoint | Method | 기능 |
|----------|--------|------|
| `/api/generate` | POST | 유사문항 생성 (이미지2장 + variant_type + difficulty + model) |
| `/api/solve-variant` | POST | 변형문항 풀이 (이미지3장 + model) |
| `/api/prompt-feedback` | POST | 프롬프트 피드백 → 규칙 자동 추가 |

### 프론트엔드 탭 구조

- **탭1 (TabCreateVariant)**: 원본문제+해설 → 옵션(숫자/아이디어변형, 난이도, 모델) → 유사문항 생성
- **탭2 (TabSolveVariant)**: 원본문제+해설+변형문항 → 원본 해설 스타일로 풀이 작성
- **탭3 (TabPromptEdit)**: 사용자 피드백 → 프롬프트에 규칙 자동 추가

### 프롬프트 시스템

- `backend/prompts/solve_prompt.txt`: 유사문항 생성용 시스템 프롬프트
- `backend/prompts/variant_solve_prompt.txt`: 변형문항 풀이용 시스템 프롬프트
- `backend/data/hwp_math_mapping.json`: 수식 매핑 사전 → 프롬프트에 자동 결합됨 (`ClaudeService._load_mapping_reference()`)
- 프롬프트 파일 수정 시 서버 재시작 불필요 (피드백 API가 `reload_prompts()` 호출)

### 수식 출력 형식

Claude 출력에서 수식은 `[한글수식코드]` 형태. 프론트엔드 `SolutionDisplay.jsx`가 `[...]`를 파싱하여 클릭 복사 가능한 `[수식]` 버튼으로 렌더링.

## Critical Rules

- **포트**: 백엔드 8001 (8000 아님, 좀비 프로세스 이슈)
- **--reload 금지**: 파일 업로드 시 서버가 재시작되어 응답이 끊김
- **Python 3.14**: anthropic >= 0.40.0 필요 (이전 버전 호환 안됨)
- **모델**: Sonnet(저렴, 빠름) / Opus(고품질, 비쌈) 선택 가능, 기본값 Sonnet
- **원본 정확성 가정**: 검증 기능 제거됨 — 원본 문제/해설은 정확하다고 가정하고 변형문제만 생성
- **수식 규칙**: ±는 `+-` (pm 아님), 괄호는 `left( right)`, 수식 세로 배치, 어림값 금지
