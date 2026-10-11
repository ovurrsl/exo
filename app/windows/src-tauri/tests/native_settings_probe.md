# Native Settings DOM/IPC probe

This debug/test-only bin uses the real Tauri event loop, fixed WebView2 runtime,
embedded production frontend and existing `snapshot` / `get_settings` commands.
It registers no mutating command or production startup/plugin/tray setup.
`Desktop::isolated_probe` disables credential reads and stays stopped, with unused
zero ports. Each run owns a UUID app identifier, namespace, app-directory root and
WebView profile under `build/acceptance/native-settings-probe-20261010/`.

Build the production frontend first. In a configured Rust PowerShell environment,
from `app/windows/src-tauri`:

```powershell
$env:TAURI_CONFIG = Get-Content tests/native-settings-probe.conf.json -Raw
$env:EXO_SETTINGS_PROBE_SOURCE_COMMIT = git rev-parse HEAD
$env:EXO_SETTINGS_PROBE_WEBVIEW2 = 'C:\absolute\path\to\fixed\webview2'
$env:EXO_SETTINGS_PROBE_THEME = 'light' # repeat with 'dark'
cargo run --features native-settings-probe --bin exo-native-settings-probe
```

The helper rejects a dev-server/packaging context before creating a WebView.
The feature enables `tauri/custom-protocol`; ordinary production/package feature
lists do not enable this bin. Release-profile builds of the helper are rejected.
`TAURI_CONFIG` affects compilation; keep the test override set during native runs.
The override disables bundling/resources/default windows. It does not replace the
production frontend or its IPC bridge. Inherited profile/debugging WebView2
environment overrides are cleared only in this process.

The hidden, unfocused, taskbar-free Settings window checks all five tab renders
at 640×560 and 640×520 logical sizes. Native synchronous eval callbacks return DOM
measurements; no JavaScript promise is mistaken for completed IPC. The unique
namespace/version in General and version/data path in About prove actual Rust
responses were rendered. Checks include positive nav/content/marker rects, loaded
CSS and logo, no script errors/alerts, unchanged Save disabled, stopped footer
copy, and no About Save. The report records frontend/dist and embedded asset
hashes, helper/config hash, source identity, actual COM WebView2 version and
native scale. Profiles/evidence are retained in their isolated run directories.

Each eval waits at most two seconds within a shared 30-second deadline. A watchdog
also covers WebView creation and requests exit of this helper's AppHandle only;
it never locates, kills or signals another EXO process/window. Failure exits 1,
success exits 0. To exercise the native failure path, set
`EXO_SETTINGS_PROBE_DEADLINE_MS=1`; expect rejection/exit 1, then unset it.

```powershell
cargo test --features process-test-helper,firewall-helper,native-settings-probe
cargo clippy --all-targets --features process-test-helper,firewall-helper,native-settings-probe -- -D warnings
```

CI builds the frontend before those commands. They compile the helper and run its
acceptance verifier units, **not its native main/event loop**; CI unit success is
not native acceptance. Actual native runs require Windows and fixed WebView2.

This gate does not call the production Settings opener (which shows/focuses the
window). It does not accept production opener/reuse/show/focus, real keyboard
navigation, painted screenshots, monitor/DPI transitions, running backend saves,
or installed/upgraded/uninstalled application behavior. Those remain separate
native/manual acceptance gates; browser density emulation cannot replace them.
