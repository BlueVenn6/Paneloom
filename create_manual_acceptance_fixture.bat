@echo off
setlocal
cd /d "%~dp0"

if not exist "%~dp0.desktop-venv\Scripts\python.exe" (
  echo Paneloom desktop Python environment is missing.
  pause
  exit /b 1
)

"%~dp0.desktop-venv\Scripts\python.exe" "%~dp0scripts\create_manual_acceptance_fixture.py"
if errorlevel 1 (
  echo.
  echo The manual acceptance fixture could not be created.
  pause
  exit /b 1
)

echo.
echo The non-billed manual acceptance fixture is ready. Start Paneloom to use it.
pause
endlocal
