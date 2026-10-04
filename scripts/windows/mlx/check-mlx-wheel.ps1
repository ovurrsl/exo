# Check an MLX install on Windows: that processes which used the GPU still exit with
# their own exit code (the v0.32.3 wheel without the wddm.cpp change exited with 2170),
# that a model file larger than 2 GiB loads (the cc3f3e60 wheel cannot), and that the
# ring backend works between processes on this machine. Prints one PASS/FAIL line per
# run and exits 1 if anything failed.
#
#   .\check-mlx-wheel.ps1                                  # exo's .venv
#   .\check-mlx-wheel.ps1 -Python C:\tmp\mlx-official\Scripts\python.exe
#   .\check-mlx-wheel.ps1 -LargeFile C:\path\to\model-00001-of-00002.safetensors
#   .\check-mlx-wheel.ps1 -Device cpu                      # without a GPU
param(
    # The interpreter whose MLX is checked. Default: exo's .venv.
    [string]$Python,
    [ValidateSet('gpu', 'cpu')] [string]$Device = 'gpu',
    # How often each exit-code check runs; the wrong exit code was not always the same.
    [int]$Runs = 5,
    # A safetensors file larger than 2 GiB, e.g. a shard of
    # mlx-community/Meta-Llama-3.1-8B-Instruct-8bit. Skipped when not given.
    [string]$LargeFile,
    # Ring group sizes to run on 127.0.0.1. Pass @() to skip.
    [int[]]$RingSizes = @(2, 3, 4),
    # A run that takes longer counts as hung and is killed.
    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = 'Stop'
$OnWindows = $env:OS -eq 'Windows_NT'
$ExoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
if (-not $Python) {
    $Python = if ($OnWindows) { Join-Path $ExoRoot '.venv\Scripts\python.exe' }
    else { Join-Path $ExoRoot '.venv/bin/python' }
}
if (-not (Test-Path $Python)) { throw "Python not found: $Python" }
$Python = (Resolve-Path $Python).Path

$WorkDir = Join-Path ([System.IO.Path]::GetTempPath()) ("mlx-check-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $WorkDir | Out-Null
$script:Failures = 0

function Write-Script([string]$Name, [string]$Code) {
    $path = Join-Path $WorkDir $Name
    # ASCII: Windows PowerShell 5.1 would otherwise write UTF-16 or a BOM.
    Set-Content -Path $path -Value $Code -Encoding Ascii
    return $path
}

function Stop-Tree([System.Diagnostics.Process]$Process) {
    # cmd does the redirection: under Windows PowerShell 5.1 a native command's
    # redirected stderr becomes an error record, which 'Stop' turns into a throw.
    if ($OnWindows) { & cmd /c "taskkill /T /F /PID $($Process.Id) >nul 2>&1" }
    else { Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue }
}

# Starts the script; with -Redirect its stdout and stderr go to files, which is how
# exo's runners and the earlier hang ran. Returns the process.
function Start-Check([string]$ScriptPath, [string]$Tag, [switch]$Redirect) {
    $arguments = @{
        FilePath     = $Python
        ArgumentList = "`"$ScriptPath`""
        NoNewWindow  = $true
        PassThru     = $true
    }
    if ($Redirect) {
        $arguments.RedirectStandardOutput = Join-Path $WorkDir "$Tag.out"
        $arguments.RedirectStandardError = Join-Path $WorkDir "$Tag.err"
    }
    $process = Start-Process @arguments
    # Windows PowerShell only fills in ExitCode if the handle was opened while the
    # process ran.
    $null = $process.Handle
    return $process
}

# Waits for the process and reports whether it exited with $Expected in time.
function Complete-Check([System.Diagnostics.Process]$Process, [string]$Label, [int]$Expected, [string]$Tag) {
    $finished = $Process.WaitForExit($TimeoutSeconds * 1000)
    if (-not $finished) {
        Stop-Tree $Process
        Write-Host "[FAIL] $Label`: no exit after $TimeoutSeconds s (killed)" -ForegroundColor Red
        $script:Failures++
        return
    }
    $Process.WaitForExit()
    $code = $Process.ExitCode
    $detail = '{0} (0x{0:X8})' -f $code
    $output = ''
    if ($Tag) {
        $files = @("$Tag.out", "$Tag.err") | ForEach-Object { Join-Path $WorkDir $_ } | Where-Object { Test-Path $_ }
        $output = ($files | ForEach-Object { Get-Content $_ -Raw }) -join ' '
        $output = ($output -replace '\s+', ' ').Trim()
        if ($output.Length -gt 200) { $output = $output.Substring($output.Length - 200) }
    }
    if ($code -eq $Expected) {
        Write-Host "[PASS] $Label`: exit $detail $output" -ForegroundColor Green
    }
    else {
        Write-Host "[FAIL] $Label`: exit $detail, expected $Expected $output" -ForegroundColor Red
        $script:Failures++
    }
}

$deviceExpression = "mx.$Device"

$info = Write-Script 'info.py' @"
import mlx.core as mx
mx.set_default_device($deviceExpression)
print("mlx", mx.__version__, "from", mx.__file__)
print("default device", mx.default_device())
print("ring available", mx.distributed.is_available("ring"))
"@
Write-Host "==> $Python" -ForegroundColor Cyan
& $Python $info
if ($LASTEXITCODE -ne 0) { throw "MLX does not import or has no $Device device (exit $LASTEXITCODE)" }
if ($OnWindows -and (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    & nvidia-smi --query-gpu=name,driver_version,driver_model.current --format=csv,noheader
}

$importOnly = Write-Script 'import_only.py' @"
import sys
import mlx.core as mx
sys.exit(7)
"@
$compute = Write-Script 'compute.py' @"
import sys
import mlx.core as mx
mx.set_default_device($deviceExpression)
a = mx.random.normal((2048, 2048))
b = (a @ a).sum()
mx.eval(b)
print("computed on", mx.default_device())
sys.exit(7)
"@

Write-Host "==> Exit codes ($Runs runs each, expected 7)" -ForegroundColor Cyan
for ($run = 1; $run -le $Runs; $run++) {
    Complete-Check (Start-Check $importOnly "import-$run") "import only, run $run" 7
    Complete-Check (Start-Check $compute "compute-$run") "$Device compute, run $run" 7
    $tag = "redirected-$run"
    Complete-Check (Start-Check $compute $tag -Redirect) "$Device compute with output to files, run $run" 7 $tag
}

if ($LargeFile) {
    Write-Host "==> Loading $LargeFile" -ForegroundColor Cyan
    $size = (Get-Item $LargeFile).Length
    Write-Host ('    {0:N2} GiB' -f ($size / 1GB))
    if ($size -le 2GB) { Write-Host '    (not larger than 2 GiB, so this does not test the 2 GiB limit)' -ForegroundColor Yellow }
    $env:MLX_CHECK_FILE = (Resolve-Path $LargeFile).Path
    $load = Write-Script 'load.py' @"
import os
import sys
import mlx.core as mx
mx.set_default_device($deviceExpression)
arrays = mx.load(os.environ["MLX_CHECK_FILE"])
mx.eval(list(arrays.values()))
print("loaded", len(arrays), "arrays")
sys.exit(7)
"@
    Complete-Check (Start-Check $load 'load' -Redirect) 'load large file' 7 'load'
    Remove-Item Env:\MLX_CHECK_FILE
}

if ($RingSizes.Count -gt 0) {
    $ring = Write-Script 'ring.py' @"
import sys
import mlx.core as mx
mx.set_default_device($deviceExpression)
group = mx.distributed.init(strict=True, backend="ring")
total = mx.distributed.all_sum(mx.ones((4096,)) * (group.rank() + 1))
mx.eval(total)
expected = group.size() * (group.size() + 1) / 2
ok = bool(mx.all(total == expected).item())
print("rank", group.rank(), "of", group.size(), "sum", total[0].item(), "expected", expected)
sys.exit(7 if ok else 1)
"@
    foreach ($size in $RingSizes) {
        Write-Host "==> Ring, $size ranks on 127.0.0.1" -ForegroundColor Cyan
        $ports = @()
        for ($rank = 0; $rank -lt $size; $rank++) {
            $listener = New-Object System.Net.Sockets.TcpListener ([System.Net.IPAddress]::Loopback, 0)
            $listener.Start()
            $ports += $listener.LocalEndpoint.Port
            $listener.Stop()
        }
        $hosts = ($ports | ForEach-Object { "[`"127.0.0.1:$_`"]" }) -join ','
        $hostfile = Join-Path $WorkDir "hosts-$size.json"
        Set-Content -Path $hostfile -Value "[$hosts]" -Encoding Ascii
        $env:MLX_HOSTFILE = $hostfile
        $processes = @()
        for ($rank = 0; $rank -lt $size; $rank++) {
            $env:MLX_RANK = "$rank"
            $processes += Start-Check $ring "ring-$size-$rank" -Redirect
        }
        Remove-Item Env:\MLX_RANK, Env:\MLX_HOSTFILE
        for ($rank = 0; $rank -lt $size; $rank++) {
            Complete-Check $processes[$rank] "ring $size ranks, rank $rank" 7 "ring-$size-$rank"
        }
    }
}

if ($script:Failures -eq 0) {
    Write-Host '==> All checks passed' -ForegroundColor Green
    Remove-Item -Recurse -Force $WorkDir
    exit 0
}
Write-Host "==> $($script:Failures) check(s) failed; outputs are in $WorkDir" -ForegroundColor Red
exit 1
