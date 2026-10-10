# Mandatory >2GiB, compilerless CPU/CUDA, exit-code, spawn and ring release gates.
param(
    [string]$Python,
    [ValidateSet('gpu', 'cpu')] [string]$Device = 'gpu',
    [int]$Runs = 3,
    [string]$LargeFile,
    [int[]]$RingSizes = @(2, 3, 4),
    [int]$TimeoutSeconds = 120,
    [string]$Output
)
$ErrorActionPreference = 'Stop'
$ExoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
if (-not $Python) { $Python = Join-Path $ExoRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $Python)) { throw "Python not found: $Python" }
$arguments = @((Join-Path $PSScriptRoot 'check_mlx.py'), '--device', $Device,
    '--runs', "$Runs", '--timeout', "$TimeoutSeconds", '--ring-sizes')
foreach ($size in $RingSizes) { $arguments += "$size" }
if ($LargeFile) { $arguments += @('--large-file', (Resolve-Path -LiteralPath $LargeFile).Path) }
if ($Output) { $arguments += @('--output', [System.IO.Path]::GetFullPath($Output)) }
& $Python @arguments
if ($LASTEXITCODE -ne 0) { throw "MLX release gate failed (exit $LASTEXITCODE)" }
