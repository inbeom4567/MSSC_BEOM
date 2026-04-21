@echo off
REM 유사문제 찾기 GUI 실행기
REM .venv가 있으면 venv의 pythonw, 없으면 시스템 pythonw 사용 (콘솔 창 안 뜸)

setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py
) else (
    start "" pythonw main.py
)

endlocal
