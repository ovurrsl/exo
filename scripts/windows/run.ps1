# Start exo on Windows from a source checkout.
#
# Prerequisites: `uv sync --extra mlx-cpu` (or `--extra mlx-cuda13` with the CUDA
# MLX wheel) has been run, so .venv holds the Windows MLX build with the ring backend.
#
# Usage:
#   .\scripts\windows\run.ps1
#   .\scripts\windows\run.ps1 -v --api-port 52415
#
# On a CUDA node the model weights live in GPU memory, but exo reports system RAM
# to the master by default. Unless OVERRIDE_MEMORY_MB is already set, this script
# sets it to the GPU's free memory minus a fixed 2.5 GiB reserve (KV cache, prefill
# logits, CUDA context), so the master never places more on this node than the GPU
# can hold. Windows does not fail an over-full GPU: it silently spills into shared
# system memory and generation becomes very slow.
#
# In a cluster with macOS nodes, also set EXO_MEMORY_THRESHOLD to the Mac's default
# (0.70 for a 16 GB Mac, 0.75 for 32 GB, 0.80 for 64 GB+) so every rank evicts the
# prefix cache at the same point.
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
    Write-Error 'No .venv found. Run `uv sync --python 3.13 --extra mlx-cpu` (or --extra mlx-cuda13) first.'
}

$GpuReserveMiB = 2560

if ((-not $env:OVERRIDE_MEMORY_MB -or -not $env:MLX_PTX_CACHE_DIR) -and (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    $mlxInfo = & $python -c "import mlx.core as mx; print(mx.cuda.is_available(), mx.__version__)" 2>$null
    if ($mlxInfo -match '^True (\S+)$') {
        $mlxVersion = $Matches[1]
        if (-not $env:OVERRIDE_MEMORY_MB) {
            $freeMiB = [int]((nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | Select-Object -First 1).Trim())
            $env:OVERRIDE_MEMORY_MB = [string][math]::Max(0, $freeMiB - $GpuReserveMiB)
            Write-Host "CUDA node: reporting $($env:OVERRIDE_MEMORY_MB) MB available (GPU free memory minus $GpuReserveMiB MB)."
        }
        if (-not $env:MLX_PTX_CACHE_DIR) {
            $computeCap = (nvidia-smi --query-gpu=compute_cap --format=csv,noheader | Select-Object -First 1).Trim()
            $env:MLX_PTX_CACHE_DIR = Join-Path $env:LOCALAPPDATA "exo\mlx-kernel-cache\$mlxVersion-sm$($computeCap -replace '\.', '')"
        }
    }
}

& $exo @args
exit $LASTEXITCODE
