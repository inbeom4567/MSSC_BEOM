$base = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  수학 유사문항 생성기 시작" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/2] 백엔드 서버 시작 중..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$base\backend'; python -m uvicorn main:app --port 8001"

Start-Sleep -Seconds 3

Write-Host "[2/2] 프론트엔드 서버 시작 중..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$base\frontend'; npm run dev"

Start-Sleep -Seconds 4

Write-Host ""
Write-Host "브라우저를 열고 있습니다..." -ForegroundColor Green
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  서버가 실행 중입니다!" -ForegroundColor Cyan
Write-Host "  종료: 열린 PowerShell 창들을 닫으세요" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
