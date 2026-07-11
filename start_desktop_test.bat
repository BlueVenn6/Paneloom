@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_desktop_test.ps1"
if errorlevel 1 (
  echo.
  echo Paneloom desktop test could not start. The error above is the real startup result.
  pause
  exit /b 1
)

endlocal
exit /b 0
