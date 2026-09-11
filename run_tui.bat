@echo off
setlocal
cd /d "%~dp0"

title CUTI Ops Control Deck

call .\.venv\Scripts\python.exe scripts\cuti_tui.py

endlocal
