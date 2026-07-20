param(
  [string]$BaselineTag = "v0.1.0-beta.1-functional-baseline"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".desktop-venv\Scripts\python.exe"
$frontend = Join-Path $root "frontend"
$generated = Join-Path $root "packaging\generated"
$cache = Join-Path $root "packaging\cache"
$work = Join-Path $root "packaging\work"
$dist = Join-Path $work "dist"
$stage = Join-Path $dist "Paneloom"
$artifactRoot = Join-Path $root "artifacts\windows"
$installerDir = Join-Path $artifactRoot "installer"
$manifestPath = Join-Path $artifactRoot "build-manifest.json"
$webViewBootstrapper = Join-Path $cache "MicrosoftEdgeWebview2Setup.exe"
$webViewUrl = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
$nsisCompiler = Join-Path ${env:ProgramFiles(x86)} "NSIS\makensis.exe"

function Assert-UnderRoot([string]$Path) {
  $full = [IO.Path]::GetFullPath($Path)
  $rootFull = [IO.Path]::GetFullPath($root).TrimEnd('\') + '\'
  if (-not $full.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to modify a path outside the repository: $full"
  }
}

function Invoke-Step([string]$Name, [scriptblock]$Command) {
  Write-Host "==> $Name"
  & $Command
  if ($LASTEXITCODE -ne 0) {
    throw "$Name failed with exit code $LASTEXITCODE."
  }
}

Set-Location $root
foreach ($required in @($python, $nsisCompiler, (Join-Path $frontend "package-lock.json"))) {
  if (-not (Test-Path -LiteralPath $required)) {
    throw "Required packaging input is missing: $required"
  }
}

$status = git status --porcelain
if ($status) {
  throw "The worktree must be clean before packaging.`n$status"
}
$packagingCommit = (git rev-parse HEAD).Trim()
$baselineCommit = (git rev-list -n 1 $BaselineTag).Trim()
if (-not $baselineCommit) {
  throw "The frozen baseline tag does not exist: $BaselineTag"
}
$releaseSource = Get-Content -LiteralPath (Join-Path $root "release-source.json") -Raw | ConvertFrom-Json
if ($releaseSource.frozen_business_tag -ne $BaselineTag -or
    $releaseSource.frozen_business_commit -ne $baselineCommit) {
  throw "release-source.json does not match the frozen business tag."
}
$packagingSourceTagCommit = (git rev-list -n 1 $releaseSource.packaging_source_tag).Trim()
if (-not $packagingSourceTagCommit -or
    $packagingSourceTagCommit -ne $releaseSource.packaging_source_commit) {
  throw "The packaging source tag does not match release-source.json."
}
git merge-base --is-ancestor $releaseSource.packaging_source_commit $packagingCommit
if ($LASTEXITCODE -ne 0) {
  throw "The recorded packaging source is not an ancestor of the current release commit."
}

$allowedChanges = @(
  ".gitignore",
  ".github/CODEOWNERS",
  ".github/workflows/ci.yml",
  "CHANGELOG.md",
  "README.md",
  "README.en.md",
  "README.ja.md",
  "README.ko.md",
  "README.zh-CN.md",
  "THIRD_PARTY_LICENSES.md",
  "THIRD_PARTY_NOTICES.md",
  "docs/open_source_release_readiness_2026-07-20.md",
  "docs/screenshots/",
  "docs/windows_installer_validation_2026-07-20.md",
  "packaging/",
  "release-source.json",
  "requirements-build.txt",
  "requirements-lock.txt",
  "sbom/",
  "scripts/build_windows_installer.ps1",
  "scripts/capture_readme_screenshots.py",
  "scripts/generate_release_metadata.py"
)
$unexpected = @(
  git diff --name-only "$baselineCommit..$packagingCommit" |
    Where-Object {
      $path = $_
      -not ($allowedChanges | Where-Object { $path -eq $_ -or $path.StartsWith($_) })
    }
)
if ($unexpected.Count -gt 0) {
  throw "Business source differs from the frozen baseline:`n$($unexpected -join "`n")"
}

Invoke-Step "Repository hygiene" { & $python scripts\check_repository_hygiene.py }
Invoke-Step "Python lint" { & $python -m ruff check backend api desktop scripts tests packaging }
Invoke-Step "Python tests" { & $python -m unittest discover -s tests -v }
Invoke-Step "Python dependency audit" { & $python -m pip_audit --path .desktop-venv\Lib\site-packages }
Invoke-Step "Frontend clean install" { Push-Location $frontend; try { npm ci } finally { Pop-Location } }
Invoke-Step "Frontend check and production build" { Push-Location $frontend; try { npm run check } finally { Pop-Location } }
Invoke-Step "Frontend dependency audit" { Push-Location $frontend; try { npm audit --audit-level=moderate } finally { Pop-Location } }

foreach ($path in @($generated, $work, $artifactRoot)) {
  Assert-UnderRoot $path
  if (Test-Path -LiteralPath $path) {
    Remove-Item -LiteralPath $path -Recurse -Force
  }
  New-Item -ItemType Directory -Path $path -Force | Out-Null
}
New-Item -ItemType Directory -Path $cache -Force | Out-Null
New-Item -ItemType Directory -Path $installerDir -Force | Out-Null

$version = (Get-Content -LiteralPath (Join-Path $root "VERSION") -Raw).Trim()
$buildTime = [DateTime]::UtcNow.ToString("o")
$buildInfo = [ordered]@{
  product = "Paneloom"
  version = $version
  baseline_tag = $BaselineTag
  baseline_commit = $baselineCommit
  packaging_source_tag = $releaseSource.packaging_source_tag
  packaging_source_commit = $releaseSource.packaging_source_commit
  packaging_commit = $packagingCommit
  open_source_tag = $releaseSource.open_source_tag
  built_at_utc = $buildTime
  python = (& $python --version 2>&1).ToString()
  pyinstaller = (& $python -m PyInstaller --version).Trim()
  nsis = "3.12"
}
$buildInfo | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $generated "build-info.json") -Encoding UTF8

if (-not (Test-Path -LiteralPath $webViewBootstrapper)) {
  Write-Host "==> Download signed Microsoft WebView2 bootstrapper"
  Invoke-WebRequest -Uri $webViewUrl -OutFile $webViewBootstrapper -UseBasicParsing
}
$signature = Get-AuthenticodeSignature -LiteralPath $webViewBootstrapper
if ($signature.Status -ne "Valid" -or $signature.SignerCertificate.Subject -notmatch "Microsoft") {
  throw "The WebView2 bootstrapper does not have a valid Microsoft signature."
}

Invoke-Step "PyInstaller one-folder build" {
  & $python -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath $dist `
    --workpath (Join-Path $work "build") `
    (Join-Path $root "packaging\paneloom.spec")
}
if (-not (Test-Path -LiteralPath (Join-Path $stage "Paneloom.exe"))) {
  throw "PyInstaller did not create the expected Paneloom.exe."
}

$installerPath = Join-Path $installerDir "Paneloom-$version-OpenSource-Windows-x64-Setup.exe"
Invoke-Step "NSIS installer" {
  & $nsisCompiler `
    "/INPUTCHARSET" `
    "UTF8" `
    "/DSTAGE_DIR=$stage" `
    "/DOUTPUT_FILE=$installerPath" `
    "/DSOURCE_ROOT=$root" `
    "/DWEBVIEW_BOOTSTRAPPER=$webViewBootstrapper" `
    "/DAPP_VERSION=$version" `
    (Join-Path $root "packaging\paneloom.nsi")
}

$installer = Get-Item -LiteralPath $installerPath -ErrorAction SilentlyContinue
if (-not $installer) {
  throw "NSIS did not create an installer."
}
$application = Get-Item -LiteralPath (Join-Path $stage "Paneloom.exe")
$releaseEvidencePaths = @(
  "THIRD_PARTY_LICENSES.md",
  "THIRD_PARTY_NOTICES.md",
  "sbom/frontend.cdx.json",
  "sbom/python-build.cdx.json",
  "sbom/python-runtime.cdx.json"
)
$releaseEvidence = foreach ($relativePath in $releaseEvidencePaths) {
  $evidencePath = Join-Path $root $relativePath
  if (-not (Test-Path -LiteralPath $evidencePath)) {
    throw "Release evidence is missing: $relativePath"
  }
  $evidence = Get-Item -LiteralPath $evidencePath
  [ordered]@{
    path = $relativePath.Replace("\", "/")
    size = $evidence.Length
    sha256 = (Get-FileHash -LiteralPath $evidence.FullName -Algorithm SHA256).Hash
  }
}
$manifest = [ordered]@{
  product = "Paneloom"
  version = $version
  baseline_tag = $BaselineTag
  baseline_commit = $baselineCommit
  packaging_source_tag = $releaseSource.packaging_source_tag
  packaging_source_commit = $releaseSource.packaging_source_commit
  packaging_commit = $packagingCommit
  open_source_tag = $releaseSource.open_source_tag
  built_at_utc = $buildTime
  signed = $false
  release_evidence = $releaseEvidence
  webview2_bootstrapper = [ordered]@{
    source = $webViewUrl
    signer = $signature.SignerCertificate.Subject
    sha256 = (Get-FileHash -LiteralPath $webViewBootstrapper -Algorithm SHA256).Hash
  }
  application = [ordered]@{
    path = $application.FullName
    size = $application.Length
    modified_utc = $application.LastWriteTimeUtc.ToString("o")
    sha256 = (Get-FileHash -LiteralPath $application.FullName -Algorithm SHA256).Hash
  }
  installer = [ordered]@{
    path = $installer.FullName
    size = $installer.Length
    modified_utc = $installer.LastWriteTimeUtc.ToString("o")
    sha256 = (Get-FileHash -LiteralPath $installer.FullName -Algorithm SHA256).Hash
  }
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

Write-Host "Installer: $($installer.FullName)"
Write-Host "SHA-256: $($manifest.installer.sha256)"
Write-Host "Manifest: $manifestPath"
