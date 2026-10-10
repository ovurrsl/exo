//! Explicit, headless integration probe. It creates no WebView, tray, startup
//! registration, user credential, or global EXO data. Never bundled in releases.
#[allow(dead_code)]
#[path = "../src/desktop.rs"]
mod desktop;
#[path = "../src/native.rs"]
mod native;
#[allow(dead_code)]
#[path = "../src/settings.rs"]
mod settings;
use std::{
    net::{TcpListener, UdpSocket},
    path::PathBuf,
    time::Instant,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let runtime = PathBuf::from(std::env::var("EXO_DESKTOP_PROBE_RUNTIME")?).canonicalize()?;
    let workspace = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../..")
        .canonicalize()?;
    let data = workspace
        .join("build/windows-desktop-probe")
        .join(uuid::Uuid::new_v4().simple().to_string());
    std::fs::create_dir_all(&data)?;
    let namespace = format!("desktop-probe-{}", uuid::Uuid::new_v4().simple());
    let api = TcpListener::bind(("127.0.0.1", 0))?;
    let zenoh = TcpListener::bind(("127.0.0.1", 0))?;
    let discovery = UdpSocket::bind(("127.0.0.1", 0))?;
    let ports = native::RuntimePorts {
        api: api.local_addr()?.port(),
        zenoh: zenoh.local_addr()?.port(),
        discovery: discovery.local_addr()?.port(),
    };
    let mut context = tauri::generate_context!();
    context.config_mut().app.windows.clear();
    let app = tauri::Builder::default().build(context)?;
    let controller = desktop::Desktop::isolated_probe(
        app.handle().clone(),
        data.clone(),
        runtime.clone(),
        namespace.clone(),
        ports,
    )?;
    let executor = tokio::runtime::Runtime::new()?;
    let report = executor.block_on(async {
        // A foreign listener must never be adopted, signalled or treated as EXO.
        controller.start().await?;
        assert_eq!(controller.snapshot().status, "External");
        assert!(!controller.snapshot().owned);
        assert!(controller.snapshot().node_id.is_none());
        assert!(controller.cluster().await?.as_object().is_some_and(|value| value.is_empty()));
        assert!(controller.require_owned().is_err());
        assert!(controller.require_local_data_access().is_err());
        drop(api);
        drop(zenoh);
        drop(discovery);
        controller.refresh_process_status().await;
        assert_eq!(controller.snapshot().status, "Stopped");
        controller.save(controller.settings(), None, false).await?;
        assert!(!controller.settings_path.exists(), "Unchanged stopped settings were persisted");
        assert_eq!(controller.snapshot().status, "Stopped");
        let starting = Instant::now();
        controller.start().await?;
        let start_seconds = starting.elapsed().as_secs_f64();
        let ready = controller.snapshot();
        assert_eq!(ready.status, "Running");
        assert!(ready.owned);
        assert!(ready.node_id.as_ref().is_some_and(|node| !node.is_empty()));
        controller.save(controller.settings(), Some("  ".into()), false).await?;
        assert!(controller.last_stop.lock().map_err(|e| e.to_string())?.is_none(), "Unchanged running settings restarted the backend");
        assert!(!controller.settings_path.exists(), "Unchanged running settings were persisted");
        assert_eq!(controller.snapshot().node_id, ready.node_id);
        assert_eq!(controller.snapshot().status, "Running");
        controller.require_owned()?;
        let mut state = controller.cluster().await?;
        let node_id = ready.node_id.as_ref().ok_or("Missing node id")?;
        for _ in 0..120 {
            if state.get("nodeBackends").and_then(|nodes| nodes.get(node_id)).and_then(serde_json::Value::as_array).is_some_and(|backends| !backends.is_empty()) { break; }
            tokio::time::sleep(std::time::Duration::from_millis(250)).await;
            state = controller.cluster().await?;
        }
        let reported_backends = state.get("nodeBackends").and_then(|nodes| nodes.get(node_id)).cloned().unwrap_or(serde_json::Value::Null);
        if std::env::var_os("EXO_DESKTOP_PROBE_REQUIRE_CUDA").is_some() {
            assert!(reported_backends.as_array().is_some_and(|backends| backends.iter().any(|backend| backend == "MlxCuda")), "Frozen runtime did not advertise healthy MlxCuda: {reported_backends}");
        }
        std::fs::write(data.join("live-state.json"), serde_json::to_vec_pretty(&state).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
        let restarting = Instant::now();
        controller.restart().await?;
        let restart_seconds = restarting.elapsed().as_secs_f64();
        let restart_stop = controller.last_stop.lock().map_err(|e| e.to_string())?.clone().ok_or("Missing restart stop outcome")?;
        assert!(restart_stop.graceful, "Runtime ignored graceful event on restart");
        assert_eq!(restart_stop.exit_code, Some(0));
        assert_eq!(controller.snapshot().status, "Running");
        let stopping = Instant::now();
        controller.stop().await?;
        let stop_seconds = stopping.elapsed().as_secs_f64();
        let stop = controller.last_stop.lock().map_err(|e| e.to_string())?.clone().ok_or("Missing stop outcome")?;
        assert!(stop.graceful, "Runtime ignored graceful event");
        assert_eq!(stop.exit_code, Some(0));
        assert_eq!(controller.snapshot().status, "Stopped");
        assert!(std::net::TcpStream::connect(("127.0.0.1", ports.api)).is_err());
        // Redirected Windows/Python output can use the system code page.
        // Shutdown warnings are ASCII; decoding other bytes lossily keeps this
        // guard compatible with the real diagnostic archive's log reader.
        let log_bytes = std::fs::read(&controller.log).map_err(|e| e.to_string())?;
        let log = String::from_utf8_lossy(&log_bytes);
        for forced_warning in ["Child process didn't shut down successfully, terminating", "Child process didn't respond to SIGTERM, killing"] {
            assert!(!log.contains(forced_warning), "Python child shutdown used forced termination: {forced_warning}");
        }
        Ok::<_, String>(serde_json::json!({"runtime":runtime,"data":data,"namespace":namespace,"apiPort":ports.api,"zenohPort":ports.zenoh,"discoveryPort":ports.discovery,"ready":ready,"reportedBackends":reported_backends,"startSeconds":start_seconds,"restartSeconds":restart_seconds,"restartStop":restart_stop,"stopSeconds":stop_seconds,"stop":stop,"unchangedSettingsNoOpStopped":true,"unchangedSettingsNoOpRunning":true,"pythonForcedShutdownWarnings":false,"foreignPortReadOnly":true,"startupRegistryChanged":false,"credentialsRead":false,"guiWindowsCreated":false,"webviewsCreated":0,"trayCreated":false}))
    });
    match report {
        Ok(report) => {
            std::fs::write(
                data.join("probe-report.json"),
                serde_json::to_vec_pretty(&report)?,
            )?;
            println!("{}", serde_json::to_string_pretty(&report)?);
            Ok(())
        }
        Err(error) => {
            // Drop closes the owning Job Object even after an early error.
            eprintln!(
                "Probe failed: {error}. Isolated backend log: {}",
                controller.log.display()
            );
            Err(error.into())
        }
    }
}
