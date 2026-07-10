param(
  [switch]$SmokeTest
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".desktop-venv\Scripts\python.exe"
$pythonw = Join-Path $root ".desktop-venv\Scripts\pythonw.exe"
$launcher = Join-Path $root "desktop\launcher.py"
$frontend = Join-Path $root "frontend\dist\index.html"

if (-not (Test-Path $python) -or -not (Test-Path $pythonw)) {
  throw "Paneloom desktop runtime is missing. Install desktop/requirements.txt in .desktop-venv."
}
if (-not (Test-Path $frontend)) {
  throw "Paneloom production UI is missing. Build frontend/dist before production-like validation."
}

if ($SmokeTest) {
  & $python $launcher --window-smoke --no-single-instance
  exit $LASTEXITCODE
}

Start-Process `
  -FilePath $pythonw `
  -ArgumentList @($launcher) `
  -WorkingDirectory $root `
  -WindowStyle Hidden
