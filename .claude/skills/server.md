---
name: server
description: >
  MathSolution 서버 제어 스킬. 백엔드(FastAPI:8001)와 프론트엔드(Vite:5173) 시작/종료/재시작.
  "서버 재시작", "백엔드 켜줘", "프론트엔드 종료" 등 요청 시 사용.
---

# MathSolution 서버 제어

## 환경 정보

- **백엔드**: FastAPI, 포트 8001, WSL 내부에서 실행됨
- **프론트엔드**: Vite dev server, 포트 5173, WSL 내부에서 실행됨
- **프로젝트 경로**: `c:\Users\tnaak\OneDrive\바탕 화면\MathSolution`
- **WSL 경로**: `/mnt/c/Users/tnaak/OneDrive/바탕\ 화면/MathSolution`
- **주의**: `--reload` 절대 사용 금지 (파일 업로드 시 서버 재시작됨)

---

## 포트 8001 (백엔드) 종료

```bash
# WSL 내부에서 포트 8001 프로세스 종료
wsl -e sh -c "fuser -k 8001/tcp 2>/dev/null && echo killed || echo not_found"
```

종료 확인:
```bash
wsl -e sh -c "ss -tlnp 2>/dev/null | grep 8001 || echo 'port 8001 free'"
```

## 포트 5173 (프론트엔드) 종료

```bash
wsl -e sh -c "fuser -k 5173/tcp 2>/dev/null && echo killed || echo not_found"
```

---

## 백엔드 시작

```bash
cd "c:\Users\tnaak\OneDrive\바탕 화면\MathSolution\backend" && python -m uvicorn main:app --port 8001 &
```

시작 확인 (3초 대기 후):
```bash
sleep 3 && curl -s http://localhost:8001/api/health
```

정상이면 `{"status":"ok"}` 반환.

## 프론트엔드 시작

```bash
cd "c:\Users\tnaak\OneDrive\바탕 화면\MathSolution\frontend" && npm run dev &
```

---

## 전체 재시작 절차

1. 백엔드 종료
2. 프론트엔드 종료
3. 백엔드 시작 (백그라운드)
4. 프론트엔드 시작 (백그라운드)
5. 헬스체크로 백엔드 확인

```bash
# 1. 종료
wsl -e sh -c "fuser -k 8001/tcp 2>/dev/null; fuser -k 5173/tcp 2>/dev/null; echo done"

# 2. 백엔드 시작
cd "c:\Users\tnaak\OneDrive\바탕 화면\MathSolution\backend" && python -m uvicorn main:app --port 8001 &

# 3. 프론트엔드 시작
cd "c:\Users\tnaak\OneDrive\바탕 화면\MathSolution\frontend" && npm run dev &

# 4. 확인
sleep 4 && curl -s http://localhost:8001/api/health
```

---

## 주의사항

- 백엔드 프로세스는 WSL(`wslrelay`) 통해 포워딩됨 — Windows의 PID가 아닌 WSL 내부 PID를 종료해야 함
- `fuser -k` 명령이 `not_found`를 반환하면 이미 종료된 것
- 포트 2880(wslrelay), 24192(Docker)는 시스템 프로세스 — 절대 종료하지 말 것
