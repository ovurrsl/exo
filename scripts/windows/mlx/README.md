# MLX for Windows with the ring backend

exo's cluster backend between Macs and a Windows PC is MLX's ring backend (TCP).
Upstream MLX builds Windows wheels, including CUDA ones, but compiles ring out on
Windows (`if(MLX_BUILD_CPU AND NOT WIN32)`). This directory holds the patch that ports
it, and the script that builds a wheel from it.

## The patch

[`mlx-windows-ring-v0.32.3.patch`](mlx-windows-ring-v0.32.3.patch) applies to
ml-explore/mlx v0.32.3 (`64ea011cb65f14d9ce2737e60db9a4ae91ed7441`), 10 files,
+284/-71:

- `mlx/distributed/utils.{h,cpp}`, `mlx/distributed/ring/ring.cpp`: sockets go
  through small `socket_t` helpers (Winsock2 on Windows, BSD sockets elsewhere);
  `WSAStartup` on first use, `int` lengths for Winsock, `SO_REUSEPORT` only where it
  exists. The POSIX code paths do the same calls as before.
- `mlx/distributed/CMakeLists.txt`, `mlx/distributed/ring/CMakeLists.txt`: build ring
  on Windows and link `ws2_32`.
- `mlx/backend/cuda/event.cu`: under WDDM the driver batches kernel launches, so a
  CPU thread waiting for the signal kernel could spin forever; `cuStreamQuery` from the
  launching thread submits the batch.
- `mlx/backend/cuda/delayload.cpp`, `mlx/backend/cuda/CMakeLists.txt`: load the CUDA
  DLLs from NVIDIA's CUDA 13 pip wheel layout (`nvidia/cu13/bin/x86_64`), put their
  directories on `PATH` (nvrtc and cuDNN load further DLLs by name, which ignores
  `AddDllDirectory`), and name the DLL that failed to load instead of dying with only
  an exception code.
- `mlx/backend/cpu/jit_compiler.cpp`: find standalone Build Tools too
  (`vswhere -products * -requires ...VC.Tools...`).
- `mlx/backend/cuda/wddm.cpp`: the WDDM memory budget (new in v0.32.3, it holds
  DXGI adapters) is leaked at exit like MLX's other CUDA singletons. It is the only
  static added since cc3f3e60 that the first GPU allocation creates (the allocator
  asks it for the memory limit), and destroying it
  while the process unloads its DLLs is the likely cause of processes that allocated
  GPU memory exiting with code 2170 (or hanging); to be confirmed on the rebuilt
  wheel.

The ring wire protocol of v0.32.3 is the same as that of the MLX commit exo installs
on macOS (rltakashige/mlx-jaccl-fix-small-recv@cc3f3e60): packet and segment sizes are
unchanged; v0.32.3 adds a 1 GiB per-call I/O cap and fails fast when a peer is lost.
This was established by comparing the sources; a Mac <-> Windows ring has not been run
yet.

## Building

From PowerShell on Windows (see the header of the script for prerequisites):

```powershell
$env:CMAKE_BUILD_PARALLEL_LEVEL = '8'
.\scripts\windows\mlx\build-mlx-wheel.ps1 -Backend cuda13 -CudnnDir C:\path\to\cudnn-build
```

It clones MLX next to the exo checkout if needed, checks that the tree is v0.32.3 with
exactly this patch, builds one self-contained `mlx` wheel and prints its SHA-256.

## Wheels

| Wheel | MLX source | GPUs | Status |
|---|---|---|---|
| `mlx-0.32.0.dev20261003-cp313-cp313-win_amd64.whl`, sha256 `d7159f4cffa38608dffd17fd95a81fe184312a7a0ce158d4461e6d4a934be255` | cc3f3e60 + an earlier revision of this patch | RTX 50 (sm_120a) | pinned by `pyproject.toml` from the [`mlx-windows-0.32.0.dev20261003`](https://github.com/ovurrsl/exo/releases/tag/mlx-windows-0.32.0.dev20261003) release; loads CUDA from the CUDA 13.0 Toolkit's default folder and cuDNN from a folder of the build machine; tested on that machine only |
| `mlx-0.32.3.dev20261004-cp313-cp313-win_amd64.whl` | v0.32.3 + this patch without the `wddm.cpp` change | RTX 20-50 | not used: a process that ran GPU work exits with 2170 instead of its exit code |
| next build | v0.32.3 + this patch | RTX 20-50 | to be built and tested; CUDA libraries come from NVIDIA's pip wheels, so no CUDA Toolkit is needed to run it |

The earlier patch revision is not in this repository; it differs in the base commit,
in not loading CUDA from the pip wheels, and in the details of the WDDM fix.
