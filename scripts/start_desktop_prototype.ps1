$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".desktop-venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
  throw "Desktop prototype dependencies are missing. Create .desktop-venv and install desktop/requirements.txt first."
}

& $python (Join-Path $root "desktop\launcher.py")
exit $LASTEXITCODE
