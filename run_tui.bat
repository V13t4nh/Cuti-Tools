@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
setlocal
cd /d "%~dp0"

title CUTI Ops Control Deck

call .\.venv\Scripts\python.exe scripts\cuti_tui.py

endlocal
