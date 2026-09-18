@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" app.py --open-browser
if errorlevel 1 goto failed
exit /b 0
:failed
echo Startup failed. See docs\acceptance-guide.md for troubleshooting.
pause
exit /b 1
