# MLX for Windows with the ring backend

exo's cluster backend between Macs and a Windows PC is MLX's ring backend (TCP).
Upstream MLX builds Windows wheels, including CUDA ones, but compiles ring out on
Windows (`if(MLX_BUILD_CPU AND NOT WIN32)`). This directory holds the patch that ports
it, and the script that builds a wheel from it.

## The patch

[`mlx-windows-ring-v0.32.3.patch`](mlx-windows-ring-v0.32.3.patch) applies to
ml-explore/mlx v0.32.3 (`64ea011cb65f14d9ce2737e60db9a4ae91ed7441`). The
build script verifies the complete source diff byte-for-byte against this patch.

- `mlx/distributed/utils.{h,cpp}`, `mlx/distributed/ring/ring.cpp`: sockets go
  through small `socket_t` helpers (Winsock2 on Windows, BSD sockets elsewhere);
  `WSAStartup` on first use, `int` lengths for Winsock, `SO_REUSEPORT` only where it
  exists. The POSIX code paths do the same calls as before.
- `mlx/distributed/CMakeLists.txt`, `mlx/distributed/ring/CMakeLists.txt`: build ring
  on Windows and link `ws2_32`.
- `mlx/distributed/ring/ring.cpp`, `mlx/distributed/utils.cpp`: the Windows
  socket worker waits for readiness instead of spinning on `WSAEWOULDBLOCK`,
  propagates failures to pending and subsequent operations, and bounds idle
  transfers and accepts. `MLX_RING_IO_TIMEOUT_SECONDS` defaults to 120 and can
  be set to an integer between 1 and 86400. The Mac worker remains unchanged.
- `mlx/compile.cpp`: leaves CPU-stream primitives unfused on Windows, including
  CPU operations inside a GPU-default compiled graph. CUDA NVRTC fusion stays
  enabled. Consumers need neither MSVC nor a CUDA Toolkit.
- `mlx/backend/cuda/event.cu`: under WDDM the driver batches kernel launches, so a
  CPU thread waiting for the signal kernel could spin forever; `cuStreamQuery` from the
  launching thread submits the batch. Windows host event waits poll briefly, then
  sleep between checks so a stalled CPU ring does not consume a whole CPU core.
- `mlx/backend/cuda/delayload.cpp`, `mlx/backend/cuda/CMakeLists.txt`: load the CUDA
  DLLs from NVIDIA's CUDA 13 pip wheel layout (`nvidia/cu13/bin/x86_64`), put their
  directories on `PATH` (nvrtc and cuDNN load further DLLs by name, which ignores
  `AddDllDirectory`), and name the DLL that failed to load instead of dying with only
  an exception code.
- `mlx/backend/cpu/jit_compiler.cpp`: find standalone Build Tools too
  (`vswhere -products * -requires ...VC.Tools...`).
- `mlx/windows_utils.h`, `mlx/io/load.h`: use strict UTF-8 to UTF-16 conversion
  and `_wopen` for Windows model reads and writes. Windows writes use the CRT's
  permission flags, and failed readers do not close an invalid descriptor. These
  fixes prevent native fail-fast exits for missing files and preserve Turkish,
  Chinese and emoji filenames. Other platforms retain their existing file calls.
- `mlx/backend/common/utils.cpp`, `mlx/backend/cuda/jit_module.cpp`: obtain the
  module path and CUDA/cache environment paths through wide Windows APIs. NVRTC
  accepts losslessly encoded ANSI include paths; headers below paths outside the
  active codepage are provided through NVRTC's virtual-header API. This avoids
  changing the machine codepage or requiring an ASCII installation directory.
- `mlx/backend/cuda/dirs.cpp`, `mlx/backend/cuda/delayload.cpp`: retain wide
  paths when resolving and loading bundled Windows CUDA DLLs, including paths
  outside the active ANSI codepage.
- `mlx/distributed/ring/ring.cpp`: read `MLX_HOSTFILE` with the wide Windows
  environment API and open hostfiles through their Unicode filesystem paths.
- `mlx/backend/cuda/wddm.cpp`: the WDDM memory budget (new in v0.32.3, it holds
  DXGI adapters) is leaked at exit like MLX's other CUDA singletons. It is the only
  static added since cc3f3e60 that the first GPU allocation creates (the allocator
  asks it for the memory limit), and destroying it
  while the process unloads its DLLs is the likely cause of processes that allocated
  GPU memory exiting with code 2170 (or hanging). The rebuilt candidate passed
  repeated bare and Exo-hooked GPU process exits on the RTX 5070, although that
  validates the fix's behavior rather than isolating the original driver cause.
  2170 is 0x87A, the facility code of DXGI's HRESULTs (`_FACDXGI`,
  0x887Axxxx), and `wddm.cpp` is the only code in MLX that uses DXGI.

The ring wire protocol of v0.32.3 is the same as that of the MLX commit exo installs
on macOS (rltakashige/mlx-jaccl-fix-small-recv@cc3f3e60): packet and segment sizes are
unchanged; v0.32.3 adds a 1 GiB per-call I/O cap and fails fast when a peer is lost.
On Linux, CPU builds of cc3f3e60 and of v0.32.3 with this patch ran rings together
(2, 3 and 4 ranks, mixed in both orders): `all_sum`, `all_gather` and a `send`/`recv`
pipeline over float32, float16, bfloat16 and int32 arrays of 1 to 33.5 million elements
all gave the expected results. That covers the protocol code both platforms share, not
the Winsock paths; a Mac <-> Windows ring has not been run yet.

## Building

From PowerShell on Windows (see the header of the script for prerequisites):

```powershell
$env:CMAKE_BUILD_PARALLEL_LEVEL = '8'
.\scripts\windows\mlx\build-mlx-wheel.ps1 -Backend cuda13 -CudnnDir C:\path\to\cudnn-build
```

It clones MLX next to the exo checkout if needed, checks that the tree is v0.32.3 with
exactly this patch, builds one self-contained `mlx` wheel and prints its SHA-256.
It writes an adjacent `.provenance.json` containing the upstream commit, patch hash,
wheel hash, backend and architecture list. Use `-VsInstallPath` for a custom Build
Tools installation and `-Python` to reuse an explicitly prepared build environment.
That environment needs wheel, cmake, ninja, nanobind and pybind11. Existing builds
from the same backend are reused; previous wheel outputs are preserved.

Build with the CUDA 13.0 Toolkit: at run time the wheel loads the CUDA libraries from
the 13.0 `nvidia-*` wheels `pyproject.toml` pins on Windows (cuBLAS 13.1, cuFFT,
cuSOLVER, cuSPARSE, nvJitLink, NVRTC 13.0, cuDNN 9.19), and a newer toolkit could
use functions or PTX those libraries and R580 drivers do not have. Checked on Linux
against those wheels: they put their DLLs where the patch looks
(`nvidia\cu13\bin\x86_64`, `nvidia\cudnn\bin`), every DLL they import is among them or
part of Windows, and the CUDA headers NVRTC needs come from `nvidia-cuda-runtime`
(`nvidia\cu13\include`) and the CCCL headers the wheel bundles, so no CUDA Toolkit is
needed to run it. `mlx.dll` needs the Microsoft Visual C++ runtime (`msvcp140.dll`),
which the Build Tools install.

## Checking a wheel

[`check-mlx-wheel.ps1`](check-mlx-wheel.ps1) checks the MLX of a Python
environment (exo's `.venv` by default, or `-Python <path>`):

- bare and Exo-hooked MLX import/compute exit codes, repeated `-Runs` times;
- process spawn, CPU compilation, GPU NVRTC and a mixed CPU/GPU-stream graph
  with a fresh JIT cache, no Toolkit variables and a consumer PATH;
- ASCII and Turkish/Chinese/emoji safetensors save/load for float32, float16,
  bfloat16 and int32, plus graceful missing-file and malformed-path failures;
- a mandatory valid sparse safetensors fixture larger than 2 GiB: evaluates
  four float32 values beyond the 2 GiB offset without allocating the padding.
  `-LargeFile <path>` instead evaluates every tensor in a real >2 GiB shard;
- ring sum/max/min/gather and send/recv for float32, float16, bfloat16 and int32,
  including strided data crossing the 8 MiB chunk boundary at 2/3/4 ranks and
  Unicode hostfiles;
- missing peer, killed connected peer and connected but stalled peer errors.

The checks are implemented in `check_mlx.py`, so the identical gate is executable
inside the frozen package with `exo.exe --runtime-check`. Reports retain per-check
exit codes, durations and logs. `-Output <path>` writes JSON evidence. A loopback
pass does not prove physical Mac/Windows interoperability or model inference parity.

A run that does not exit within `-TimeoutSeconds` is killed and counts as failed.

```powershell
.\scripts\windows\mlx\check-mlx-wheel.ps1 -LargeFile C:\path\to\model-00001-of-00002.safetensors
```

To tell whether a problem comes from this patch or from MLX itself, run the same
script against upstream's own Windows CUDA wheel in a separate environment:

```powershell
uv venv C:\tmp\mlx-official --python 3.13
uv pip install --python C:\tmp\mlx-official\Scripts\python.exe "mlx[cuda13]==0.32.3"
.\scripts\windows\mlx\check-mlx-wheel.ps1 -Python C:\tmp\mlx-official\Scripts\python.exe -RingSizes @()
```

(Upstream compiles ring out on Windows, hence `-RingSizes @()`.)

## Wheels

| Wheel | MLX source | GPUs | Status |
|---|---|---|---|
| `mlx-0.32.0.dev20261003-cp313-cp313-win_amd64.whl`, sha256 `d7159f4cffa38608dffd17fd95a81fe184312a7a0ce158d4461e6d4a934be255` | cc3f3e60 + an earlier revision of this patch | RTX 50 (sm_120a) | historical release, no longer pinned; loads CUDA from the CUDA 13.0 Toolkit's default folder and cuDNN from a folder of the build machine; tested on that machine only. **Cannot load a model file larger than 2 GiB** (see below) |
| `mlx-0.32.3.dev20261004-cp313-cp313-win_amd64.whl` | v0.32.3 + this patch without the `wddm.cpp` change | RTX 20-50 | not used: a process that ran GPU work exits with 2170 instead of its exit code |
| `mlx-0.32.3.dev20261009-cp313-cp313-win_amd64.whl`, sha256 `364daa278b094f771e55dad7739369c1b77e8f349726e25ff93e261af212a5c5` | v0.32.3 + this patch, patch sha256 `37762249a1112031eae074b50f80403c38730b2bd962e1cb6039775aa3f1805c` | compiled for RTX 20-50; physically tested on RTX 5070 | all 31 native CUDA gates passed on Windows 11 / driver 617.42. Idle stalled-ring CPU measured 0.78% including real interpreter children. Frozen package evidence is recorded in `runtime-manifest.json`; physical Mac/Windows mixed-model validation remains required. |

The earlier patch revision is not in this repository; it differs in the base commit,
in not loading CUDA from the pip wheels, and in the details of the WDDM fix.

The active candidate is `mlx-0.32.3.dev20261009+win.3`, wheel SHA-256
`045831dade422768798c314e63d4a8324873d8b3f64c12097ba4a6d3841885b2`, patch SHA-256
`15b57315406c4453956f1398bc3465cd7dd043575eb513dc9f419396fe28f779`.
Its tracked provenance lists **120a-real;120-virtual**, so the current package
targets the validated RTX 5070 and does not establish RTX 20–40 support. The
older multi-architecture wheel in the table is a different immutable artifact.
Physical single-M1/RTX 5070 results are scoped in
[`windows-hardware-acceptance.md`](../../../docs/windows-hardware-acceptance.md);
clean-machine and three-device release gates remain open.

### Files larger than 2 GiB

The historical `0.32.0.dev20261003` wheel cannot load a safetensors file larger than
2 GiB on Windows, so most models above roughly 3B parameters fail with
`[load_safetensors] The JSON header is ... bytes long but the file is only 8 bytes`.
The files are fine: the v0.32.3 build loads them. In cc3f3e60, `mlx/io/load.h` seeks
with `lseek`, whose offset is a 32-bit `long` on Windows, so the file size comes out
wrong. Upstream fixed this in ml-explore/mlx#4456 (`334cfdc5`, `_lseeki64` on Windows,
`mlx/io/load.h` only), which v0.32.3 and the patch above include; reads already use
64-bit offsets (`pread` emulated with `ReadFile` and an `OVERLAPPED` offset).
