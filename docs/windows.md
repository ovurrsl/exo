# Native Windows and NVIDIA support

This fork runs EXO natively on Windows with NVIDIA CUDA, alongside Mac nodes using
Metal. The initial target is one RTX 5070 and two 8 GB M1 MacBook Airs. Run the
same fork release on every node. Physical Mac–Windows acceptance remains a release
requirement; local Windows ring tests do not establish mixed-device support.

The default API and dashboard remains **http://localhost:52415** in both the CLI
and Windows desktop. Acceptance scripts select temporary ports and a separate
namespace to avoid joining or stopping an existing installation.

## Windows desktop and installation

The independent [Tauri and Svelte app](../app/windows/README.md) provides a compact
system tray panel, live topology, devices, memory, instances, downloads and tasks.
It opens the existing dashboard in the default browser. Its General, Model,
Advanced, Environment and About settings include namespace, offline mode, model
directories, Hugging Face endpoint and token, custom environment variables, start
at login, diagnostics, restart and signed updates.

The installer contains Python, Rust bindings, MLX, NVIDIA runtime libraries, CPU
PyTorch, dashboard and model resources. The end user needs a CUDA 13 compatible
NVIDIA display driver. Python, uv, Rust, Node, Visual Studio and CUDA Toolkit are
build dependencies. Development hardware acceptance uses Windows 11, RTX 5070 and
driver 617.42; other GPU generations still need physical qualification.

The per-user installer embeds the WebView2 offline installer. Application binaries
go to `%LOCALAPPDATA%\Programs\EXO`; settings, logs, cache and default models go to
`%LOCALAPPDATA%\exo`. Hugging Face tokens use Windows Credential Manager.
Custom and read-only model directories remain outside the application directory.
The uninstall flow offers to preserve downloaded models.

The desktop starts its backend suspended and assigns it to a kill-on-close Job
Object. Stop signals a random event restricted to the current user and SYSTEM.
Python drains runner shutdown acknowledgements before cancelling the node. After
ten seconds the desktop terminates only its owned process tree. Running appears
after the API responds. An external process occupying 52415 is shown read-only and
is never stopped by this app.

Unsigned review builds disable updater artifacts. A signed release requires the
owner's signing keys and the compiled public key. Updates use this fork's fixed
channel and install only on an explicit user action. Publication is separate from
building a local installer.

## Build and run from source

Developers need Python 3.13, uv, Node, an MSVC Rust toolchain, Visual Studio C++
Build Tools and the Windows SDK. Building MLX additionally needs the pinned CUDA
and cuDNN build inputs in the [MLX guide](../scripts/windows/mlx/README.md).

The Windows dependency points to a local reviewed wheel because the candidate has
not been published. Tracked provenance pins its source commit, patch SHA256 and
wheel SHA256. Staging refuses different bytes; a rebuild requires fresh gates and
an explicit provenance and lock update. Do not substitute the historical wheel.

```powershell
git clone https://github.com/ovurrsl/exo
cd exo
git checkout windows-native
.\scripts\windows\prepare-runtime-wheel.ps1 -WheelPath C:\path\mlx-0.32.3.dev20261009-cp313-cp313-win_amd64.whl
uv sync --frozen --python 3.13 --all-packages --extra mlx-cuda13
Push-Location dashboard
npm ci
npm run build
Pop-Location
.\scripts\windows\run.ps1
```

`run.ps1` forwards explicit CLI arguments, including `--api-port` when requested.
It retains CUDA's JIT cache under `%LOCALAPPDATA%\exo\mlx-kernel-cache`.
First use can compile kernels. The native patch leaves CPU-stream operations
unfused to avoid requiring an external compiler; CUDA fusion uses bundled NVRTC
and headers.

Build the complete runtime and installer with the
[Windows packaging scripts](../packaging/windows/README.md):

```powershell
.\scripts\windows\build-runtime.ps1 -MlxWheel C:\path\mlx-0.32.3.dev20261009-cp313-cp313-win_amd64.whl
.\scripts\windows\build-installer.ps1 -MlxWheel C:\path\mlx-0.32.3.dev20261009-cp313-cp313-win_amd64.whl -SkipRuntimeBuild
```

The runtime manifest records source inputs, package versions, native binary hashes
and gate results. It remains `release_ready: false` until physical cluster and
clean-machine acceptance are recorded. Use `-RequireSignedUpdater` for builds
intended for the signed release channel.

## CUDA capacity and model contracts

CUDA is advertised only after an isolated process executes a real MLX kernel,
verifies ring availability and exits normally. Failed checks are retried.
The first supported configuration has exactly one NVIDIA GPU; multiple GPUs
produce a clear error instead of silently selecting GPU 0.

Placement uses NVML VRAM with an initial 2.5 GiB reserve for context, activations,
KV cache and workspace. NVML loss reports no new placement capacity and never
substitutes host RAM. Swap performance counters are independent of GPU capacity.
Before evaluation, the loader checks owned layers and replicated parameters
against the measured budget. An override cannot raise capacity above that budget.

For groups containing CUDA, all ranks jointly decide prefix cache eviction and
check cache entry identity before removing the same entry in the same order.
The initial free-VRAM threshold is 1 GiB. Local rank thresholds need not match.
Disagreement produces an instance error. Failed or stalled runners remove the
whole CUDA instance. Mac-only cache decisions retain their existing path.

Before loading a CUDA group, ranks compare the immutable Hugging Face snapshot,
tokenizer and processor files, precision and global shard assignments. Downloads
save verified revision sidecars; pre-staged snapshots may use Hugging Face download
metadata. Copy the same pinned snapshot and metadata onto every rank. Missing or
different revision records cause a controlled error.

## Mac and Windows clustering

Namespace priority is explicit `--namespace`, then a nonempty
`EXO_ZENOH_NAMESPACE`, then the package version. This makes the existing Mac
app's environment setting effective without changing Swift sources.

The first heterogeneous configuration uses pipeline parallelism with TCP ring.
M1 Air ports support Thunderbolt 3/USB4; Apple's RDMA support requires Thunderbolt
5. These M1 devices therefore use IP networking rather than JACCL. See
[M1 specifications](https://support.apple.com/en-my/111883) and
[Apple TN3205](https://developer.apple.com/documentation/technotes/tn3205-low-latency-communication-with-rdma-over-thunderbolt).

Use a working wired IP link with IPv6 discovery. Desktop diagnostics show USB4
P2P adapters, IPv6 and firewall information. Verify the actual PC's adapter and
cable support; a USB-C connector alone does not establish an IP link.
Mark the intended trusted link Private before applying firewall rules.
The normal app stays unelevated and invokes a narrow administrator helper.

| Port | Protocol | Purpose |
| --- | --- | --- |
| 52413 | UDP | IPv6 multicast discovery |
| 52414 | TCP | Zenoh cluster messaging |
| **52415** | TCP | API and dashboard |
| 49152–65535 | TCP | Per-instance MLX ring sockets |

For source development, `allow-firewall.ps1` opens Private/Domain profiles.
The packaged helper restricts ring access to its bundled backend and local subnet.
For an API conflict, identify the occupying process, stop it yourself or explicitly
choose a different CLI port. Global dynamic port ranges need not be changed.

Mixed CUDA tensor parallelism is disabled by default pending validation of weight
replication, loading peaks and cache reserves. The acceptance-test opt-in is
`EXO_ENABLE_CUDA_TENSOR_PARALLEL=true`. Mac-only tensor parallelism is unchanged.

## Vision and image models

Windows uses CPU PyTorch for vision preprocessing and MLX CUDA for the language
model. Initialization errors are returned explicitly. The first acceptance model
is `mlx-community/Qwen3-VL-4B-Instruct-4bit`.

The Windows mflux path stages text encoders and VAE on CPU, keeps owned transformer
layers on GPU, tiles VAE work and restores stages after cancellation. Full
FLUX.1-schnell generation and API-driven cancellation/recovery passed on the
RTX 5070; its card advertises both Metal and CUDA. This qualification covers one
Windows CUDA rank and text-to-image. Image editing, other image families and
mixed image pipelines still require physical acceptance. Windows can also request
image work from a qualified Mac.

## Verification and release requirements

```powershell
uv run --no-sync basedpyright --pythonplatform Windows
uv run --no-sync basedpyright --pythonplatform Darwin
uv run --no-sync ruff check
uv run --no-sync ruff format --check
uv run --no-sync pytest --import-mode=importlib
.\scripts\windows\mlx\check-mlx-wheel.ps1 -Output build\acceptance\native-wheel.json
.venv\Scripts\python.exe scripts\windows\check_inference.py --model-dir C:\pinned-models --output build\acceptance\source-inference --exercise-cancel
```

The import mode avoids collisions between separate repository `tests` namespace
directories. Normal slow-test exclusions remain enabled. Hosted CPU CI uses
`mlx-none` without the private wheel; full type checks resolve MLX model
dependencies separately.

Wheel gates require valid >2 GiB safetensors with tensor reads beyond that offset,
normal GPU and spawned process exits, compiler-free CPU/CUDA compilation,
2/3/4-rank collectives over four dtypes, and missing, disconnected and stalled-peer
failures. `-LargeFile` also evaluates every tensor in a real model shard.
The same gates run inside the frozen runtime. Real HTTP tests cover repeated chat,
prefix cache, longer context, cancellation recovery and worker exit code 0.

Before publication, validate RTX 5070 alone, two M1s, PC with each M1, then all
three, changing master and rank order. Compare Mac-only baseline output, teardown
and namespace behavior. A clean Windows system must verify installation,
offline WebView2, Unicode/spaced paths, GPU inference, updates and model-preserving
uninstall. Windows CI and packaging jobs remain separate from Mac releases.
The previous Codex Security scan had zero source coverage; a functioning source
audit is also required before a stable release.

The [physical hardware checklist](windows-hardware-acceptance.md) includes the
Mac/Windows ring commands, model metadata requirements and acceptance matrix.
