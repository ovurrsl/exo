use crate::{
    native::{EngineProcess, RuntimePorts, StopOutcome},
    settings::{self, SavedSettings, Settings},
};
use serde::Serialize;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, AtomicU64, Ordering},
        Arc, Mutex,
    },
    time::Duration,
};
use tauri::{AppHandle, Manager};
use tauri_plugin_notification::NotificationExt;
use tauri_plugin_updater::UpdaterExt;

const UPDATE_ENDPOINT: &str =
    "https://github.com/ovurrsl/exo/releases/latest/download/windows-update.json";
#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateInfo {
    pub version: String,
    pub body: String,
}
#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Snapshot {
    pub status: String,
    pub detail: String,
    pub owned: bool,
    pub node_id: Option<String>,
    pub version: String,
    pub runtime_path: String,
    pub source_commit: Option<String>,
    pub source_modified: bool,
    pub mlx_version: Option<String>,
    pub data_path: String,
    pub log_path: String,
    pub update: Option<UpdateInfo>,
    pub updater_configured: bool,
}
pub struct Desktop {
    pub app: AppHandle,
    pub settings_path: PathBuf,
    pub runtime: PathBuf,
    pub data: PathBuf,
    pub log: PathBuf,
    pub client: reqwest::Client,
    pub api: String,
    ports: RuntimePorts,
    read_credentials: bool,
    settings: Mutex<Settings>,
    snapshot: Mutex<Snapshot>,
    process: tokio::sync::Mutex<Option<EngineProcess>>,
    settings_save: tokio::sync::Mutex<()>,
    stop_requested: AtomicBool,
    launch_generation: AtomicU64,
    pub last_diagnostics: Mutex<Option<PathBuf>>,
    pub dialog_active: AtomicBool,
    pub last_stop: Mutex<Option<StopOutcome>>,
}
impl Desktop {
    pub fn new(app: AppHandle) -> Result<Self, String> {
        let data = settings::data_directory()?;
        let settings_path = data.join("desktop").join("settings.json");
        let settings = Settings::load(&settings_path)?;
        let runtime = std::env::var_os("EXO_RUNTIME_DIR")
            .map(PathBuf::from)
            .unwrap_or(
                app.path()
                    .resource_dir()
                    .map_err(|e| e.to_string())?
                    .join("runtime"),
            );
        let version = app.package_info().version.to_string();
        Self::with_paths(
            app,
            data,
            runtime,
            settings_path,
            settings,
            version,
            RuntimePorts::default(),
            true,
        )
    }
    #[allow(clippy::too_many_arguments)]
    fn with_paths(
        app: AppHandle,
        data: PathBuf,
        runtime: PathBuf,
        settings_path: PathBuf,
        settings: Settings,
        version: String,
        ports: RuntimePorts,
        read_credentials: bool,
    ) -> Result<Self, String> {
        let identity = runtime_identity(&runtime);
        let log = data.join("exo_log").join("desktop-backend.log");
        let client = reqwest::Client::builder()
            .no_proxy()
            .timeout(Duration::from_secs(2))
            .build()
            .map_err(|e| e.to_string())?;
        let snapshot = Snapshot {
            status: "Stopped".into(),
            detail: "Starting automatically in 5 seconds.".into(),
            owned: false,
            node_id: None,
            version,
            source_commit: identity.commit,
            source_modified: identity.modified,
            mlx_version: identity.mlx,
            runtime_path: runtime.display().to_string(),
            data_path: data.display().to_string(),
            log_path: log.display().to_string(),
            update: None,
            updater_configured: option_env!("EXO_WINDOWS_UPDATER_PUBLIC_KEY")
                .is_some_and(|key| !key.trim().is_empty()),
        };
        Ok(Self {
            app,
            settings_path,
            runtime,
            data,
            log,
            client,
            api: format!("http://127.0.0.1:{}", ports.api),
            ports,
            read_credentials,
            settings: Mutex::new(settings),
            snapshot: Mutex::new(snapshot),
            process: tokio::sync::Mutex::new(None),
            settings_save: tokio::sync::Mutex::new(()),
            stop_requested: AtomicBool::new(false),
            launch_generation: AtomicU64::new(0),
            last_diagnostics: Mutex::new(None),
            dialog_active: AtomicBool::new(false),
            last_stop: Mutex::new(None),
        })
    }
    #[cfg(feature = "process-test-helper")]
    #[allow(dead_code)]
    pub fn isolated_probe(
        app: AppHandle,
        data: PathBuf,
        runtime: PathBuf,
        namespace: String,
        ports: RuntimePorts,
    ) -> Result<Self, String> {
        let settings_path = data.join("desktop").join("settings.json");
        let settings = Settings {
            namespace,
            offline: true,
            start_on_login: false,
            ..Settings::default()
        };
        let version = app.package_info().version.to_string();
        Self::with_paths(
            app,
            data,
            runtime,
            settings_path,
            settings,
            version,
            ports,
            false,
        )
    }
    pub fn snapshot(&self) -> Snapshot {
        self.snapshot.lock().expect("Snapshot lock").clone()
    }
    pub fn settings(&self) -> Settings {
        self.settings.lock().expect("Settings lock").clone()
    }
    pub fn saved_settings(&self) -> Result<SavedSettings, String> {
        Ok(SavedSettings {
            settings: self.settings(),
            hf_token_present: settings::read_token()?.is_some(),
        })
    }
    pub fn mark_onboarding(&self, completed: bool) -> Result<(), String> {
        let mut settings = self.settings.lock().map_err(|e| e.to_string())?;
        if settings.onboarding_completed != completed {
            settings.onboarding_completed = completed;
            settings.save(&self.settings_path)?;
        }
        Ok(())
    }
    fn status(&self, status: &str, detail: impl Into<String>, owned: bool, node: Option<String>) {
        let mut snapshot = self.snapshot.lock().expect("Snapshot lock");
        snapshot.status = status.into();
        snapshot.detail = detail.into();
        snapshot.owned = owned;
        snapshot.node_id = node;
    }
    pub fn cancel_pending_launch(&self) {
        self.launch_generation.fetch_add(1, Ordering::SeqCst);
    }
    pub async fn save(
        &self,
        settings: Settings,
        token: Option<String>,
        clear: bool,
    ) -> Result<SavedSettings, String> {
        let _save = self.settings_save.lock().await;
        settings.validate()?;
        settings::write_token(token.as_deref(), clear)?;
        settings::set_login_startup(settings.start_on_login)?;
        {
            let mut current = self.settings.lock().map_err(|e| e.to_string())?;
            settings.save(&self.settings_path)?;
            *current = settings;
        }
        if matches!(self.snapshot().status.as_str(), "Running" | "Starting") {
            self.stop().await?;
            self.start().await?;
        }
        self.saved_settings()
    }
    pub async fn cluster(&self) -> Result<Value, String> {
        let snapshot = self.snapshot();
        if !matches!(snapshot.status.as_str(), "Running" | "External") || snapshot.node_id.is_none()
        {
            return Ok(serde_json::json!({}));
        }
        self.client
            .get(format!("{}/state", self.api))
            .send()
            .await
            .map_err(|e| format!("Read cluster: {e}"))?
            .error_for_status()
            .map_err(|e| e.to_string())?
            .json()
            .await
            .map_err(|e| e.to_string())
    }
    async fn readiness(&self) -> Result<String, String> {
        let node: String = self
            .client
            .get(format!("{}/node_id", self.api))
            .send()
            .await
            .map_err(|e| e.to_string())?
            .error_for_status()
            .map_err(|e| e.to_string())?
            .json()
            .await
            .map_err(|e| e.to_string())?;
        let state: Value = self
            .client
            .get(format!("{}/state", self.api))
            .send()
            .await
            .map_err(|e| e.to_string())?
            .error_for_status()
            .map_err(|e| e.to_string())?
            .json()
            .await
            .map_err(|e| e.to_string())?;
        if !state.is_object() || state.get("topology").is_none() || node.is_empty() {
            return Err("The local API is not an EXO cluster endpoint.".into());
        }
        Ok(node)
    }
    pub async fn start(&self) -> Result<(), String> {
        self.cancel_pending_launch();
        self.stop_requested.store(false, Ordering::SeqCst);
        let mut process = self.process.lock().await;
        if process.is_some() {
            return Ok(());
        }
        let address = std::net::SocketAddr::from(([127, 0, 0, 1], self.ports.api));
        if std::net::TcpStream::connect_timeout(&address, Duration::from_millis(200)).is_ok() {
            match self.readiness().await {
                Ok(node) => self.status(
                    "External",
                    "An existing EXO process owns the API port. Read-only view.",
                    false,
                    Some(node),
                ),
                Err(_) => self.status(
                    "External",
                    format!(
                        "Port {} is used by another process; EXO was not started.",
                        self.ports.api
                    ),
                    false,
                    None,
                ),
            }
            return Ok(());
        }
        let executable = self.runtime.join("exo.exe");
        if !executable.is_file() {
            let message = format!(
                "The packaged EXO runtime is missing: {}",
                executable.display()
            );
            self.status("Failed", &message, false, None);
            return Err(message);
        }
        let config = self.settings();
        let token = if self.read_credentials {
            settings::read_token()?
        } else {
            None
        };
        self.status(
            "Starting",
            "Initializing EXO and checking the local API…",
            true,
            None,
        );
        let event = format!("Local\\exo-shutdown-{}", uuid::Uuid::new_v4().simple());
        let env = config.environment(
            &self.runtime,
            &self.data,
            token.as_deref(),
            &event,
            &self.snapshot().version,
        );
        let namespace = env.get("EXO_ZENOH_NAMESPACE").ok_or("Missing namespace")?;
        let engine = match EngineProcess::spawn(
            &executable,
            &self.data,
            &self.log,
            &env,
            event,
            namespace,
            self.ports,
        ) {
            Ok(engine) => engine,
            Err(error) => {
                self.status("Failed", &error, false, None);
                return Err(error);
            }
        };
        *process = Some(engine);
        let deadline = tokio::time::Instant::now() + Duration::from_secs(90);
        loop {
            if self.stop_requested.load(Ordering::SeqCst) {
                if let Some(engine) = process.take() {
                    engine.stop().await?;
                }
                self.status("Stopped", "Startup cancelled.", false, None);
                return Ok(());
            }
            if let Some(code) = process
                .as_ref()
                .ok_or("Missing backend process")?
                .exit_code()?
            {
                process.take();
                let message = format!("Backend exited with code {code}. Open Logs for details.");
                self.status("Failed", &message, false, None);
                return Err(message);
            }
            if let Ok(node) = self.readiness().await {
                self.status(
                    "Running",
                    "Connected to the local EXO API.",
                    true,
                    Some(node),
                );
                return Ok(());
            }
            if tokio::time::Instant::now() >= deadline {
                if let Some(engine) = process.take() {
                    engine.stop().await?;
                }
                let message =
                    "EXO did not become ready within 90 seconds. Open Logs for diagnostics.";
                self.status("Failed", message, false, None);
                return Err(message.into());
            }
            tokio::time::sleep(Duration::from_millis(300)).await;
        }
    }
    pub async fn stop(&self) -> Result<(), String> {
        self.cancel_pending_launch();
        self.stop_requested.store(true, Ordering::SeqCst);
        let mut process = self.process.lock().await;
        if let Some(engine) = process.take() {
            self.status(
                "Stopping",
                "Waiting for the EXO process tree to stop…",
                true,
                None,
            );
            match engine.stop().await {
                Ok(outcome) => *self.last_stop.lock().map_err(|e| e.to_string())? = Some(outcome),
                Err(error) => {
                    self.status("Failed", &error, false, None);
                    return Err(error);
                }
            }
        }
        // External processes are never signalled, terminated or adopted.
        self.status("Stopped", "", false, None);
        Ok(())
    }
    pub async fn restart(&self) -> Result<(), String> {
        self.stop().await?;
        self.start().await
    }
    pub fn require_owned(&self) -> Result<(), String> {
        let status = self.snapshot();
        if status.status == "Running" && status.owned {
            Ok(())
        } else {
            Err("Start the backend owned by this desktop before changing the cluster.".into())
        }
    }
    pub fn require_local_data_access(&self) -> Result<(), String> {
        if self.snapshot().status == "External" {
            Err(
                "The existing EXO process is read-only. Stop it before changing local EXO data."
                    .into(),
            )
        } else {
            Ok(())
        }
    }
    pub async fn refresh_process_status(&self) {
        if let Ok(mut process) = self.process.try_lock() {
            if let Some(engine) = process.as_ref() {
                if let Ok(Some(code)) = engine.exit_code() {
                    process.take();
                    self.status(
                        "Failed",
                        format!("Backend exited with code {code}. Open Logs for details."),
                        false,
                        None,
                    );
                }
            }
        }
        if self.snapshot().status == "External" {
            let address = std::net::SocketAddr::from(([127, 0, 0, 1], self.ports.api));
            if std::net::TcpStream::connect_timeout(&address, Duration::from_millis(200)).is_err() {
                self.status(
                    "Stopped",
                    "The external process has closed. EXO can now be started.",
                    false,
                    None,
                );
            }
        }
    }
    pub async fn check_update(&self, notify: bool) -> Result<(), String> {
        if self.settings().effective_offline() {
            return Err("Update checks are disabled in offline mode.".into());
        }
        let key = option_env!("EXO_WINDOWS_UPDATER_PUBLIC_KEY")
            .filter(|key| !key.trim().is_empty())
            .ok_or("This build has no update signing key configured.")?;
        let updater = self
            .app
            .updater_builder()
            .pubkey(key)
            .endpoints(vec![
                url::Url::parse(UPDATE_ENDPOINT).map_err(|e| e.to_string())?
            ])
            .map_err(|e| e.to_string())?
            .build()
            .map_err(|e| e.to_string())?;
        let update = updater
            .check()
            .await
            .map_err(|e| format!("Update check: {e}"))?;
        let info = update.map(|update| UpdateInfo {
            version: update.version,
            body: update.body.unwrap_or_default(),
        });
        let previously_seen = self.snapshot().update.map(|update| update.version);
        if notify {
            if let Some(info) = &info {
                if previously_seen.as_ref() != Some(&info.version) {
                    let _ = self
                        .app
                        .notification()
                        .builder()
                        .title("EXO update available")
                        .body(format!(
                            "Version {} is ready. Open EXO to install it.",
                            info.version
                        ))
                        .show();
                }
            }
        }
        self.snapshot.lock().map_err(|e| e.to_string())?.update = info;
        Ok(())
    }
    pub async fn install_update(&self) -> Result<(), String> {
        if self.settings().effective_offline() {
            return Err("Updates are disabled in offline mode.".into());
        }
        let key = option_env!("EXO_WINDOWS_UPDATER_PUBLIC_KEY")
            .filter(|key| !key.trim().is_empty())
            .ok_or("No update signing key configured")?;
        let updater = self
            .app
            .updater_builder()
            .pubkey(key)
            .endpoints(vec![
                url::Url::parse(UPDATE_ENDPOINT).map_err(|e| e.to_string())?
            ])
            .map_err(|e| e.to_string())?
            .build()
            .map_err(|e| e.to_string())?;
        let update = updater
            .check()
            .await
            .map_err(|e| e.to_string())?
            .ok_or("No newer signed Windows release available")?;
        // Download and verify before stopping the user's cluster.
        let bytes = update
            .download(|_, _| {}, || {})
            .await
            .map_err(|e| e.to_string())?;
        self.stop().await?;
        update.install(bytes).map_err(|e| e.to_string())?;
        Ok(())
    }
    pub fn launch_tasks(self: Arc<Self>) {
        let startup = self.clone();
        let generation = self.launch_generation.load(Ordering::SeqCst);
        tauri::async_runtime::spawn(async move {
            if let Err(error) =
                crate::settings::set_login_startup(startup.settings().start_on_login)
            {
                startup.status(
                    "Stopped",
                    format!("Login startup could not be configured: {error}"),
                    false,
                    None,
                );
            }
            tokio::time::sleep(Duration::from_secs(5)).await;
            if startup.launch_generation.load(Ordering::SeqCst) == generation {
                if let Err(error) = startup.start().await {
                    startup.status("Failed", error, false, None);
                }
            }
        });
        let monitor = self.clone();
        tauri::async_runtime::spawn(async move {
            loop {
                tokio::time::sleep(Duration::from_secs(1)).await;
                monitor.refresh_process_status().await;
                if monitor.snapshot().status == "Running"
                    && !monitor.settings().onboarding_completed
                {
                    if let Ok(response) = monitor
                        .client
                        .get(format!("{}/onboarding", monitor.api))
                        .send()
                        .await
                    {
                        if let Ok(value) = response.json::<Value>().await {
                            if value.get("completed") == Some(&Value::Bool(true)) {
                                let _ = monitor.mark_onboarding(true);
                            }
                        }
                    }
                }
            }
        });
        tauri::async_runtime::spawn(async move {
            tokio::time::sleep(Duration::from_secs(5)).await;
            loop {
                if self.snapshot().updater_configured && !self.settings().effective_offline() {
                    let _ = self.check_update(true).await;
                }
                tokio::time::sleep(Duration::from_secs(900)).await;
            }
        });
    }
}

#[derive(Default)]
struct RuntimeIdentity {
    commit: Option<String>,
    modified: bool,
    mlx: Option<String>,
}
fn runtime_identity(runtime: &std::path::Path) -> RuntimeIdentity {
    let path = runtime.join("runtime-manifest.json");
    let Ok(metadata) = std::fs::metadata(&path) else {
        return RuntimeIdentity::default();
    };
    if metadata.len() > 16 * 1024 * 1024 {
        return RuntimeIdentity::default();
    }
    let Ok(bytes) = std::fs::read(path) else {
        return RuntimeIdentity::default();
    };
    let Ok(value) = serde_json::from_slice::<Value>(&bytes) else {
        return RuntimeIdentity::default();
    };
    let commit = value["exo_commit"]
        .as_str()
        .filter(|commit| commit.len() == 40 && commit.bytes().all(|byte| byte.is_ascii_hexdigit()))
        .map(str::to_owned);
    let modified = value["tracked_working_diff_sha256"]
        .as_str()
        .filter(|hash| hash.len() == 64 && hash.bytes().all(|byte| byte.is_ascii_hexdigit()))
        .is_some_and(|hash| !hash.eq_ignore_ascii_case(&format!("{:x}", Sha256::digest(b""))));
    let mlx = value["runtime_gates"]["native_identity"]["mlx"]
        .as_str()
        .filter(|version| {
            !version.is_empty() && version.len() <= 128 && !version.chars().any(char::is_control)
        })
        .map(str::to_owned);
    RuntimeIdentity {
        commit,
        modified,
        mlx,
    }
}

#[cfg(test)]
mod identity_tests {
    use super::*;
    #[test]
    fn absent_runtime_identity_remains_unknown() {
        let identity = runtime_identity(std::path::Path::new("C:\\nonexistent-exo-runtime"));
        assert!(identity.commit.is_none());
        assert!(identity.mlx.is_none());
        assert!(!identity.modified);
    }
    #[test]
    fn manifest_identity_reports_real_build_and_local_changes() {
        let directory = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("target")
            .join(format!("identity-{}", uuid::Uuid::new_v4().simple()));
        std::fs::create_dir_all(&directory).unwrap();
        let path = directory.join("runtime-manifest.json");
        let commit = "931e0ff4a4fcdb0a5f04f7a71f3a5e4201867df3";
        let value = serde_json::json!({"exo_commit":commit,"tracked_working_diff_sha256":"a".repeat(64),"runtime_gates":{"native_identity":{"mlx":"0.32.3.dev20261009+win.3"}}});
        std::fs::write(&path, serde_json::to_vec(&value).unwrap()).unwrap();
        let identity = runtime_identity(&directory);
        assert_eq!(identity.commit.as_deref(), Some(commit));
        assert_eq!(identity.mlx.as_deref(), Some("0.32.3.dev20261009+win.3"));
        assert!(identity.modified);
        std::fs::write(&path, b"invalid JSON").unwrap();
        assert!(runtime_identity(&directory).commit.is_none());
        std::fs::remove_file(path).unwrap();
        std::fs::remove_dir(directory).unwrap();
    }
}
