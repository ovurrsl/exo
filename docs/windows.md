# Running exo on Windows (experimental)

This branch runs exo natively on Windows (no WSL2) on PCs with an NVIDIA GPU, so a
Windows PC can join a cluster of macOS nodes running upstream exo. Models are split
across machines with MLX's ring (TCP) backend; each node computes its layers on its
own GPU.

Status: single-node GPU inference through the exo API works (Qwen3-0.6B-4bit, about
260-280 tokens/s streaming on an RTX 5070), and the ring backend passes 2, 3 and
4 rank tests on one Windows machine. **A real macOS + Windows ring has not been
tested yet.** With the MLX wheel pinned today, only models whose files are all
smaller than 2 GiB load (see Known limitations).

## How it works

Upstream MLX publishes Windows CUDA wheels but compiles the ring backend out on
Windows. exo therefore installs its own MLX wheel on Windows: the same MLX source the
macOS nodes use, with the ring backend ported to Winsock2 and two Windows CUDA fixes.
The wire protocol is unchanged. How the wheel is built is described in
[`scripts/windows/mlx/README.md`](../scripts/windows/mlx/README.md).

Everything else is Windows-only code behind `sys.platform == "win32"` or
`#[cfg(windows)]`; macOS and Linux behave exactly as upstream.

## Requirements

- Windows 10/11 x64 with an NVIDIA GPU and a driver that supports CUDA 13: version
  580.88 or newer. On RTX 50 with Windows 11 24H2, use 581.36 or newer: NVIDIA's
  Nsight known issues list a system hang with earlier R576/R580 drivers there while
  debugging CUDA with hardware-accelerated GPU scheduling on. Game Ready and Studio
  drivers of the same version are the same driver as far as CUDA is concerned;
  either works.
- [uv](https://docs.astral.sh/uv/), Node.js (for the dashboard), Rust nightly
  (`rustup`), and Visual Studio Build Tools with the C++ workload (for the Rust
  bindings and MLX's CPU kernel compiler).
- The LAN must carry IPv6: discovery uses IPv6 multicast and link-local addresses,
  exactly as on macOS.

## Install and run

```powershell
git clone https://github.com/ovurrsl/exo
cd exo
git checkout windows-native
cd dashboard; npm install; npm run build; cd ..
uv sync --python 3.13 --extra mlx-cuda13
```

Once, from an administrator PowerShell, open the firewall for the cluster ports:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\allow-firewall.ps1
```

Start exo:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\run.ps1
```

`run.ps1` passes its arguments to `exo` (for example `-v` or `--api-port`), and on a
CUDA node it sets `MLX_PTX_CACHE_DIR` unless you set it yourself: MLX compiles CUDA
kernels on first use (the first request takes 20-30 s) and caches them under `%TEMP%`,
which Storage Sense cleans. The script keeps the cache under
`%LOCALAPPDATA%\exo\mlx-kernel-cache\<mlx version>-sm<compute cap>`.

### GPU memory

On a CUDA node the model weights and the KV cache live in GPU memory, and Windows does
not fail an allocation that does not fit: it silently moves it to shared system memory
and generation becomes very slow. So on Windows exo works with the GPU's memory, read
through NVML (installed by `--extra mlx-cuda13`) every second:

- It reports the GPU's total memory and its free memory minus 2.5 GiB (for the KV
  cache, prefill activations and the CUDA context) to the master, which places models
  by that. Set `OVERRIDE_MEMORY_MB` to report a fixed amount instead.
- It evicts the prefix cache when less than 1 GiB of GPU memory is free
  (`EXO_WINDOWS_GPU_MIN_FREE_MB`, keep it below the 2.5 GiB reserve), counting
  buffers MLX keeps cached for reuse as free; every rank of the instance evicts with
  it. The system RAM threshold (`EXO_MEMORY_THRESHOLD`) still applies as well.
- Both assume one NVIDIA GPU: NVML's GPU 0 is used, which with several GPUs need not
  be the one MLX runs on.

Whether CUDA may spill into shared memory at all is the driver's "CUDA - Sysmem Fallback
Policy" (NVIDIA Control Panel, Manage 3D settings, globally or for `python.exe`):
"Prefer No Sysmem Fallback" makes an allocation that does not fit fail instead.

Data, models and logs go to `%LOCALAPPDATA%\exo` unless `EXO_HOME` is set.
`EXO_MODELS_DIRS` and `EXO_MODELS_READ_ONLY_DIRS` are separated with `;` on Windows.

## Running the tests

The tests also need the workspace packages, so sync with `--all-packages` and run
the unit tests under `src` (the top-level `tests/` are cluster tests that need a
POSIX host):

```powershell
uv sync --python 3.13 --all-packages --extra mlx-cuda13
uv run pytest src
```

Image generation (mflux) is not installed on Windows, so its tests are not collected.
`basedpyright` is configured for macOS (`pythonPlatform = "Darwin"`); on Windows it
also reports that the macOS/Linux-only `python-daemon` is not installed.

## Ports

| Port | Protocol | Use |
|---|---|---|
| 52413 | UDP | discovery (IPv6 multicast `ff12::e0a1:de89`) |
| 52414 | TCP | zenoh (cluster messaging) |
| 52415 | TCP | API and dashboard; peers also probe it |
| 49152-65535 | TCP | MLX ring; exo picks a random port per instance |

`allow-firewall.ps1` opens these for Private and Domain networks (mark your LAN as
Private); the ring range is allowed only for the Python interpreter and only from
the local subnet.

Windows' default dynamic port range (49152-65535) contains 52413-52415, so another
program can hold one of them by chance (seen with SteelSeries GG on 52415). To keep
them free, move the dynamic range above exo's ports from an administrator prompt:

```powershell
netsh int ipv4 set dynamicport tcp start=52500 num=13036
netsh int ipv6 set dynamicport tcp start=52500 num=13036
```

## In a cluster with macOS nodes

- Run the same exo commit on every node. This branch is based on upstream `main`;
  the macOS nodes should run that commit too.
- Set `EXO_MEMORY_THRESHOLD` on the Windows node to the Macs' default (0.70 below
  32 GB, 0.75 for 32 GB, 0.80 for 64 GB, 0.85 for 128 GB or more), so every rank evicts
  the prefix cache at the same point; otherwise ranks can disagree mid-collective and
  stall.
- Connect the PC to a Mac with a wired link; Wi-Fi adds milliseconds to every token.
  The fastest is a USB4/Thunderbolt cable between the two computers' USB4 or
  Thunderbolt ports: Windows 11 shows it as a "USB4(TM) P2P Network Adapter", which
  exo reports as a Thunderbolt link so the ring backend prefers it, and the Mac sees
  it as its Thunderbolt Bridge. (Others measured about 15 Gbit/s between a Mac and a
  Windows PC this way with an MTU of 9000 on both sides; not yet tried with exo.)
  Windows puts such an unidentified network in the Public firewall profile, which
  `allow-firewall.ps1` does not open; mark it Private, e.g.
  `Set-NetConnectionProfile -InterfaceAlias "Ethernet 3" -NetworkCategory Private`
  with the adapter's name.

## Known limitations

- The MLX wheel this branch pins (`0.32.0.dev20261003`, downloaded from this fork's
  `mlx-windows-0.32.0.dev20261003` release) contains CUDA code for RTX 50 series GPUs
  (sm_120a) only, and looks for the CUDA libraries in the CUDA 13.0 Toolkit's default
  install folder and for cuDNN in a folder of the machine it was built on. It has
  only been run on that machine. The portable build (MLX v0.32.3: RTX 20-50, CUDA
  libraries from NVIDIA's pip wheels, no CUDA Toolkit needed) made processes that ran
  GPU work exit with code 2170; the patch now carries the fix, and the wheel will
  replace this one once it has been rebuilt and tested (see the MLX README).
- The pinned wheel cannot load a model file larger than 2 GiB (MLX's file reader used
  32-bit seeks on Windows before ml-explore/mlx#4456), so most models above roughly
  3B parameters fail to load with `The JSON header is ... bytes long but the file is
  only 8 bytes`. The files are not corrupt. A rebuilt wheel with that fix is planned.
- Only NVIDIA GPUs are supported. MLX's CPU backend works on Windows but is far too
  slow on x86 to be useful (about 0.2 tokens/s for Qwen3-0.6B), and every extra
  installs the CUDA build of MLX.
- vLLM is not advertised on Windows, and `--legacy-daemon` is not supported.
- Each idle runner keeps about two CPU cores busy; the cause is not known yet.
