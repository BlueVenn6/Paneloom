$ErrorActionPreference = "SilentlyContinue"

$root = Split-Path -Parent $PSScriptRoot
$pidFiles = @(
  Join-Path $root "logs\backend-dev.pid",
  Join-Path $root "logs\frontend-dev.pid"
)

foreach ($pidPath in $pidFiles) {
  if (Test-Path $pidPath) {
    $value = Get-Content $pidPath
    if ($value) {
      $tracked = Get-CimInstance Win32_Process -Filter "ProcessId = $([int]$value)" -ErrorAction SilentlyContinue
      if ($tracked -and $tracked.CommandLine -like "*$root*") {
        Stop-Process -Id ([int]$value) -Force
        Write-Host "Stopped tracked Paneloom process $value"
      }
    }
  }
}
