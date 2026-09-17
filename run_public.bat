@echo off
setlocal
cd /d "%~dp0"

title CUTI Public Launcher

echo ======================================================================
echo  CUTI DECISION TERMINAL - PRODUCTION PREVIEW + CLOUDFLARE TUNNEL
echo ======================================================================
echo.
echo  [1] He thong se khoi dong:
echo      - Backend API Server  : http://127.0.0.1:8000
echo      - Frontend Production : http://127.0.0.1:4173
echo.
echo  [2] Khoi dong Cloudflare Tunnel o cua so rieng de lay URL...
echo.

set CLOUDFLARED_BIN=cloudflared
if exist ".\var\cloudflared.exe" set CLOUDFLARED_BIN=.\var\cloudflared.exe

:: Mo cua so Cloudflare Tunnel tu dong ket noi toi port 4173
start "CUTI - Cloudflare Tunnel" cmd /k "cd /d "%~dp0" && echo Dang ket noi Cloudflare Tunnel... && %CLOUDFLARED_BIN% tunnel --url http://127.0.0.1:4173"

:: Chay he thong Frontend Preview + Backend
if exist ".\.venv\Scripts\python.exe" (
    .\.venv\Scripts\python.exe scripts\run_frontend.py preview
) else (
    python scripts\run_frontend.py preview
)

pause
