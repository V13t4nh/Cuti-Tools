@echo off
setlocal
cd /d "%~dp0"

title CUTI Launcher

echo ======================================================================
echo  KHOI DONG SONG SONG 2 TIEN TRINH RIENG BIET:
echo  1. CUTI Daily Pipeline (Crawl, Settle, Images, Gemini Refine)
echo  2. CUTI Frontend Dev Server (FastAPI 8000 + Vite 5173)
echo ======================================================================

:: 1. Mo cua so rieng chay Daily Pipeline (khi chay xong giu nguyen cua so de xem log)
start "CUTI - Daily Pipeline" cmd /k "cd /d "%~dp0" && .\.venv\Scripts\python.exe scripts\run_daily.py"

:: 2. Mo cua so rieng chay Frontend Dev Server (API Backend 8000 + Vite Hot Reload 5173)
start "CUTI - Frontend Dev" cmd /k "cd /d "%~dp0" && .\.venv\Scripts\python.exe scripts\run_frontend.py dev"

echo.
echo [v] Da kich hoat thanh cong ca 2 tien trinh chay song song trong 2 cua so rieng!
echo     - Cua so 1: Dong bo du lieu, tai anh va Gemini Refine
echo     - Cua so 2: Backend API (http://127.0.0.1:8000) va Vite UI (http://127.0.0.1:5173)
echo.
