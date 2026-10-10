# Stage the exact reviewed candidate used by the Windows-only uv source.
param(
    [Parameter(Mandatory = $true)] [string]$WheelPath
)
$ErrorActionPreference = 'Stop'
$ExoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$wheelName = 'mlx-0.32.3.dev20261009+win.3-cp313-cp313-win_amd64.whl'
$destinationDirectory = Join-Path $ExoRoot 'packaging\windows\wheels'
$trackedProvenance = Join-Path $destinationDirectory ($wheelName + '.provenance.json')
$expected = Get-Content -LiteralPath $trackedProvenance -Raw | ConvertFrom-Json
$source = (Resolve-Path -LiteralPath $WheelPath).Path
if ((Split-Path $source -Leaf) -ne $wheelName) { throw "Expected $wheelName" }
if ($expected.upstream_commit -ne '64ea011cb65f14d9ce2737e60db9a4ae91ed7441') {
    throw 'Tracked candidate uses an unexpected MLX source commit'
}
$patch = Join-Path $ExoRoot 'scripts\windows\mlx\mlx-windows-ring-v0.32.3.patch'
if ((Get-FileHash -LiteralPath $patch -Algorithm SHA256).Hash.ToLower() -ne $expected.patch_sha256) {
    throw 'Reviewed candidate does not match the current Windows MLX patch'
}
if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLower() -ne $expected.wheel_sha256) {
    throw 'Wheel hash differs from the reviewed candidate. Rebuilt wheels require new gates and an explicit lock/provenance update.'
}
$destination = Join-Path $destinationDirectory $wheelName
if ($source -ne [System.IO.Path]::GetFullPath($destination)) {
    Copy-Item -LiteralPath $source -Destination $destination -Force
}
Write-Host "Staged reviewed MLX candidate: $destination" -ForegroundColor Green
Write-Host 'Install source dependencies with uv sync --frozen --extra mlx-cuda13; CPU CI uses --extra mlx-none and needs no wheel.'
