@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

title CUTI Development Launcher

echo ======================================================================
echo  KHOI DONG 2 TIEN TRINH:
echo  1. Daily Pipeline (Crawl, Detail, Gallery, Settle, Images, Refine)
echo  2. Frontend Dev Server (FastAPI 8000 + Vite 5173)
echo ======================================================================

start "CUTI - Daily Pipeline" cmd /k "cd /d ""%PROJECT_ROOT%"" ^&^& ""%PROJECT_ROOT%\.venv\Scripts\python.exe"" ""%PROJECT_ROOT%\scripts\run_daily.py"""
start "CUTI - Frontend Dev" cmd /k "cd /d ""%PROJECT_ROOT%"" ^&^& ""%PROJECT_ROOT%\.venv\Scripts\python.exe"" ""%PROJECT_ROOT%\scripts\run_frontend.py"" dev"

echo.
echo [v] Da mo 2 cua so rieng cho pipeline va frontend dev.
endlocal
