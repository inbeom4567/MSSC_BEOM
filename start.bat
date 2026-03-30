@echo off
chcp 65001 >nul
echo ==========================================
echo   수학 유사문항 생성기 시작
echo ==========================================
echo.

:: 백엔드 시작
echo [1/2] 백엔드 서버 시작 중...
start "백엔드 서버" cmd /k "cd /d %~dp0backend && python -m uvicorn main:app --port 8001"

:: 2초 대기
timeout /t 2 /nobreak >nul

:: 프론트엔드 시작
echo [2/2] 프론트엔드 서버 시작 중...
start "프론트엔드 서버" cmd /k "cd /d %~dp0frontend && npm run dev"

:: 3초 대기 후 브라우저 열기
timeout /t 3 /nobreak >nul
echo.
echo 브라우저를 열고 있습니다...
start http://localhost:5173

echo.
echo ==========================================
echo   서버가 실행 중입니다!
echo   종료하려면 열린 터미널 창들을 닫으세요.
echo ==========================================
pause
