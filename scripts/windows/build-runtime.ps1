# Produces a compilerless onedir runtime. Requires the reviewed wheel + provenance.
param(
    [Parameter(Mandatory = $true)] [string]$MlxWheel,
    [string]$Python,
    [switch]$SkipDashboardBuild,
    [string]$LargeFile,
    [switch]$ReuseAnalysisCache
)
$ErrorActionPreference = 'Stop'
$ExoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $Python) { $Python = Join-Path $ExoRoot '.venv\Scripts\python.exe' }
$Python = (Resolve-Path -LiteralPath $Python).Path
$MlxWheel = (Resolve-Path -LiteralPath $MlxWheel).Path
$provenancePath = $MlxWheel + '.provenance.json'
if (-not (Test-Path -LiteralPath $provenancePath)) { throw "Missing wheel provenance: $provenancePath" }
$provenance = Get-Content -LiteralPath $provenancePath -Raw | ConvertFrom-Json
$patch = Join-Path $PSScriptRoot 'mlx\mlx-windows-ring-v0.32.3.patch'
if ($provenance.upstream_commit -ne '64ea011cb65f14d9ce2737e60db9a4ae91ed7441' -or
    $provenance.patch_sha256 -ne (Get-FileHash $patch -Algorithm SHA256).Hash.ToLower() -or
    $provenance.wheel_sha256 -ne (Get-FileHash $MlxWheel -Algorithm SHA256).Hash.ToLower()) {
    throw 'MLX wheel/provenance/pinned patch mismatch'
}
$installedVersion = (& $Python -c 'import importlib.metadata; print(importlib.metadata.version("mlx"))').Trim()
if ($LASTEXITCODE -ne 0 -or -not ([System.IO.Path]::GetFileName($MlxWheel).StartsWith("mlx-$installedVersion-"))) {
    throw "Install exactly the reviewed wheel in the build environment first (currently mlx $installedVersion)"
}
Push-Location $ExoRoot
try {
    if (-not $SkipDashboardBuild) {
        Push-Location (Join-Path $ExoRoot 'dashboard')
        try {
            & npm.cmd ci
            if ($LASTEXITCODE -ne 0) { throw 'dashboard npm ci failed' }
            & npm.cmd run build
            if ($LASTEXITCODE -ne 0) { throw 'dashboard build failed' }
        } finally { Pop-Location }
    }
    $sourceInputs = Join-Path $ExoRoot 'build\windows-runtime\source-inputs.json'
    New-Item -ItemType Directory -Path (Split-Path $sourceInputs -Parent) -Force | Out-Null
    & $Python packaging/windows/record_inputs.py --root $ExoRoot --output $sourceInputs
    if ($LASTEXITCODE -ne 0) { throw 'Runtime source snapshot failed' }
    $pyinstallerArguments = @('-m', 'PyInstaller', '--noconfirm', '--distpath', 'dist/windows', '--workpath', 'build/windows-runtime')
    if (-not $ReuseAnalysisCache) { $pyinstallerArguments += '--clean' }
    $pyinstallerArguments += 'packaging/windows/exo.spec'
    & $Python @pyinstallerArguments
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller runtime build failed' }
    $runtime = Join-Path $ExoRoot 'dist\windows\exo'
    $gate = Join-Path $ExoRoot 'dist\windows\runtime-gates.json'
    $arguments = @('--runtime-check', '--device', 'gpu', '--output', $gate)
    if ($LargeFile) { $arguments += @('--large-file', (Resolve-Path -LiteralPath $LargeFile).Path) }
    & (Join-Path $runtime 'exo.exe') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Frozen runtime failed its compilerless/GPU/ring gate; see $gate" }
    & $Python packaging/windows/record_inputs.py --root $ExoRoot --output $sourceInputs --check
    if ($LASTEXITCODE -ne 0) { throw 'Source files changed while packaging; rebuild the runtime' }
    & $Python packaging/windows/write_manifest.py --runtime $runtime --wheel $MlxWheel --root $ExoRoot --gates $gate --source-inputs $sourceInputs
    if ($LASTEXITCODE -ne 0) { throw 'Runtime attestation failed' }
    Write-Host "Validated runtime: $runtime" -ForegroundColor Green
} finally { Pop-Location }
