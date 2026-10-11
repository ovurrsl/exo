# Build per-user NSIS with the full frozen runtime and app-owned fixed WebView2.
param(
    [Parameter(Mandatory = $true)] [string]$MlxWheel,
    [string]$Python,
    [string]$VsInstallPath,
    [switch]$SkipRuntimeBuild,
    [switch]$SkipDashboardBuild,
    [string]$LargeFile,
    [string]$WebView2Archive,
    [switch]$RequireSignedUpdater
)
$ErrorActionPreference = 'Stop'
if ($RequireSignedUpdater -and (-not $env:TAURI_SIGNING_PRIVATE_KEY -or -not $env:EXO_WINDOWS_UPDATER_PUBLIC_KEY)) {
    throw 'TAURI_SIGNING_PRIVATE_KEY and EXO_WINDOWS_UPDATER_PUBLIC_KEY are required for a signed updater release'
}
$ExoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $Python) { $Python = Join-Path $ExoRoot '.venv\Scripts\python.exe' }
$Python = (Resolve-Path -LiteralPath $Python).Path
& (Join-Path $PSScriptRoot 'prepare-webview2.ps1') -Archive $WebView2Archive
if (-not $SkipRuntimeBuild) {
    & (Join-Path $PSScriptRoot 'build-runtime.ps1') -MlxWheel $MlxWheel -Python $Python -SkipDashboardBuild:$SkipDashboardBuild -LargeFile $LargeFile
}
$runtime = (Resolve-Path -LiteralPath (Join-Path $ExoRoot 'dist\windows\exo')).Path
& $Python (Join-Path $PSScriptRoot 'validate_runtime.py') --runtime $runtime
if ($LASTEXITCODE -ne 0) { throw 'Runtime files differ from their validated build manifest' }
if (-not (Test-Path -LiteralPath (Join-Path $runtime 'runtime-manifest.json'))) {
    throw 'The frozen runtime must pass build-runtime.ps1 before installer staging'
}
$runtimeManifest = Get-Content -LiteralPath (Join-Path $runtime 'runtime-manifest.json') -Raw | ConvertFrom-Json
if ($runtimeManifest.mlx.wheel_sha256 -ne (Get-FileHash -LiteralPath $MlxWheel -Algorithm SHA256).Hash.ToLower()) {
    throw 'Staged runtime was built from a different MLX wheel'
}
$runtimeExecutableHash = (Get-FileHash -LiteralPath (Join-Path $runtime 'exo.exe') -Algorithm SHA256).Hash.ToLower()
if ($runtimeManifest.binary_sha256.'exo.exe' -ne $runtimeExecutableHash) {
    throw 'The runtime executable differs from the validated manifest'
}
$env:EXO_WINDOWS_FIREWALL_RUNTIME_SHA256 = $runtimeExecutableHash
$destination = [System.IO.Path]::GetFullPath((Join-Path $ExoRoot 'app\windows\src-tauri\resources\runtime'))
$expectedResources = [System.IO.Path]::GetFullPath((Join-Path $ExoRoot 'app\windows\src-tauri\resources'))
if (-not $destination.StartsWith($expectedResources + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing staging outside desktop resources: $destination"
}
if (Test-Path -LiteralPath $destination) { Remove-Item -LiteralPath $destination -Recurse -Force }
New-Item -ItemType Directory -Path $destination -Force | Out-Null
Copy-Item -Path (Join-Path $runtime '*') -Destination $destination -Recurse -Force
& $Python (Join-Path $PSScriptRoot 'validate_runtime.py') --runtime $destination
if ($LASTEXITCODE -ne 0) { throw 'Staged runtime files differ from their validated build manifest' }
if ($VsInstallPath) {
    & cmd.exe /c "`"$VsInstallPath\VC\Auxiliary\Build\vcvarsall.bat`" x64 >NUL 2>NUL && set" | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') { Set-Item -Path "env:$($Matches[1])" -Value $Matches[2] }
    }
}
$localCargo = Join-Path (Split-Path $ExoRoot -Parent) 'deps\cargo'
$localRustup = Join-Path (Split-Path $ExoRoot -Parent) 'deps\rustup'
if (Test-Path -LiteralPath (Join-Path $localCargo 'bin\cargo.exe')) {
    $env:CARGO_HOME = $localCargo
    $env:RUSTUP_HOME = $localRustup
    $env:Path = "$(Join-Path $localCargo 'bin');$env:Path"
}
Push-Location (Join-Path $ExoRoot 'app\windows\src-tauri')
try {
    & cargo.exe build --release --features firewall-helper --bin exo-firewall-helper
    if ($LASTEXITCODE -ne 0) { throw 'Pinned Windows firewall helper build failed' }
    $firewallResources = Join-Path $ExoRoot 'app\windows\src-tauri\resources\firewall'
    New-Item -ItemType Directory -Path $firewallResources -Force | Out-Null
    Copy-Item -LiteralPath 'target\release\exo-firewall-helper.exe' -Destination $firewallResources -Force
} finally { Pop-Location }
Push-Location (Join-Path $ExoRoot 'app\windows')
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Windows desktop npm ci failed' }
    $buildArguments = @('run', 'tauri', '--', 'build', '--bundles', 'nsis')
    if (-not $env:TAURI_SIGNING_PRIVATE_KEY) {
        if ($RequireSignedUpdater) { throw 'TAURI_SIGNING_PRIVATE_KEY is required for signed updater artifacts' }
        $overrideDirectory = Join-Path $ExoRoot 'build\windows-runtime'
        New-Item -ItemType Directory -Path $overrideDirectory -Force | Out-Null
        $override = Join-Path $overrideDirectory 'unsigned-installer-config.json'
        '{"bundle":{"createUpdaterArtifacts":false}}' | Set-Content -LiteralPath $override -Encoding utf8
        $buildArguments += @('--config', $override)
        Write-Host 'Building an unsigned review installer; updater artifacts are disabled for this build.'
    }
    & npm.cmd @buildArguments
    if ($LASTEXITCODE -ne 0) { throw 'Windows desktop/offline NSIS build failed' }
    Write-Host 'Installer: app/windows/src-tauri/target/release/bundle/nsis' -ForegroundColor Green
} finally { Pop-Location }
