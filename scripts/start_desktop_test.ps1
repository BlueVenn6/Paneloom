param(
  [switch]$Offline
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".desktop-venv\Scripts\python.exe"
$pythonw = Join-Path $root ".desktop-venv\Scripts\pythonw.exe"
$launcher = Join-Path $root "desktop\launcher.py"
$frontend = Join-Path $root "frontend\dist\index.html"
$runtimeState = Join-Path $env:LOCALAPPDATA "Paneloom\temp\desktop-test-runtime.json"

foreach ($required in @($python, $pythonw, $launcher, $frontend)) {
  if (-not (Test-Path -LiteralPath $required)) {
    throw "Paneloom desktop test prerequisite is missing: $required"
  }
}

& $python -c "import fastapi, uvicorn, webview" 2>$null
if ($LASTEXITCODE -ne 0) {
  throw "Paneloom desktop Python dependencies are incomplete."
}

$stateDirectory = Split-Path -Parent $runtimeState
New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null
Remove-Item -LiteralPath $runtimeState -Force -ErrorAction SilentlyContinue

$previousStatePath = $env:PANELOOM_RUNTIME_STATE_PATH
$previousOffline = $env:PANELOOM_FORCE_OFFLINE
try {
  $env:PANELOOM_RUNTIME_STATE_PATH = $runtimeState
  $env:PANELOOM_FORCE_OFFLINE = if ($Offline) { "1" } else { "0" }
  $process = Start-Process `
    -FilePath $pythonw `
    -ArgumentList @("`"$launcher`"") `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -PassThru
} finally {
  $env:PANELOOM_RUNTIME_STATE_PATH = $previousStatePath
  $env:PANELOOM_FORCE_OFFLINE = $previousOffline
}

$deadline = [DateTime]::UtcNow.AddSeconds(120)
while ([DateTime]::UtcNow -lt $deadline) {
  if ($process.HasExited) {
    throw "Paneloom desktop test exited during startup. Check %LOCALAPPDATA%\Paneloom\logs\desktop-startup.log."
  }
  try {
    $state = Get-Content -LiteralPath $runtimeState -Raw | ConvertFrom-Json
    if ($state.status -eq "window_ready") {
      $mode = if ($Offline) { "offline" } else { "online" }
      Write-Host "Paneloom desktop test window is ready in $mode mode on its private loopback service."
      exit 0
    }
    if ($state.status -eq "stopped") {
      throw "Paneloom desktop test stopped before the window became ready."
    }
  } catch [System.IO.IOException], [System.Management.Automation.ItemNotFoundException], [System.ArgumentException] {
    # The launcher replaces this small state file atomically; retry while it is being published.
  }
  Start-Sleep -Milliseconds 200
}

throw "Paneloom desktop test did not open within 120 seconds."
