# Start exo on Windows from a source checkout.
#
# Prerequisites: `uv sync --extra mlx-cuda13` has been run, so .venv holds the
# Windows MLX build (CUDA + ring backend) and the node advertises MlxCuda.
#
# Usage:
#   .\scripts\windows\run.ps1
#   .\scripts\windows\run.ps1 -v --api-port 52415
#
# On a CUDA node exo reports the GPU's memory to the master by itself (its free
# memory minus a 2.5 GiB reserve, read through NVML every second). Set
# OVERRIDE_MEMORY_MB to report a fixed amount instead.
#
# In a cluster with macOS nodes, also set EXO_MEMORY_THRESHOLD to the Mac's default
# (0.70 below 32 GB, 0.75 for 32 GB, 0.80 for 64 GB, 0.85 for 128 GB+) so every
# rank evicts the prefix cache at the same point.
#
# MLX compiles CUDA kernels on first use and caches them under %TEMP% by default,
# where Windows' Storage Sense deletes them; that makes the first request after a
# cleanup stall for 20-30 s. Unless MLX_PTX_CACHE_DIR is set, keep the cache under
# %LOCALAPPDATA%\exo, in a folder per MLX version (delete it after rebuilding the
# wheel with the same version string).

$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $Root

$exo = Join-Path $Root '.venv\Scripts\exo.exe'
$python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $exo)) {
    Write-Error 'No .venv found. Run `uv sync --python 3.13 --extra mlx-cuda13` first.'
}

if (-not $env:MLX_PTX_CACHE_DIR -and (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    # Windows PowerShell 5.1 turns a native command's stderr output into error
    # records, which 'Stop' makes fatal even with 2>$null, and MLX may log there.
    $ErrorActionPreference = 'Continue'
    $mlxInfo = & $python -c "import mlx.core as mx; print(mx.cuda.is_available(), mx.__version__)" 2>$null
    $mlxExitCode = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($mlxExitCode -eq 0 -and ($mlxInfo | Select-Object -Last 1) -match '^True (\S+)$') {
        $mlxVersion = $Matches[1]
        $computeCap = (nvidia-smi --query-gpu=compute_cap --format=csv,noheader | Select-Object -First 1).Trim()
        $env:MLX_PTX_CACHE_DIR = Join-Path $env:LOCALAPPDATA "exo\mlx-kernel-cache\$mlxVersion-sm$($computeCap -replace '\.', '')"
    }
}

& $exo @args
exit $LASTEXITCODE
