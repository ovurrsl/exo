//! Test-only native WebView2 gate; never part of the desktop release target.
#[cfg(not(debug_assertions))]
compile_error!("The native Settings probe is restricted to debug/test builds");

mod settings_probe_gate;

#[allow(dead_code)]
#[path = "../src/commands.rs"]
mod commands;
#[allow(dead_code)]
#[path = "../src/desktop.rs"]
mod desktop;
#[allow(dead_code)]
#[path = "../src/firewall.rs"]
mod firewall;
#[allow(dead_code)]
#[path = "../src/native.rs"]
mod native;
#[allow(dead_code)]
#[path = "../src/settings.rs"]
mod settings;

use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicBool, Ordering},
        mpsc, Arc, Mutex,
    },
    time::{Duration, Instant},
};
use tauri::{Manager, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

const MEASURE: &str = include_str!("native_settings_probe.js");
const COLLECT_ERRORS: &str = r#"
window.__nativeSettingsProbeErrors = [];
window.addEventListener('error', event => window.__nativeSettingsProbeErrors.push(String(event.message)));
window.addEventListener('unhandledrejection', event => window.__nativeSettingsProbeErrors.push(String(event.reason)));
"#;

#[derive(Clone)]
struct Probe {
    root: PathBuf,
    namespace: String,
    deadline: Duration,
    report: Arc<Mutex<Value>>,
    calls: Arc<Mutex<BTreeMap<String, usize>>>,
    finished: Arc<AtomicBool>,
    theme: Option<tauri::Theme>,
}

impl Probe {
    fn write(&self) -> Result<(), String> {
        let report = self.report.lock().map_err(|error| error.to_string())?;
        std::fs::write(
            self.root.join("report.json"),
            serde_json::to_vec_pretty(&*report).map_err(|error| error.to_string())?,
        )
        .map_err(|error| error.to_string())
    }
}

fn sha256(path: &Path) -> Result<String, Box<dyn std::error::Error>> {
    Ok(format!("{:x}", Sha256::digest(std::fs::read(path)?)))
}

fn main() {
    if let Err(error) = run() {
        eprintln!("Native Settings probe failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let workspace = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../..")
        .canonicalize()?;
    let id = uuid::Uuid::new_v4().simple().to_string();
    let root = workspace
        .join("build/acceptance/native-settings-probe-20261010")
        .join(&id);
    std::fs::create_dir_all(&root)?;
    let runtime = PathBuf::from(std::env::var("EXO_SETTINGS_PROBE_WEBVIEW2")?).canonicalize()?;
    let webview_exe = runtime.join("msedgewebview2.exe");
    let deadline_ms: u64 = std::env::var("EXO_SETTINGS_PROBE_DEADLINE_MS")
        .unwrap_or_else(|_| "30000".into())
        .parse()?;
    if !(1..=60000).contains(&deadline_ms) {
        return Err("Deadline must be 1..60000 ms".into());
    }
    // Process-local environment override: no installed runtime/profile/registry changes.
    // Inherited WebView2 overrides must not redirect this helper to another profile.
    for variable in [
        "WEBVIEW2_USER_DATA_FOLDER",
        "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
        "WEBVIEW2_PIPE_FOR_SCRIPT_DEBUGGER",
        "WEBVIEW2_WAIT_FOR_SCRIPT_DEBUGGER",
    ] {
        std::env::remove_var(variable);
    }
    std::env::set_var("WEBVIEW2_BROWSER_EXECUTABLE_FOLDER", &runtime);
    let theme = match std::env::var("EXO_SETTINGS_PROBE_THEME").ok().as_deref() {
        None => None,
        Some("light") => Some(tauri::Theme::Light),
        Some("dark") => Some(tauri::Theme::Dark),
        _ => return Err("Theme must be light or dark".into()),
    };
    let identifier = format!("io.ovurrsl.exo.test.settings.{id}");
    let mut context = tauri::generate_context!();
    if tauri::is_dev() || context.config().bundle.active || !context.config().app.windows.is_empty()
    {
        return Err("Build with tests/native-settings-probe.conf.json as TAURI_CONFIG".into());
    }
    context.config_mut().identifier = identifier.clone();
    context.config_mut().app.app_directories_override = Some(
        tauri::utils::config::AppDirectoriesOverride::Root(root.join("app-directories")),
    );
    let mut frontend = BTreeMap::new();
    for path in [
        workspace.join("app/windows/dist/index.html"),
        workspace.join("app/windows/dist/icon.png"),
    ]
    .into_iter()
    .chain(
        std::fs::read_dir(workspace.join("app/windows/dist/assets"))?
            .map(|entry| entry.map(|entry| entry.path()))
            .collect::<Result<Vec<_>, _>>()?,
    ) {
        frontend.insert(
            path.strip_prefix(&workspace)?.display().to_string(),
            sha256(&path)?,
        );
    }
    let mut embedded = BTreeMap::new();
    for (key, _) in context.assets().iter() {
        let bytes = context
            .assets()
            .get(&tauri::utils::assets::AssetKey::from(key.as_ref()))
            .ok_or("Embedded asset unreadable")?;
        embedded.insert(key.to_string(), format!("{:x}", Sha256::digest(bytes)));
    }
    let config_hash = format!(
        "{:x}",
        Sha256::digest(include_bytes!("native-settings-probe.conf.json"))
    );
    let probe = Probe {
        namespace: format!("native-settings-probe-{id}"),
        root: root.clone(),
        deadline: Duration::from_millis(deadline_ms),
        calls: Arc::default(),
        finished: Arc::default(),
        theme,
        report: Arc::new(Mutex::new(json!({
            "passed": false, "sourceCommit": option_env!("EXO_SETTINGS_PROBE_SOURCE_COMMIT"),
            "binarySha256": sha256(&std::env::current_exe()?)?, "frontendSha256": frontend,
            "embeddedFrontendSha256": embedded, "probeConfigSha256": config_hash,
            "features": ["native-settings-probe", "process-test-helper", "tauri/custom-protocol"],
            "webviewRuntimePath": runtime, "webviewExeSha256": sha256(&webview_exe)?,
            "identifier": identifier, "root": root, "profile": root.join("webview-profile"),
            "deadlineMs": deadline_ms, "readonlyCommands": ["get_settings", "snapshot"],
            "helperPid": std::process::id(), "requestedTheme": theme.map(|theme| theme.to_string()),
            "usesProductionSettingsOpener": false, "credentialsRead": false,
            "backendStarted": false, "boundPorts": [], "samples": [], "pageLoads": [],
            "limitations": ["Hidden DOM render and IPC only; no production opener/focus/keyboard, physical DPI, painted screenshot, installation or running-backend acceptance"]
        }))),
    };
    probe.write()?;
    println!("Native Settings evidence: {}", root.display());
    let handler: fn(tauri::ipc::Invoke<tauri::Wry>) -> bool =
        tauri::generate_handler![commands::snapshot, commands::get_settings];
    let for_commands = probe.clone();
    let for_setup = probe.clone();
    let app = tauri::Builder::default()
        // No single-instance, updater, notification, tray or startup plugins/setup.
        .invoke_handler(move |invoke| {
            let name = invoke.message.command().to_owned();
            if let Ok(mut calls) = for_commands.calls.lock() {
                *calls.entry(name).or_default() += 1;
            }
            handler(invoke)
        })
        .setup(move |app| {
            let controller = Arc::new(desktop::Desktop::isolated_probe(
                app.handle().clone(),
                for_setup.root.join("data"),
                for_setup.root.join("runtime-unused"),
                for_setup.namespace.clone(),
                native::RuntimePorts {
                    api: 0,
                    zenoh: 0,
                    discovery: 0,
                },
            )?);
            app.manage(controller.clone());
            let app = app.handle().clone();
            let probe = for_setup.clone();
            let (done, completion) = mpsc::channel::<()>();
            let watchdog_app = app.clone();
            let watchdog_probe = probe.clone();
            std::thread::spawn(move || {
                if completion.recv_timeout(watchdog_probe.deadline).is_err()
                    && !watchdog_probe.finished.swap(true, Ordering::SeqCst)
                {
                    if let Ok(mut report) = watchdog_probe.report.lock() {
                        report["passed"] = json!(false);
                        report["error"] =
                            json!("Native Settings creation/callback deadline expired");
                    }
                    let _ = watchdog_probe.write();
                    watchdog_app.exit(1);
                }
            });
            std::thread::spawn(move || {
                let started = Instant::now();
                let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                    drive(&app, &probe, &controller, started)
                }))
                .unwrap_or_else(|_| Err("Probe driver panicked".into()));
                if probe.finished.swap(true, Ordering::SeqCst) {
                    return;
                }
                let passed = result.is_ok();
                if let Ok(mut report) = probe.report.lock() {
                    report["passed"] = json!(passed);
                    report["error"] = json!(result.err());
                    report["elapsedMs"] = json!(started.elapsed().as_millis());
                    report["ipcCalls"] = json!(*probe.calls.lock().expect("IPC count lock"));
                    report["backendStatusAfter"] = json!(controller.snapshot().status);
                    report["settingsFileWritten"] = json!(controller.settings_path.exists());
                }
                let persisted = probe.write().is_ok();
                // AppHandle belongs only to this process; no process-name or foreign-window action.
                let _ = done.send(());
                app.exit(if passed && persisted { 0 } else { 1 });
            });
            Ok(())
        })
        .build(context)?;
    let code = app.run_return(|_, _| {});
    {
        let mut report = probe.report.lock().map_err(|error| error.to_string())?;
        report["eventLoopReturned"] = json!(true);
        report["exitCode"] = json!(code);
        report["ipcCalls"] = json!(*probe.calls.lock().map_err(|error| error.to_string())?);
    }
    probe.write()?;
    if code != 0 || probe.report.lock().map_err(|error| error.to_string())?["passed"] != true {
        return Err(format!(
            "Native gate rejected; see {}",
            root.join("report.json").display()
        )
        .into());
    }
    Ok(())
}

fn evaluate(window: &WebviewWindow, script: &str, deadline: Instant) -> Result<Value, String> {
    let remaining = settings_probe_gate::callback_budget(deadline, Instant::now())?;
    let (send, receive) = mpsc::channel();
    window
        .eval_with_callback(script, move |result| {
            let _ = send.send(result);
        })
        .map_err(|error| error.to_string())?;
    let result = receive
        .recv_timeout(remaining)
        .map_err(|error| format!("Native eval callback: {error}"))?;
    settings_probe_gate::callback_budget(deadline, Instant::now())?;
    serde_json::from_str(&result).map_err(|error| format!("Native eval JSON: {error}: {result}"))
}

fn drive(
    app: &tauri::AppHandle,
    probe: &Probe,
    controller: &desktop::Desktop,
    started: Instant,
) -> Result<(), String> {
    let deadline = started + probe.deadline;
    let page_probe = probe.clone();
    let window = WebviewWindowBuilder::new(
        app,
        "settings",
        WebviewUrl::App("index.html?view=settings".into()),
    )
    .title("EXO Settings native test probe")
    .inner_size(640.0, 560.0)
    .min_inner_size(640.0, 520.0)
    .resizable(true)
    .visible(false)
    .focused(false)
    .skip_taskbar(true)
    .theme(probe.theme)
    .data_directory(probe.root.join("webview-profile"))
    .initialization_script(COLLECT_ERRORS)
    .on_page_load(move |_, payload| {
        if let Ok(mut report) = page_probe.report.lock() {
            report["pageLoads"]
                .as_array_mut()
                .expect("page load array")
                .push(json!({
                    "event": format!("{:?}", payload.event()), "url": payload.url().as_str()
                }));
        }
    })
    .build()
    .map_err(|error| error.to_string())?;
    let (send, receive) = mpsc::channel();
    window
        .with_webview(move |webview| {
            let version = unsafe {
                let mut value = Default::default();
                webview
                    .environment()
                    .BrowserVersionString(&mut value)
                    .map_err(|error| error.to_string())
                    .and_then(|_| {
                        let result = value.to_string().map_err(|error| error.to_string());
                        #[link(name = "ole32")]
                        unsafe extern "system" {
                            fn CoTaskMemFree(value: *mut std::ffi::c_void);
                        }
                        CoTaskMemFree(value.0.cast());
                        result
                    })
            };
            let _ = send.send(version);
        })
        .map_err(|error| error.to_string())?;
    let version = receive
        .recv_timeout(Duration::from_secs(2))
        .map_err(|error| error.to_string())??;
    let scale = window.scale_factor().map_err(|error| error.to_string())?;
    let hidden = !window.is_visible().map_err(|error| error.to_string())?;
    let focused = window.is_focused().map_err(|error| error.to_string())?;
    {
        let mut report = probe.report.lock().map_err(|error| error.to_string())?;
        report["actualWebviewVersion"] = json!(version);
        report["nativeScaleFactor"] = json!(scale);
        report["hidden"] = json!(hidden);
        report["focused"] = json!(focused);
    }
    if !hidden || focused {
        return Err("Probe window became visible or focused".into());
    }
    let data = controller.data.display().to_string();
    for height in [560, 520] {
        window
            .set_size(tauri::LogicalSize::new(640.0, f64::from(height)))
            .map_err(|error| error.to_string())?;
        for tab in settings_probe_gate::TABS {
            let click = format!("(() => {{ const button = Array.from(document.querySelectorAll('nav.tabs button')).find(button => button.querySelector('span')?.textContent.trim() === {}); if (button) button.click(); return Boolean(button); }})()", json!(tab));
            loop {
                evaluate(&window, &click, deadline)?;
                let sample = evaluate(&window, MEASURE, deadline)?;
                let result = settings_probe_gate::validate(
                    &sample,
                    tab,
                    &probe.namespace,
                    &controller.snapshot().version,
                    &data,
                )
                .and_then(|()| {
                    if sample["viewport"]["width"] == 640 && sample["viewport"]["height"] == height
                    {
                        if probe.theme.is_some_and(|theme| {
                            sample["appearance"]["dark"] != (theme == tauri::Theme::Dark)
                        }) {
                            Err(
                                "Requested native theme not reflected by WebView media query"
                                    .into(),
                            )
                        } else {
                            Ok(())
                        }
                    } else {
                        Err("Requested logical viewport not rendered yet".into())
                    }
                });
                {
                    let mut report = probe.report.lock().map_err(|error| error.to_string())?;
                    report["lastSample"] = sample.clone();
                    report["lastRejection"] = json!(result.as_ref().err());
                }
                if result.is_ok() {
                    let mut report = probe.report.lock().map_err(|error| error.to_string())?;
                    report["samples"].as_array_mut().expect("sample array").push(json!({ "tab": tab, "requestedLogicalSize": [640, height], "dom": sample }));
                    break;
                }
                if Instant::now() >= deadline {
                    return Err(format!("{tab}: {}", result.unwrap_err()));
                }
                std::thread::sleep(Duration::from_millis(50));
            }
        }
    }
    let calls = probe.calls.lock().map_err(|error| error.to_string())?;
    if calls.get("get_settings").copied().unwrap_or(0) == 0
        || calls.get("snapshot").copied().unwrap_or(0) == 0
        || calls
            .keys()
            .any(|name| !matches!(name.as_str(), "snapshot" | "get_settings"))
    {
        return Err("Readonly IPC allowlist/count violated".into());
    }
    if controller.snapshot().status != "Stopped" || controller.settings_path.exists() {
        return Err("Probe mutated backend/settings".into());
    }
    if Instant::now() >= deadline {
        return Err("Probe deadline expired before acceptance".into());
    }
    Ok(())
}
