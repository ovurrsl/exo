# Windows MLX builds with the ring backend

Upstream MLX compiles its `ring` distributed backend out on Windows
(`if(MLX_BUILD_CPU AND NOT WIN32)`), so a Windows node cannot join an MLX ring
with macOS/Linux nodes. This directory holds MLX wheels built with the ring
backend ported to Winsock2, one folder per backend:

| Folder | Contents |
|---|---|
| `cpu/` | CPU backend + ring |
| `cuda13/` | CUDA 13 + CPU backends + ring (needs an NVIDIA driver for CUDA 13) |

`[tool.uv.sources] mlx` in `pyproject.toml` has a single `sys_platform == 'win32'`
entry pointing at the wheel in use; the rebuild script switches it. (Selecting
the wheel per extra does not work: `mlx` is declared in the `mlx` extra, which
`mlx-cpu`/`mlx-cuda13` pull in by self-reference, so an `extra == ...` source
marker never matches it.) Every wheel is built from
`rltakashige/mlx-jaccl-fix-small-recv@cc3f3e60`, the exact commit exo installs on
macOS, plus `mlx-windows-ring.patch`.

SHA-256 of the vendored wheels (kept in sync with `uv.lock` by the rebuild script):

| Wheel | SHA-256 |
|---|---|
<!-- wheel-hashes -->
| `vendor/windows/cuda13/mlx-0.32.0.dev20261003-cp313-cp313-win_amd64.whl` | `d7159f4cffa38608dffd17fd95a81fe184312a7a0ce158d4461e6d4a934be255` |
| `vendor/windows/cpu/mlx-0.32.0.dev20261002-cp313-cp313-win_amd64.whl` | `5141ba04677b13fc0c09cbebd874d875f06b2900377fef591af96b1186d9b5b8` |

## The patch

The ring part only touches the socket layer (`mlx/distributed/utils.{h,cpp}`,
`ring/ring.cpp`, two CMake files): `int` sockets become `socket_t`, and
`close`/`fcntl`/`errno` go through small helpers that map to
`closesocket`/`ioctlsocket`/`WSAGetLastError` on Windows. The ring algorithm and
the bytes on the wire are unchanged, so a Windows rank interoperates with
macOS ranks running the unpatched commit. POSIX behaviour is unchanged.

It also fixes a Windows-only hang in the CUDA build (`mlx/backend/cuda/event.cu`):
on GPUs without concurrent managed access (all GeForce cards under WDDM) MLX
synchronises CPU streams through a small signal kernel launched on a
non-blocking stream, while the host polls with `cudaMemcpy` on the legacy
stream. WDDM batches kernel launches and that poll never flushes the batch, so
the signal could stay queued forever and any CPU-stream evaluation - including
every ring collective - hung at random. The fix calls `cudaStreamQuery` after
the two event kernel launches (Windows only) to submit them. Before: 4-6 of 10
CPU-stream scenarios hung per run; after: 0 of 30.

The patch also fixes `mlx/backend/cpu/jit_compiler.cpp`: MLX's CPU backend
compiles `mx.compile`d functions at runtime with MSVC and locates it with
`vswhere -latest`, which skips the standalone Visual Studio Build Tools. It now
passes `-products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64`.
Without Build Tools installed, compiled functions still fail on Windows; set
`MLX_DISABLE_COMPILE=1` on such machines.

## Rebuild

Requirements: Visual Studio 2022 Build Tools (C++ workload), uv, git. For CUDA
also the CUDA 13.0 Toolkit (nvcc, cudart, cuBLAS, cuFFT, cuSOLVER, NVRTC, crt,
nvvm, ptxcompiler) and an extracted cuDNN 9 for CUDA 13 archive - the same
components upstream MLX's release workflow uses.

```powershell
# From the exo checkout; clones and patches ..\mlx-src if it is missing.
.\.claude\skills\rebuild-mlx-windows\scripts\rebuild.ps1 -Backend cpu
.\.claude\skills\rebuild-mlx-windows\scripts\rebuild.ps1 -Backend cuda13 -CudnnDir C:\deps\cudnn-cuda13
```

Manual CPU build (what the script does):

```powershell
# autocrlf=false: the patch uses the repository's LF line endings.
git -c core.autocrlf=false clone https://github.com/rltakashige/mlx-jaccl-fix-small-recv.git mlx-src
cd mlx-src
git -c core.autocrlf=false checkout cc3f3e60be1289506125f2fa19b73b05aa770df8
git -c core.autocrlf=false apply ..\exo\vendor\windows\mlx-windows-ring.patch
$env:MLX_BUILD_STAGE = "0"; $env:DEV_RELEASE = "1"
$env:CMAKE_ARGS = "-DMLX_BUILD_METAL=OFF -DMLX_BUILD_CUDA=OFF"
uv build --wheel --python 3.13 --out-dir dist
```
