@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
setlocal
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

title CUTI Ops Control Deck - Daily Materialization + Refine

call "%PROJECT_ROOT%.venv\Scripts\python.exe" "%PROJECT_ROOT%scripts\cuti_tui.py"

endlocal
