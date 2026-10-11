# Compile the actual patched MLX socket implementation without importing MLX/CUDA.
param(
    [Parameter(Mandatory)] [string]$MlxSrc,
    [Parameter(Mandatory)] [string]$VsInstallPath,
    [string]$OutputDirectory = (Join-Path $env:TEMP 'exo-tcp-ownership'),
    [switch]$Loopback
)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $MlxSrc).Path
$compilerSetup = Join-Path $VsInstallPath 'VC\Auxiliary\Build\vcvars64.bat'
if (-not (Test-Path -LiteralPath $compilerSetup)) { throw 'vcvars64.bat missing' }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$output = (Resolve-Path -LiteralPath $OutputDirectory).Path
$test = Join-Path $PSScriptRoot 'check_tcp_ownership.cpp'
$implementation = Join-Path $source 'mlx\distributed\utils.cpp'
$exe = Join-Path $output 'check_tcp_ownership.exe'
# Reject cmd expansion and quoting characters in caller-supplied paths.
foreach ($path in @($source, $compilerSetup, $output, $test, $implementation, $exe)) {
    if ($path -match '["%\r\n!&|<>^]') { throw "Unsupported build path: $path" }
}
Push-Location $output
try {
    $command = 'call "{0}" >nul && cl /DNOMINMAX /nologo /EHsc /std:c++17 /I"{1}" "{2}" "{3}" /Fe:"{4}" /link ws2_32.lib' -f $compilerSetup, $source, $test, $implementation, $exe
    & $env:ComSpec /d /s /c $command
    if ($LASTEXITCODE -ne 0) { throw "Native compilation failed: $LASTEXITCODE" }
    if ($Loopback) { & $exe --loopback } else { & $exe }
    if ($LASTEXITCODE -ne 0) { throw "TCP ownership regression failed: $LASTEXITCODE" }
} finally { Pop-Location }

