@echo off
REM Similarity Finder GUI launcher
REM Uses py -3 (Python Launcher for Windows) to bypass the Microsoft Store python stub.
REM Console window stays open; errors are visible there.

setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    py -3 main.py
)

if errorlevel 1 (
    echo.
    echo [ERROR] Launch failed - exit code %errorlevel%
    echo Check the message above or contact the developer.
    pause
)

endlocal
