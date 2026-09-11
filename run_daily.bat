@echo off
setlocal
cd /d "%~dp0"

title CUTI Daily Pipeline

echo ======================================================================
echo  CHAY DAILY PIPELINE (Crawl, Settle, Images, Gemini Refine)
echo ======================================================================
call .\.venv\Scripts\python.exe scripts\run_daily.py

echo.
echo ======================================================================
echo  Daily pipeline ket thuc voi ma: %ERRORLEVEL%
echo ======================================================================
pause
endlocal
