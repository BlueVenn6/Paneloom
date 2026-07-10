$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backendPid = Join-Path $root "logs\backend-dev.pid"
$frontendPid = Join-Path $root "logs\frontend-dev.pid"

New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null

function Stop-OldProcess($pidPath) {
  if (Test-Path $pidPath) {
    $value = Get-Content $pidPath -ErrorAction SilentlyContinue
    if ($value) {
      $tracked = Get-CimInstance Win32_Process -Filter "ProcessId = $([int]$value)" -ErrorAction SilentlyContinue
      if ($tracked -and $tracked.CommandLine -like "*$root*") {
        Stop-Process -Id ([int]$value) -Force -ErrorAction SilentlyContinue
      }
    }
  }
}

Stop-OldProcess $backendPid
Stop-OldProcess $frontendPid

foreach ($port in @(8000, 5173)) {
  if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $port is already in use. Stop that service explicitly or choose another port."
  }
}

$backend = Start-Process `
  -FilePath "python" `
  -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000") `
  -WorkingDirectory $root `
  -PassThru `
  -WindowStyle Hidden
$backend.Id | Set-Content $backendPid

$frontend = Start-Process `
  -FilePath "npm" `
  -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173") `
  -WorkingDirectory (Join-Path $root "frontend") `
  -PassThru `
  -WindowStyle Hidden
$frontend.Id | Set-Content $frontendPid

Start-Sleep -Seconds 5
Start-Process "http://127.0.0.1:5173"
Write-Host "Paneloom local browser workspace is starting:"
Write-Host "Backend:  http://127.0.0.1:8000"
Write-Host "Frontend: http://127.0.0.1:5173"
