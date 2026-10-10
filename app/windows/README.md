# EXO Windows desktop

The tray panel follows `app/EXO/EXO/ContentView.swift`: 340 logical pixels,
compact status and memory summary, device glyphs, collapsed node/instance lists
and plain menu rows. Settings follow the Mac five-tab layout at 640×560.
Light/dark semantic colors match the AppKit values sampled on the reference M1;
Windows supplies its native window chrome and available fonts. The original Mac
black/yellow app icon is reused. Mac sources are never changed by this build.

Independent Windows-only Tauri 2 / Svelte 5 workspace. The Swift app, Mac
packaging, and root Cargo workspace are not changed by this app.

The tray shows the live cluster topology, devices, memory, instances, tasks and
downloads. The full existing EXO dashboard opens in your default browser. Five
settings tabs match the Mac app's organization. Hugging Face tokens are stored
in Windows Credential Manager, separately from JSON settings.

## Develop and verify

Use Node.js 22+, a current stable Rust/MSVC toolchain (Rust 1.95+), Visual Studio
2022 C++ Build Tools with the Windows SDK, and WebView2 for development.

```powershell
cd app/windows
npm ci
npm run check
npm test
npm run test:ui
npm run build
cargo test --manifest-path src-tauri/Cargo.toml --features process-test-helper,firewall-helper
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets --features process-test-helper,firewall-helper -- -D warnings
```

UI tests use installed Chrome in headless mode. Native tests launch only hidden
test helpers; they verify the named shutdown event, whole-tree Job Object
ownership, Windows quoting, and the ten-second forced-shutdown fallback. They
do not start the desktop, write login entries or modify firewall rules.

To verify a staged frozen runtime through the actual desktop controller without
opening a window or writing login settings, run the explicit test-only probe:

```powershell
$env:EXO_DESKTOP_PROBE_RUNTIME = (Resolve-Path ../../dist/windows/exo).Path
$env:EXO_DESKTOP_PROBE_REQUIRE_CUDA = '1'
cargo run --manifest-path src-tauri/Cargo.toml --features process-test-helper --bin exo-frozen-desktop-probe
```

The probe allocates separate API/Zenoh/discovery ports and a random namespace,
uses offline mode, excludes Credential Manager access, and writes its report,
live state and logs only under repository `build/windows-desktop-probe/<uuid>`.
It exercises an occupied foreign port, readiness, restart and event shutdown.
With `EXO_DESKTOP_PROBE_REQUIRE_CUDA` set it also requires healthy `MlxCuda`
advertisement. Forced Python child-shutdown warnings fail the probe, even when
the primary process exits successfully.
The probe binary is excluded from normal desktop builds and installers.

Set `EXO_DESKTOP_LIVE_STATE` to the probe's `live-state.json` before running
`npm test` and `npm run test:ui` to check parsing and rendering against the
captured runtime response. The generated `test-results/live-tray.png` uses that
response through the test bridge; settings and firewall screenshots use mock
command results. UI tests do not access Credential Manager, change startup
registration, or apply firewall rules. Unknown system metrics render as `N/A`;
the NVIDIA device's board power is not substituted for whole-system power.
Pending catalog entries appear in the existing dashboard, while the tray shows
active downloads and failures only.

For an interactive development launch, stage the runtime as described below
or set `EXO_RUNTIME_DIR` to an existing frozen runtime directory, then run
`npm run tauri -- dev`. Closing the popover/settings keeps EXO running; Quit
stops the owned process tree. The desktop never stops an external EXO process
using the same API port.

## Runtime and release contract

`src-tauri/resources/runtime/` contains the **contents** of the PyInstaller
onedir runtime: `exo.exe`, `_internal/`, its DLLs, dashboard, model cards and
resource data. The Tauri resource map installs these at `runtime/` beside the
desktop. The package builder must validate the runtime manifest and CUDA
health gates before staging it. `scripts/windows/build-installer.ps1` owns that
pipeline. A desktop binary without a staged runtime reports its missing path
and does not launch a development Python environment.

```powershell
npm run tauri -- build --bundles nsis
```

The NSIS installer is per-user and embeds an app-owned WebView2 **fixed runtime**.
The pinned Tauri CLI 2.12.1 NSIS template sets the default installation directory
to `%LOCALAPPDATA%\Programs\EXO` and compresses files individually to avoid NSIS's
2 GiB solid temporary-block limit. Existing upgrade locations and explicit `/D`
installation paths keep upstream behavior.
`scripts/windows/prepare-webview2.ps1` stages the pinned Microsoft CAB after
checking its SHA-256, browser executable hash and Microsoft signature. Tauri
loads `resources/webview2` beside the installed desktop, without relying on the
machine's Evergreen registration. The build host downloads this payload; the
end-user installation does not need internet. Fixed WebView2 security updates
must ship with Windows application releases by reviewing and updating
`packaging/windows/webview2-runtime.json`; system Evergreen updates do not replace
this app-owned runtime. Model and application data live at `%LOCALAPPDATA%\exo`; custom and
read-only model directories are preserved. The explicit uninstall dialog
offers to retain default downloaded models. NSIS removes the owned login entry
while leaving external model directories untouched.

The runtime starts hidden and suspended, joins a kill-on-close Windows Job
Object, then resumes. A random `Local\exo-shutdown-<32 hex digits>` Event is
accessible only to the current user and SYSTEM. Its name is passed in
`EXO_WINDOWS_SHUTDOWN_EVENT`. Stop signals that event, waits ten seconds for
the entire tree, then terminates the job if necessary. The Python Windows
watcher owns graceful engine shutdown. Restart waits for the previous tree.
Running is shown only after `/node_id` and `/state` respond successfully.

## Signed updates and reports

Set `EXO_WINDOWS_UPDATER_PUBLIC_KEY` at Rust build time to the release owner's
Tauri/minisign public key. Set Tauri's signing-key environment variables on the
release builder. Never commit private keys. The fixed fork feed is:

`https://github.com/ovurrsl/exo/releases/latest/download/windows-update.json`

The feed's Windows platform entry references the signed complete NSIS update
artifact. GUI, engine, dashboard and MLX are updated together. The desktop
checks every fifteen minutes and notifies once per new version; only an
explicit Install action downloads/installs. Downloads are verified before the
backend stops. Offline mode disables all update requests. Builds without a
public key clearly report that update support is unconfigured.
Update signatures must include the release version in the signed trusted
comment; current pinned Tauri CLI signing provides it. Downgrades are rejected.

Bug Report exports a local ZIP with bounded log tails, redacted cluster state,
adapter/firewall/NVIDIA diagnostics and version metadata. The UI opens a draft
issue in `ovurrsl/exo`; it never uploads diagnostics automatically. Inspect
logs before attaching the ZIP.

The IPC bridge exposes fixed desktop actions and fixed loopback EXO requests.
It has no arbitrary shell, filesystem or URL command. Only the packaged local
main/settings windows can call it; no remote dashboard is given desktop IPC.
The Rust bridge checks both window labels and their actual packaged origin.
Diagnostics use an allowlist of executable paths from the Windows system
directory, without searching the runtime directory or PATH. Managed process
paths, ports and shutdown events cannot be overridden in custom environment
settings. Token aliases are excluded from JSON settings and inherited aliases
are removed before backend launch. Model preservation includes custom
environment overrides, read-only directories and Windows path aliases.

The Advanced settings tab's explicit local-network action elevates only the
separate bundled `firewall/exo-firewall-helper.exe` through Windows UAC. The
helper accepts only `--apply`, derives the neighboring `runtime/exo.exe`, and
checks the validated runtime manifest plus its build-time pinned SHA256.
`EXO_WINDOWS_FIREWALL_RUNTIME_SHA256` must be set when building both binaries;
`scripts/windows/build-installer.ps1` builds and stages the helper first. Missing
or changed hashes fail closed. It invokes the absolute Windows system
`netsh.exe` with structured arguments, managing only the three `EXO.Windows.*`
rules. All allow rules require the exact EXO executable, Private/Domain networks
and LocalSubnet peers: UDP 52413, TCP 52414/52415 and the MLX ring TCP
49152–65535 range. Desktop/native tests never apply these rules to the host.
