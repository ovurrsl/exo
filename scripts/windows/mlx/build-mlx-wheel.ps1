# Build the Windows MLX wheel: upstream MLX v0.32.3 with mlx-windows-ring-v0.32.3.patch
# (ring backend ported to Winsock2, WDDM launch flush, CUDA DLL loading from NVIDIA's
# pip wheels). Prints the wheel path and its SHA-256; publishing it is a separate step.
#
#   .\build-mlx-wheel.ps1 -Backend cpu
#   .\build-mlx-wheel.ps1 -Backend cuda13 -CudnnDir C:\path\to\cudnn-build
#   .\build-mlx-wheel.ps1 -Backend cuda13 -CudnnDir ... -CudaArchitectures "120a-real;120-virtual"
#   .\build-mlx-wheel.ps1 -UpdatePatch     # write the source tree's diff back to the patch
#
# Needs Visual Studio Build Tools (C++ workload), uv, and for cuda13 the CUDA Toolkit 13
# (CUDA_PATH) and a cuDNN directory with include\ (headers matching the runtime cuDNN,
# 9.19), lib\x64\ (import libraries) and bin\x64\ (the DLLs: the build collects the
# delay-loaded DLL names from there; without it cudnn64_9.dll becomes a hard dependency
# and `import mlx.core` fails). The CUDA Toolkit and cuDNN are only needed to build: the
# cuda13 wheel loads the CUDA libraries from the nvidia-* wheels exo installs on Windows.
#
# The default (all cores) parallelism once failed in qqmm_utils.cu without an error
# message; $env:CMAKE_BUILD_PARALLEL_LEVEL = '8' built it reliably.
param(
    [ValidateSet('cpu', 'cuda13')] [string]$Backend = 'cpu',
    # Default: a clone of ml-explore/mlx next to the exo checkout.
    [string]$MlxSrc,
    # Build time only: cuDNN headers, import libraries and the DLL names to delay-load.
    [string]$CudnnDir,
    # RTX 20 (sm_75), 30 (sm_86 runs sm_80 code), 40 (sm_89) and 50 (sm_120), plus
    # PTX that newer GPUs can JIT. Fewer architectures build much faster.
    [string]$CudaArchitectures = '75-real;80-real;89-real;120a-real;120-virtual',
    # Where mlx.dll looks for the CUDA DLLs, relative to site-packages\mlx. The CUDA 13
    # pip wheels install them to nvidia\cu13\bin\x86_64; cuDNN keeps nvidia\cudnn\bin.
    [string]$CudaBinDir = '../nvidia/cu13/bin/x86_64',
    # Write the source tree's diff to the patch file and stop.
    [switch]$UpdatePatch
)

$ErrorActionPreference = 'Stop'
$ExoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
if (-not $MlxSrc) { $MlxSrc = Join-Path (Split-Path $ExoRoot -Parent) 'mlx-src-0323' }
# Upstream ml-explore/mlx v0.32.3. Its ring wire protocol is the same as the
# rltakashige/mlx-jaccl-fix-small-recv@cc3f3e60 that exo installs on macOS.
$PinnedCommit = '64ea011cb65f14d9ce2737e60db9a4ae91ed7441'
$Patch = Join-Path $PSScriptRoot 'mlx-windows-ring-v0.32.3.patch'
# The patch is written (-UpdatePatch) and checked with these exact options so the bytes
# do not depend on the clone or on user settings (blob id length, diff.* config).
$DiffArgs = @('-c', 'core.autocrlf=false', '-c', 'diff.suppressBlankEmpty=false', 'diff',
    '--full-index', '--no-ext-diff', '--no-textconv', '--no-color', '--diff-algorithm=myers',
    '--unified=3', '--inter-hunk-context=0', '--src-prefix=a/', '--dst-prefix=b/')

function Step([string]$Message) { Write-Host "==> $Message" -ForegroundColor Cyan }

$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { throw 'uv not found' }

# 1. The source must be the pinned commit with exactly this patch on top, otherwise the
#    Windows ring could drift from the protocol the Macs speak.
Step "Checking $MlxSrc"
if (-not (Test-Path $MlxSrc)) {
    # core.autocrlf=false keeps the repository's LF line endings for checkout, apply
    # and the byte comparison below. Only the pinned commit's files are downloaded.
    git clone -q --filter=blob:none --no-checkout -c core.autocrlf=false https://github.com/ml-explore/mlx.git $MlxSrc
    if ($LASTEXITCODE -eq 0) { git -C $MlxSrc -c core.autocrlf=false checkout -q $PinnedCommit }
    if ($LASTEXITCODE -eq 0) { git -C $MlxSrc -c core.autocrlf=false apply $Patch }
    if ($LASTEXITCODE -ne 0) { throw "Setting up $MlxSrc failed (git exit code $LASTEXITCODE)" }
}
$head = (git -C $MlxSrc rev-parse HEAD).Trim()
if ($head -ne $PinnedCommit) { throw "mlx-src HEAD is $head, expected $PinnedCommit" }
if ($UpdatePatch) {
    # --output, not `>`: Windows PowerShell would re-encode the redirected text.
    git -C $MlxSrc @DiffArgs --output=$Patch
    if ($LASTEXITCODE -ne 0) { throw "git diff failed ($LASTEXITCODE)" }
    Write-Host "Wrote $Patch"
    return
}
# Compare bytes, not PowerShell strings: Windows PowerShell decodes git output and files
# with different code pages, which mangles the non-ASCII characters in MLX.
$currentDiff = Join-Path $env:TEMP 'mlx-src-current.patch'
git -C $MlxSrc @DiffArgs --output=$currentDiff
if ($LASTEXITCODE -ne 0) { throw "git diff failed ($LASTEXITCODE)" }
if ((Get-FileHash $currentDiff).Hash -ne (Get-FileHash $Patch).Hash) {
    throw "mlx-src working tree does not match $Patch (see $currentDiff)"
}

# 2. MSVC environment (cl, rc, ninja) from the newest VS/Build Tools install.
Step 'Importing MSVC environment'
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vs) { throw 'Visual Studio Build Tools with the C++ workload not found' }
# 2>NUL: vcvarsall prints "'vswhere.exe' is not recognized" to stderr on Build Tools
# installs, which aborts the script under -ErrorAction Stop when output is redirected.
cmd /c "`"$vs\VC\Auxiliary\Build\vcvarsall.bat`" x64 >NUL 2>NUL && set" | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') { Set-Item -Path "env:$($Matches[1])" -Value $Matches[2] }
}
if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) { throw "vcvarsall.bat did not set up cl.exe ($vs)" }

# 3. Backend specific CMake arguments (setup.py splits CMAKE_ARGS on spaces, so the
#    values must not contain spaces).
$cmakeArgs = @('-DMLX_BUILD_METAL=OFF')
if ($Backend -eq 'cuda13') {
    $cudaPath = [Environment]::GetEnvironmentVariable('CUDA_PATH', 'Machine')
    if (-not $cudaPath -or -not (Test-Path "$cudaPath\bin\nvcc.exe")) { throw 'CUDA Toolkit 13 not found (CUDA_PATH)' }
    if (-not $CudnnDir -or -not (Test-Path "$CudnnDir\include\cudnn.h")) { throw '-CudnnDir must contain include\cudnn.h' }
    if (-not (Test-Path "$CudnnDir\bin\x64\cudnn64_9.dll")) { throw '-CudnnDir must contain bin\x64\cudnn64_9.dll (see the header of this script)' }
    foreach ($value in $CudnnDir, $CudaArchitectures, $CudaBinDir) {
        if ($value -match ' ') { throw "CMake arguments must not contain spaces: $value" }
    }
    $env:CUDA_PATH = $cudaPath
    $env:Path = "$cudaPath\bin;$env:Path"
    $cudnn = $CudnnDir -replace '\\', '/'
    # Forward slashes: the value ends up in a C string literal.
    $cudaBin = $CudaBinDir -replace '\\', '/'
    $cmakeArgs = @('-G', 'Ninja', '-DCMAKE_C_COMPILER=cl', '-DCMAKE_CXX_COMPILER=cl', '-DCMAKE_RC_COMPILER=rc',
        '-DMLX_BUILD_METAL=OFF', '-DMLX_BUILD_CUDA=ON',
        "-DCUDNN_INCLUDE_PATH=$cudnn/include", "-DCUDNN_LIBRARY_PATH=$cudnn/lib/x64",
        "-DMLX_CUDA_ARCHITECTURES=$CudaArchitectures",
        # Resolve the delay-loaded CUDA/cuDNN DLLs relative to mlx.dll (the NVIDIA pip
        # wheels) instead of this machine's CUDA Toolkit and cuDNN directories.
        '-DMLX_LOAD_CUDA_LIBS_FROM_PYTHON=ON', "-DMLX_CUDA_BIN_DIR=$cudaBin")
} else {
    $cmakeArgs += '-DMLX_BUILD_CUDA=OFF'
}

# The CMake build dir is shared between backends (cpu uses the Visual Studio generator,
# cuda13 uses Ninja, and CMake refuses to switch in place). Start clean unless the
# previous build was made by this script for this backend.
$marker = Join-Path $MlxSrc 'build\.exo-backend'
$buildDir = Join-Path $MlxSrc 'build'
$sameBackend = (Test-Path $marker) -and ((Get-Content $marker -Raw).Trim() -eq $Backend)
if ((Test-Path $buildDir) -and -not $sameBackend) {
    Step 'Cleaning previous build (different or unknown backend)'
    Remove-Item -Recurse -Force $buildDir
}

Step "Building MLX wheel ($Backend)"
# One self-contained 'mlx' wheel: Python bindings and libmlx from the same build, not
# the split frontend ('mlx') + backend ('mlx-cuda-13') packages of upstream releases.
# MLX's setup.py derives the dev version from today's date.
$dist = Join-Path $MlxSrc "dist\$Backend"
$env:MLX_BUILD_FRONTEND_PACKAGE = '0'
$env:MLX_BUILD_BACKEND_PACKAGE = '0'
$env:DEV_RELEASE = '1'
$env:CMAKE_ARGS = $cmakeArgs -join ' '
if (-not $env:CMAKE_BUILD_PARALLEL_LEVEL) { $env:CMAKE_BUILD_PARALLEL_LEVEL = "$([Environment]::ProcessorCount)" }
Remove-Item -Recurse -Force $dist -ErrorAction SilentlyContinue
Push-Location $MlxSrc
try {
    & $uv build --wheel --python 3.13 --out-dir $dist
    if ($LASTEXITCODE -ne 0) { throw "uv build failed ($LASTEXITCODE)" }
} finally { Pop-Location }
New-Item -ItemType Directory -Force (Split-Path $marker) | Out-Null
Set-Content -Path $marker -Value $Backend

$wheel = Get-ChildItem $dist -Filter 'mlx-*.whl' | Select-Object -First 1
if (-not $wheel) { throw "No wheel in $dist" }
$sha = (Get-FileHash $wheel.FullName -Algorithm SHA256).Hash.ToLower()
Write-Host "Built $($wheel.FullName)"
Write-Host "sha256 $sha"
