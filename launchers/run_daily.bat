@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

title CUTI Daily Pipeline

echo ======================================================================
echo  CHAY DAILY PIPELINE (Crawl, Detail, Gallery, Settle, Images, Refine)
echo ======================================================================
call "%PROJECT_ROOT%\.venv\Scripts\python.exe" "%PROJECT_ROOT%\scripts\run_daily.py"

echo.
echo ======================================================================
echo  Daily pipeline ket thuc voi ma: %ERRORLEVEL%
echo ======================================================================
pause
endlocal
