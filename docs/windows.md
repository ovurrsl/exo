# Running exo on Windows (experimental)

This branch runs exo natively on Windows (no WSL2) on PCs with an NVIDIA GPU, so a
Windows PC can join a cluster of macOS nodes running upstream exo. Models are split
across machines with MLX's ring (TCP) backend; each node computes its layers on its
own GPU.

Status: single-node GPU inference through the exo API works (Qwen3-0.6B-4bit, about
260-280 tokens/s streaming on an RTX 5070), and the ring backend passes 2, 3 and
4 rank tests on one Windows machine. **A real macOS + Windows ring has not been
tested yet.**

## How it works

Upstream MLX publishes Windows CUDA wheels but compiles the ring backend out on
Windows. exo therefore installs its own MLX wheel on Windows: the same MLX source the
macOS nodes use, with the ring backend ported to Winsock2 and two Windows CUDA fixes.
The wire protocol is unchanged. How the wheel is built is described in
[`scripts/windows/mlx/README.md`](../scripts/windows/mlx/README.md).

Everything else is Windows-only code behind `sys.platform == "win32"` or
`#[cfg(windows)]`; macOS and Linux behave exactly as upstream.

## Requirements

- Windows 10/11 x64 with an NVIDIA GPU and a driver that supports CUDA 13.
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
CUDA node it sets two variables unless you set them yourself:

- `OVERRIDE_MEMORY_MB`: the GPU's free memory minus 2.5 GiB. exo otherwise reports
  system RAM, and Windows does not fail an over-full GPU: it silently spills into
  shared system memory and generation becomes very slow.
- `MLX_PTX_CACHE_DIR`: MLX compiles CUDA kernels on first use (the first request takes
  20-30 s) and caches them under `%TEMP%`, which Storage Sense cleans. The script keeps
  the cache under `%LOCALAPPDATA%\exo\mlx-kernel-cache\<mlx version>-sm<compute cap>`.

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
- Set `EXO_MEMORY_THRESHOLD` on the Windows node to the Macs' default (0.70 for a
  16 GB Mac, 0.75 for 32 GB, 0.80 for 64 GB or more), so every rank evicts the prefix
  cache at the same point; otherwise ranks can disagree mid-collective and stall.

## Known limitations

- The MLX wheel this branch currently pins (`0.32.0.dev20261003`) was built on one
  machine, for RTX 50 series GPUs (sm_120) only, and has not been verified on another
  PC. A build for RTX 20-50 that loads CUDA from NVIDIA's pip wheels exists (MLX
  v0.32.3, see the MLX README) but is not used yet: processes that ran GPU work exit
  with code 2170 instead of their real exit code, and exo decides on runner failures
  by exit code.
- Only NVIDIA GPUs are supported. MLX's CPU backend works on Windows but is far too
  slow on x86 to be useful (about 0.2 tokens/s for Qwen3-0.6B), and every extra
  installs the CUDA build of MLX.
- vLLM is not advertised on Windows, and `--legacy-daemon` is not supported.
- Each idle runner keeps about two CPU cores busy; the cause is not known yet.
