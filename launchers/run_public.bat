@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

title CUTI Public Launcher

echo ======================================================================
echo  CUTI DECISION TERMINAL - PRODUCTION PREVIEW + CLOUDFLARE TUNNEL
echo ======================================================================
echo.
echo  Backend API: http://127.0.0.1:8000
echo  Frontend production preview: http://127.0.0.1:4173
echo.

set "CLOUDFLARED_BIN=cloudflared"
if exist "%PROJECT_ROOT%\var\cloudflared.exe" set "CLOUDFLARED_BIN=%PROJECT_ROOT%\var\cloudflared.exe"

start "CUTI - Cloudflare Tunnel" cmd /k "cd /d ""%PROJECT_ROOT%"" ^&^& echo Dang ket noi Cloudflare Tunnel... ^&^& ""%CLOUDFLARED_BIN%"" tunnel --url http://127.0.0.1:4173"
call "%PROJECT_ROOT%\.venv\Scripts\python.exe" "%PROJECT_ROOT%\scripts\run_frontend.py" preview

pause
endlocal
