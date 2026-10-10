use crate::{
    desktop::{Desktop, Snapshot},
    settings::{SavedSettings, Settings},
};
use serde_json::Value;
use std::{
    io::Write,
    os::windows::{ffi::OsStringExt, fs::MetadataExt},
    path::{Path, PathBuf},
    sync::Arc,
};
use tauri::{AppHandle, Manager, State, WebviewUrl, WebviewWindow, WebviewWindowBuilder};
use tauri_plugin_clipboard_manager::ClipboardExt;
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_opener::OpenerExt;
type DesktopState<'a> = State<'a, Arc<Desktop>>;
struct DialogGuard<'a>(&'a std::sync::atomic::AtomicBool);
impl<'a> DialogGuard<'a> {
    fn new(active: &'a std::sync::atomic::AtomicBool) -> Self {
        active.store(true, std::sync::atomic::Ordering::SeqCst);
        Self(active)
    }
}
impl Drop for DialogGuard<'_> {
    fn drop(&mut self) {
        self.0.store(false, std::sync::atomic::Ordering::SeqCst);
    }
}
fn local_window(window: &WebviewWindow) -> Result<(), String> {
    if matches!(window.label(), "main" | "settings")
        && local_ui_url(&window.url().map_err(|e| e.to_string())?)
    {
        Ok(())
    } else {
        Err("Command unavailable to this window".into())
    }
}
fn local_ui_url(url: &url::Url) -> bool {
    if !url.username().is_empty() || url.password().is_some() {
        return false;
    }
    (matches!(url.scheme(), "http" | "https")
        && url.host_str() == Some("tauri.localhost")
        && url.port().is_none())
        || (cfg!(debug_assertions)
            && url.scheme() == "http"
            && url.host_str() == Some("127.0.0.1")
            && url.port() == Some(1420))
}
#[tauri::command]
pub fn snapshot(window: WebviewWindow, desktop: DesktopState<'_>) -> Result<Snapshot, String> {
    local_window(&window)?;
    Ok(desktop.snapshot())
}
#[tauri::command]
pub async fn cluster_state(
    window: WebviewWindow,
    desktop: DesktopState<'_>,
) -> Result<Value, String> {
    local_window(&window)?;
    desktop.cluster().await
}
#[tauri::command]
pub fn get_settings(
    window: WebviewWindow,
    desktop: DesktopState<'_>,
) -> Result<SavedSettings, String> {
    local_window(&window)?;
    desktop.saved_settings()
}
#[tauri::command]
pub async fn save_settings(
    window: WebviewWindow,
    desktop: DesktopState<'_>,
    settings: Settings,
    hf_token: Option<String>,
    clear_hf_token: bool,
) -> Result<SavedSettings, String> {
    local_window(&window)?;
    desktop.save(settings, hf_token, clear_hf_token).await
}
#[tauri::command]
pub async fn start_backend(window: WebviewWindow, desktop: DesktopState<'_>) -> Result<(), String> {
    local_window(&window)?;
    desktop.start().await
}
#[tauri::command]
pub async fn stop_backend(window: WebviewWindow, desktop: DesktopState<'_>) -> Result<(), String> {
    local_window(&window)?;
    desktop.stop().await
}
#[tauri::command]
pub async fn restart_backend(
    window: WebviewWindow,
    desktop: DesktopState<'_>,
) -> Result<(), String> {
    local_window(&window)?;
    desktop.restart().await
}
pub async fn dashboard_url(desktop: &Desktop, section: &str) -> Result<(), String> {
    if !matches!(desktop.snapshot().status.as_str(), "Running" | "External")
        || desktop.snapshot().node_id.is_none()
    {
        return Err("Start EXO before opening the dashboard.".into());
    }
    let suffix = match section {
        "" => "/",
        "downloads" => "/#/downloads",
        "integrations" => "/#/integrations",
        "traces" => "/#/traces",
        "onboarding" => "/?reset-onboarding",
        _ => return Err("Unsupported dashboard section".into()),
    };
    desktop
        .app
        .opener()
        .open_url(format!("{}{suffix}", desktop.api), None::<&str>)
        .map_err(|e| e.to_string())
}
#[tauri::command]
pub async fn open_dashboard(
    window: WebviewWindow,
    desktop: DesktopState<'_>,
    section: String,
) -> Result<(), String> {
    local_window(&window)?;
    dashboard_url(&desktop, &section).await
}
#[tauri::command]
pub fn copy_api_url(
    window: WebviewWindow,
    app: AppHandle,
    desktop: DesktopState<'_>,
) -> Result<(), String> {
    local_window(&window)?;
    app.clipboard()
        .write_text(format!("{}/v1", desktop.api))
        .map_err(|e| e.to_string())
}
#[tauri::command]
pub async fn pick_directory(
    window: WebviewWindow,
    app: AppHandle,
    desktop: DesktopState<'_>,
) -> Result<Option<String>, String> {
    local_window(&window)?;
    let _dialog = DialogGuard::new(&desktop.dialog_active);
    tauri::async_runtime::spawn_blocking(move || {
        app.dialog()
            .file()
            .set_title("Choose model directory")
            .blocking_pick_folder()
            .map(|path| path.to_string())
    })
    .await
    .map_err(|e| e.to_string())
}
static SETTINGS_WINDOW_CREATION: tokio::sync::Mutex<()> = tokio::sync::Mutex::const_new(());

pub async fn settings_window(app: AppHandle) -> Result<(), String> {
    // WebView2 creation must not block a Windows command/menu event handler.
    // Serialize requests so a second invocation reuses the first window.
    let _creation = SETTINGS_WINDOW_CREATION.lock().await;
    tauri::async_runtime::spawn_blocking(move || build_settings_window(&app))
        .await
        .map_err(|error| error.to_string())?
}

fn build_settings_window(app: &AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("settings") {
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
        return Ok(());
    }
    WebviewWindowBuilder::new(
        app,
        "settings",
        WebviewUrl::App("index.html?view=settings".into()),
    )
    .title("EXO Settings")
    .inner_size(640.0, 560.0)
    .min_inner_size(640.0, 520.0)
    .resizable(true)
    .build()
    .map_err(|e| e.to_string())?;
    Ok(())
}
#[tauri::command]
pub async fn show_settings(window: WebviewWindow, app: AppHandle) -> Result<(), String> {
    local_window(&window)?;
    settings_window(app).await
}
#[tauri::command]
pub fn hide_window(window: WebviewWindow) -> Result<(), String> {
    local_window(&window)?;
    window.hide().map_err(|e| e.to_string())
}
#[tauri::command]
pub fn open_location(
    window: WebviewWindow,
    desktop: DesktopState<'_>,
    location: String,
) -> Result<(), String> {
    local_window(&window)?;
    if location == "network" {
        return desktop
            .app
            .opener()
            .open_url("ms-settings:network-status", None::<&str>)
            .map_err(|e| e.to_string());
    }
    let path = match location.as_str() {
        "logs" => desktop
            .log
            .parent()
            .ok_or("Invalid log directory")?
            .to_path_buf(),
        "data" => desktop.data.clone(),
        "runtime" => desktop.runtime.clone(),
        "diagnostics" => desktop
            .last_diagnostics
            .lock()
            .map_err(|e| e.to_string())?
            .clone()
            .ok_or("No diagnostics exported yet")?,
        _ => return Err("Unknown EXO location".into()),
    };
    if !path.exists() {
        if location == "logs" || location == "data" {
            std::fs::create_dir_all(&path).map_err(|e| e.to_string())?;
        } else {
            return Err("This EXO location does not exist yet".into());
        }
    }
    desktop
        .app
        .opener()
        .open_path(path.display().to_string(), None::<&str>)
        .map_err(|e| e.to_string())
}
#[tauri::command]
pub async fn check_update(window: WebviewWindow, desktop: DesktopState<'_>) -> Result<(), String> {
    local_window(&window)?;
    desktop.check_update(false).await
}
#[tauri::command]
pub async fn install_update(
    window: WebviewWindow,
    desktop: DesktopState<'_>,
) -> Result<(), String> {
    local_window(&window)?;
    desktop.install_update().await
}
async fn fixed_output(program: &str, arguments: &[&str]) -> String {
    let path = match diagnostic_program_path(program) {
        Ok(path) => path,
        Err(error) => return format!("Unavailable: {error}"),
    };
    let mut command = tokio::process::Command::new(path);
    command
        .args(arguments)
        .creation_flags(windows_sys::Win32::System::Threading::CREATE_NO_WINDOW)
        .kill_on_drop(true);
    match tokio::time::timeout(std::time::Duration::from_secs(10), command.output()).await {
        Ok(Ok(output)) => format!(
            "{}\n{}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        ),
        Ok(Err(error)) => format!("Unavailable: {error}"),
        Err(_) => "Unavailable: command timed out after 10 seconds.".into(),
    }
}
fn diagnostic_program_path(program: &str) -> Result<PathBuf, String> {
    let relative = match program {
        "powershell.exe" => "WindowsPowerShell\\v1.0\\powershell.exe",
        "ipconfig.exe" => "ipconfig.exe",
        "nvidia-smi.exe" => "nvidia-smi.exe",
        _ => return Err("Unsupported diagnostic executable".into()),
    };
    let mut buffer = vec![0u16; 32768];
    let length = unsafe {
        windows_sys::Win32::System::SystemInformation::GetSystemDirectoryW(
            buffer.as_mut_ptr(),
            buffer.len() as u32,
        )
    } as usize;
    if length == 0 || length >= buffer.len() {
        return Err("Windows system directory is unavailable".into());
    }
    let path = PathBuf::from(std::ffi::OsString::from_wide(&buffer[..length])).join(relative);
    if !path.is_file() {
        return Err(format!(
            "The system diagnostic executable is missing: {}",
            path.display()
        ));
    }
    Ok(path)
}
async fn collect_network() -> String {
    let mut output = String::new();
    for (heading, program, arguments) in [
        ("Network adapters and firewall profiles", "powershell.exe", vec!["-NoProfile", "-NonInteractive", "-Command", "Get-NetAdapter | Format-Table Name,InterfaceDescription,Status,LinkSpeed -Auto; Get-NetConnectionProfile | Format-Table Name,InterfaceAlias,NetworkCategory -Auto; Get-NetFirewallProfile | Format-Table Name,Enabled,DefaultInboundAction -Auto"]),
        ("IP configuration", "ipconfig.exe", vec!["/all"]),
        ("NVIDIA GPU", "nvidia-smi.exe", vec!["--query-gpu=name,driver_version,memory.total,memory.free,utilization.gpu,temperature.gpu,power.draw", "--format=csv"]),
    ] { output.push_str(&format!("## {heading}\n{}\n", fixed_output(program, &arguments).await)); }
    output
}
#[tauri::command]
pub async fn network_diagnostics(window: WebviewWindow) -> Result<String, String> {
    local_window(&window)?;
    Ok(collect_network().await)
}
#[tauri::command]
pub async fn configure_firewall(
    window: WebviewWindow,
    desktop: DesktopState<'_>,
) -> Result<(), String> {
    local_window(&window)?;
    desktop.require_owned()?;
    let installed = desktop
        .app
        .path()
        .resource_dir()
        .map_err(|e| e.to_string())?;
    let runtime = installed
        .join("runtime")
        .canonicalize()
        .map_err(|e| e.to_string())?;
    if desktop.runtime.canonicalize().map_err(|e| e.to_string())? != runtime {
        return Err("Firewall setup is available only for the installed bundled runtime.".into());
    }
    let helper = installed.join("firewall/exo-firewall-helper.exe");
    if !helper.is_file() {
        return Err("The bundled firewall helper is missing; reinstall EXO Windows.".into());
    }
    let _dialog = DialogGuard::new(&desktop.dialog_active);
    tauri::async_runtime::spawn_blocking(move || {
        crate::firewall::verify_runtime(&runtime, crate::firewall::EXPECTED_RUNTIME_SHA256)?;
        crate::firewall::elevate_helper(&helper)
    })
    .await
    .map_err(|e| e.to_string())?
}
pub fn redact_json(value: &mut Value) {
    match value {
        Value::Object(values) => {
            for (key, value) in values.iter_mut() {
                let name = key.to_ascii_lowercase().replace(['_', '-'], "");
                if [
                    "token",
                    "password",
                    "authorization",
                    "apikey",
                    "messages",
                    "prompt",
                    "attachments",
                    "environment",
                    "path",
                ]
                .iter()
                .any(|secret| name.contains(secret))
                    || matches!(
                        name.as_str(),
                        // Omit the whole request, including future content fields.
                        "taskparams"
                            | "input"
                            | "instructions"
                            | "content"
                            | "images"
                            | "imagehashes"
                            | "imagedata"
                            | "imageurl"
                            | "b64json"
                            | "tools"
                            | "stop"
                            // Errors and runner evidence may echo request content.
                            | "error"
                            | "errormessage"
                            | "errordescription"
                            | "message"
                            | "detail"
                            | "body"
                            | "evidence"
                            | "modeldirectory"
                            | "files"
                            | "fileprogress"
                    )
                {
                    *value = Value::String("[redacted]".into());
                } else {
                    redact_json(value);
                }
            }
        }
        Value::Array(values) => {
            for value in values {
                redact_json(value);
            }
        }
        _ => {}
    }
}
fn zip_entry(
    archive: &mut zip::ZipWriter<std::fs::File>,
    name: &str,
    content: &[u8],
) -> Result<(), String> {
    archive
        .start_file(
            name,
            zip::write::SimpleFileOptions::default()
                .compression_method(zip::CompressionMethod::Deflated),
        )
        .map_err(|e| e.to_string())?;
    archive.write_all(content).map_err(|e| e.to_string())
}
fn redact_known_secret(content: &[u8], token: Option<&str>) -> Vec<u8> {
    match token.filter(|token| !token.is_empty()) {
        Some(token) => {
            let escaped = serde_json::to_string(token).expect("Serialize string");
            String::from_utf8_lossy(content)
                .replace(token, "[redacted]")
                .replace(&escaped[1..escaped.len() - 1], "[redacted]")
                .into_bytes()
        }
        None => content.to_vec(),
    }
}
const DIAGNOSTICS_PRIVACY_NOTICE: &str = "Local export only. Raw logs, generation request payloads, free-form error text, environment values and local paths are omitted. Device and network information remains. Inspect this ZIP before sharing.";
const DIAGNOSTICS_PRIVACY_MANIFEST: &str = "EXO Windows diagnostics privacy\n\nThis ZIP is saved locally. EXO does not upload it automatically.\n\nIncluded: version and backend status, redacted cluster state, and Windows adapter, firewall and NVIDIA diagnostics. Task status and identifiers remain.\n\nOmitted: raw backend and runner logs; complete generation request parameters (including prompts, instructions, images and tools); free-form errors and runner evidence; environment values and local paths from JSON snapshots. Known saved credentials are also redacted. Raw logs cannot be reliably sanitized and are never read for this export.\n\nDevice names, model identifiers, IP and MAC addresses, network names, and other system/network details may remain. Inspect every included file before attaching this ZIP to a public issue or sharing it with support. Local logs remain available through Open Logs; review them separately before sharing.\n";

fn write_diagnostics_archive(
    destination: &Path,
    mut metadata: Value,
    mut state: Value,
    network: &str,
    token: Option<&str>,
) -> Result<(), String> {
    // The archive accepts only explicit diagnostic inputs, never a log directory.
    redact_json(&mut metadata);
    redact_json(&mut state);
    let file = std::fs::File::create(destination).map_err(|e| e.to_string())?;
    let mut archive = zip::ZipWriter::new(file);
    zip_entry(
        &mut archive,
        "PRIVACY.txt",
        DIAGNOSTICS_PRIVACY_MANIFEST.as_bytes(),
    )?;
    for (name, value) in [("metadata.json", metadata), ("cluster-state.json", state)] {
        zip_entry(
            &mut archive,
            name,
            &redact_known_secret(
                &serde_json::to_vec_pretty(&value).map_err(|e| e.to_string())?,
                token,
            ),
        )?;
    }
    zip_entry(
        &mut archive,
        "network.txt",
        &redact_known_secret(network.as_bytes(), token),
    )?;
    archive.finish().map_err(|e| e.to_string())?;
    Ok(())
}
#[tauri::command]
pub async fn export_diagnostics(
    window: WebviewWindow,
    desktop: DesktopState<'_>,
) -> Result<Option<String>, String> {
    local_window(&window)?;
    let app = desktop.app.clone();
    let _dialog = DialogGuard::new(&desktop.dialog_active);
    let destination = tauri::async_runtime::spawn_blocking(move || {
        app.dialog()
            .file()
            .set_title("Save local EXO diagnostics ZIP")
            .add_filter("ZIP archive", &["zip"])
            .set_file_name("exo-windows-diagnostics.zip")
            .blocking_save_file()
    })
    .await
    .map_err(|e| e.to_string())?;
    let Some(destination) = destination else {
        return Ok(None);
    };
    let path = destination.into_path().map_err(|e| e.to_string())?;
    let state = desktop
        .cluster()
        .await
        .unwrap_or_else(|error| serde_json::json!({"error": error}));
    let metadata = serde_json::json!({"desktop": desktop.snapshot(), "windows": std::env::consts::OS, "architecture": std::env::consts::ARCH, "notice": DIAGNOSTICS_PRIVACY_NOTICE, "privacy": {"rawLogsIncluded": false, "generationRequestPayloadsIncluded": false, "freeformErrorsIncluded": false, "deviceAndNetworkInformationIncluded": true}});
    let token = crate::settings::read_token()?;
    let network = collect_network().await;
    let path_for_archive = path.clone();
    tauri::async_runtime::spawn_blocking(move || {
        write_diagnostics_archive(
            &path_for_archive,
            metadata,
            state,
            &network,
            token.as_deref(),
        )
    })
    .await
    .map_err(|e| e.to_string())??;
    *desktop.last_diagnostics.lock().map_err(|e| e.to_string())? = Some(path.clone());
    Ok(Some(path.display().to_string()))
}
#[tauri::command]
pub fn open_issue(
    window: WebviewWindow,
    desktop: DesktopState<'_>,
    description: String,
) -> Result<(), String> {
    local_window(&window)?;
    if description.len() > 8000 {
        return Err("Issue description is too long.".into());
    }
    let body = format!("## Description\n{}\n\n## Environment\n- EXO Windows desktop: {}\n- OS: Windows {}\n\nAttach an inspected diagnostics ZIP if useful.", description, desktop.snapshot().version, std::env::consts::ARCH);
    let mut url =
        url::Url::parse("https://github.com/ovurrsl/exo/issues/new").map_err(|e| e.to_string())?;
    url.query_pairs_mut()
        .append_pair("title", "Windows desktop issue")
        .append_pair("body", &body);
    desktop
        .app
        .opener()
        .open_url(url.to_string(), None::<&str>)
        .map_err(|e| e.to_string())
}
#[tauri::command]
pub async fn reset_onboarding(
    window: WebviewWindow,
    desktop: DesktopState<'_>,
) -> Result<(), String> {
    local_window(&window)?;
    desktop.require_local_data_access()?;
    let path = desktop.data.join("onboarding_complete");
    match std::fs::remove_file(path) {
        Ok(()) => {}
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
        Err(error) => return Err(error.to_string()),
    }
    desktop.mark_onboarding(false)?;
    if desktop.snapshot().status == "Running" {
        dashboard_url(&desktop, "onboarding").await?;
    }
    Ok(())
}
#[tauri::command]
pub async fn delete_instance(
    window: WebviewWindow,
    desktop: DesktopState<'_>,
    instance_id: String,
) -> Result<(), String> {
    local_window(&window)?;
    desktop.require_owned()?;
    let state = desktop.cluster().await?;
    if state
        .get("instances")
        .and_then(Value::as_object)
        .is_none_or(|instances| !instances.contains_key(&instance_id))
    {
        return Err("Instance is no longer present in this cluster.".into());
    }
    let mut url = url::Url::parse(&desktop.api).map_err(|e| e.to_string())?;
    url.path_segments_mut()
        .map_err(|_| "Invalid API URL")?
        .push("instance")
        .push(&instance_id);
    desktop
        .client
        .delete(url)
        .send()
        .await
        .map_err(|e| e.to_string())?
        .error_for_status()
        .map_err(|e| e.to_string())?;
    Ok(())
}
#[tauri::command]
pub async fn cancel_download(
    window: WebviewWindow,
    desktop: DesktopState<'_>,
    node_id: String,
    model_id: String,
) -> Result<(), String> {
    local_window(&window)?;
    desktop.require_owned()?;
    let state = desktop.cluster().await?;
    let present = state
        .get("downloads")
        .and_then(|downloads| downloads.get(&node_id))
        .and_then(Value::as_array)
        .is_some_and(|downloads| {
            downloads.iter().any(|download| {
                ["DownloadOngoing"]
                    .iter()
                    .filter_map(|kind| download.get(kind))
                    .any(|download| {
                        download
                            .get("shardMetadata")
                            .and_then(Value::as_object)
                            .and_then(|shard| shard.values().next())
                            .and_then(|shard| shard.get("modelCard"))
                            .and_then(|card| card.get("modelId"))
                            .and_then(Value::as_str)
                            == Some(model_id.as_str())
                    })
            })
        });
    if !present {
        return Err("Cancel only an active download from this cluster.".into());
    }
    desktop
        .client
        .post(format!("{}/download/cancel", desktop.api))
        .json(&serde_json::json!({"target_node_id": node_id, "model_id": model_id}))
        .send()
        .await
        .map_err(|e| e.to_string())?
        .error_for_status()
        .map_err(|e| e.to_string())?;
    Ok(())
}
#[tauri::command]
pub async fn retry_download(
    window: WebviewWindow,
    desktop: DesktopState<'_>,
    node_id: String,
    shard: Value,
) -> Result<(), String> {
    local_window(&window)?;
    desktop.require_owned()?;
    let state = desktop.cluster().await?;
    let present = state
        .get("downloads")
        .and_then(|downloads| downloads.get(&node_id))
        .and_then(Value::as_array)
        .is_some_and(|downloads| {
            downloads.iter().any(|download| {
                download
                    .get("DownloadFailed")
                    .and_then(|failed| failed.get("shardMetadata"))
                    == Some(&shard)
            })
        });
    if !present {
        return Err("Retry only a failed download from this cluster.".into());
    }
    desktop
        .client
        .post(format!("{}/download/start", desktop.api))
        .json(&serde_json::json!({"target_node_id": node_id, "shard_metadata": shard}))
        .send()
        .await
        .map_err(|e| e.to_string())?
        .error_for_status()
        .map_err(|e| e.to_string())?;
    Ok(())
}
fn windows_path_key(path: &Path) -> String {
    path.to_string_lossy()
        .trim_start_matches("\\\\?\\")
        .replace('/', "\\")
        .trim_end_matches('\\')
        .to_ascii_lowercase()
}
fn paths_overlap(first: &Path, second: &Path) -> bool {
    let overlap = |first: &Path, second: &Path| {
        let first = windows_path_key(first);
        let second = windows_path_key(second);
        first == second
            || first.starts_with(&format!("{second}\\"))
            || second.starts_with(&format!("{first}\\"))
    };
    overlap(first, second)
        || overlap(
            &first.canonicalize().unwrap_or_else(|_| first.to_path_buf()),
            &second
                .canonicalize()
                .unwrap_or_else(|_| second.to_path_buf()),
        )
}
fn remove_owned_data(data: &Path, keep_models: bool, settings: &Settings) -> Result<(), String> {
    let expected = crate::settings::data_directory()?;
    if data != expected || data.file_name().is_none_or(|name| name != "exo") {
        return Err("Refusing to remove an unexpected data directory.".into());
    }
    if !data.exists() {
        return Ok(());
    }
    if std::fs::symlink_metadata(data)
        .map_err(|e| e.to_string())?
        .file_attributes()
        & 0x400
        != 0
    {
        return Err("EXO data is a linked directory; remove it manually after uninstall.".into());
    }
    remove_owned_data_contents(data, keep_models, settings)
}
fn remove_owned_data_contents(
    data: &Path,
    keep_models: bool,
    settings: &Settings,
) -> Result<(), String> {
    let protected = settings.protected_model_directories(data, keep_models);
    for entry in std::fs::read_dir(data).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        if protected
            .iter()
            .any(|path| paths_overlap(path, &entry.path()))
        {
            continue;
        }
        let kind = entry.file_type().map_err(|e| e.to_string())?;
        // Never traverse reparse/symlink model directories during uninstall.
        if kind.is_symlink()
            || std::fs::symlink_metadata(entry.path())
                .map_err(|e| e.to_string())?
                .file_attributes()
                & 0x400
                != 0
        {
            continue;
        }
        if kind.is_dir() {
            std::fs::remove_dir_all(entry.path()).map_err(|e| e.to_string())?;
        } else {
            std::fs::remove_file(entry.path()).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}
#[tauri::command]
pub async fn uninstall_app(
    window: WebviewWindow,
    desktop: DesktopState<'_>,
    keep_models: bool,
) -> Result<(), String> {
    local_window(&window)?;
    desktop.require_local_data_access()?;
    let executable = std::env::current_exe().map_err(|e| e.to_string())?;
    let uninstaller = executable
        .parent()
        .ok_or("Invalid app location")?
        .join("uninstall.exe");
    if !uninstaller.is_file() {
        return Err("This is a portable/development build. Use Windows Apps settings to uninstall an installed EXO release; models have been preserved.".into());
    }
    desktop.stop().await?;
    crate::settings::set_login_startup(false)?;
    crate::settings::write_token(None, true)?;
    remove_owned_data(&desktop.data, keep_models, &desktop.settings())?;
    desktop
        .app
        .opener()
        .open_path(uninstaller.display().to_string(), None::<&str>)
        .map_err(|e| e.to_string())?;
    desktop.app.exit(0);
    Ok(())
}
#[tauri::command]
pub async fn quit_app(window: WebviewWindow, desktop: DesktopState<'_>) -> Result<(), String> {
    local_window(&window)?;
    desktop.stop().await?;
    desktop.app.exit(0);
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn diagnostics_redact_nested_secrets_and_prompts() {
        let mut value = serde_json::json!({"task": {"messages":[{"content":"private"}],"HF_TOKEN":"secret","safe":"visible"}});
        redact_json(&mut value);
        assert_eq!(value["task"]["messages"], "[redacted]");
        assert_eq!(value["task"]["HF_TOKEN"], "[redacted]");
        assert_eq!(value["task"]["safe"], "visible");
    }
    #[test]
    fn known_credentials_are_redacted_outside_named_secret_fields() {
        assert_eq!(
            redact_known_secret(b"error: hf-private-token", Some("hf-private-token")),
            b"error: [redacted]"
        );
        assert_eq!(redact_known_secret(b"unchanged", Some("")), b"unchanged");
        let escaped =
            serde_json::to_vec(&serde_json::json!({"detail": "failed with hf-quoted\"token"}))
                .unwrap();
        assert!(
            !String::from_utf8(redact_known_secret(&escaped, Some("hf-quoted\"token")))
                .unwrap()
                .contains("hf-quoted")
        );
    }
    #[test]
    fn custom_model_paths_are_preserved_case_insensitively_on_windows() {
        assert!(paths_overlap(
            Path::new("C:\\DATA\\exo\\Models\\Qwen"),
            Path::new("c:/data/exo/models")
        ));
        assert!(!paths_overlap(
            Path::new("C:\\Data\\exo\\models-old"),
            Path::new("C:\\Data\\exo\\models")
        ));
    }
    #[test]
    fn remote_pages_and_backend_dashboard_have_no_desktop_bridge_authority() {
        for url in [
            "https://github.com/ovurrsl/exo",
            "http://127.0.0.1:52415",
            "http://tauri.localhost.evil",
            "http://tauri.localhost:52415",
            "data:text/html,exo",
        ] {
            assert!(!local_ui_url(&url::Url::parse(url).unwrap()), "{url}");
        }
        assert!(local_ui_url(
            &url::Url::parse("http://tauri.localhost/index.html?view=settings").unwrap()
        ));
    }
    #[test]
    fn diagnostics_executable_scope_rejects_arbitrary_paths() {
        assert!(diagnostic_program_path("cmd.exe").is_err());
        assert!(diagnostic_program_path("C:\\malicious\\powershell.exe").is_err());
        assert!(
            windows_path_key(&diagnostic_program_path("powershell.exe").unwrap())
                .ends_with("system32\\windowspowershell\\v1.0\\powershell.exe")
        );
    }
    #[test]
    fn uninstall_removes_owned_cache_but_keeps_custom_and_read_only_model_files() {
        let allowed = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/uninstall-tests");
        let root = allowed.join(uuid::Uuid::new_v4().simple().to_string());
        let data = root.join("exo");
        for directory in ["models", "custom-models", "read-only", "writable", "cache"] {
            std::fs::create_dir_all(data.join(directory)).unwrap();
            std::fs::write(data.join(directory).join("test.bin"), b"fixture").unwrap();
        }
        let mut settings = Settings::default();
        settings
            .custom_environment
            .insert("EXO_DEFAULT_MODELS_DIR".into(), "custom-models".into());
        settings
            .custom_environment
            .insert("EXO_MODELS_READ_ONLY_DIRS".into(), "read-only".into());
        settings
            .custom_environment
            .insert("EXO_MODELS_DIRS".into(), "writable".into());
        remove_owned_data_contents(&data, false, &settings).unwrap();
        for directory in ["custom-models", "read-only", "writable"] {
            assert!(data.join(directory).join("test.bin").is_file());
        }
        assert!(!data.join("models").exists());
        assert!(!data.join("cache").exists());
        assert!(root
            .canonicalize()
            .unwrap()
            .starts_with(allowed.canonicalize().unwrap()));
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn diagnostics_omit_canonical_generation_payloads_even_with_unknown_content_fields() {
        // These are the serialized TextGenerationTaskParams fields, not API messages.
        for (params_name, error_name) in [
            ("task_params", "error_message"),
            ("taskParams", "errorMessage"),
        ] {
            let mut value = serde_json::json!({
                "tasks": {"task-id": {"TextGeneration": {
                    "taskId": "task-id", "taskStatus": "Failed", "instanceId": "instance-id",
                    "commandId": "command-id", "errorType": "ValueError",
                    error_name: "private-input echoed by inference",
                    params_name: {
                        "model": "fixture/model", "input": [{"role": "user", "content": "private-input"}],
                        "instructions": "private-instructions", "max_output_tokens": 128,
                        "chat_template_messages": [{"content": [{"type": "image", "image_url": {"url": "private-image"}}]}],
                        "images": ["private-image"], "image_hashes": {"0": "private-image-hash"},
                        "tools": [{"description": "private-tool"}], "stop": "private-stop",
                        "future_request_field": "private-future-content"
                    }
                }}}
            });
            redact_json(&mut value);
            let task = &value["tasks"]["task-id"]["TextGeneration"];
            assert_eq!(task[params_name], "[redacted]");
            assert_eq!(task[error_name], "[redacted]");
            assert_eq!(task["errorType"], "ValueError");
            assert_eq!(task["taskStatus"], "Failed");
            assert_eq!(task["instanceId"], "instance-id");
            assert!(!value.to_string().contains("private-"));
        }
    }

    #[test]
    fn diagnostics_remove_nested_content_and_freeform_error_evidence() {
        let mut value = serde_json::json!({
            "input": [{"content": "private-input"}], "instructions": "private-instructions",
            "nested": [{"content": [{"text": "private-content", "image_data": "private-image"}]}],
            "runners": {"runner-id": {"RunnerFailed": {
                "errorMessage": "private-error", "diagnostics": [{"RunnerMetalGpuTimeout": {
                    "message": "private-error", "evidence": ["private-prompt"], "error_number": 5
                }}]
            }}},
            "error": "private-error", "detail": "private-detail", "authorization": "private-secret",
            "runtimePath": "C:\\Users\\private-user\\runtime", "custom_environment": {"UNNAMED": "private-secret"},
            "nodeMemory": {"node-id": {"ramAvailable": {"inBytes": 2048}}}, "lastEventAppliedIdx": 19
        });
        redact_json(&mut value);
        assert_eq!(
            value["nodeMemory"]["node-id"]["ramAvailable"]["inBytes"],
            2048
        );
        assert_eq!(value["lastEventAppliedIdx"], 19);
        assert_eq!(
            value["runners"]["runner-id"]["RunnerFailed"]["diagnostics"][0]
                ["RunnerMetalGpuTimeout"]["error_number"],
            5
        );
        assert!(!value.to_string().contains("private-"));
    }

    #[test]
    fn diagnostics_archive_never_includes_unstructured_logs_and_sanitizes_every_snapshot() {
        use std::io::Read;

        let allowed = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/diagnostics-tests");
        let root = allowed.join(uuid::Uuid::new_v4().simple().to_string());
        let logs = root.join("exo_log/runner");
        std::fs::create_dir_all(&logs).unwrap();
        // More logs than the former 20-file limit, with request repr and arbitrary text.
        for index in 0..21 {
            std::fs::write(logs.join(format!("runner-{index}.log")), b"INFO Starting task TextGeneration(input='private-raw-prompt')\nprivate-unstructured-text\n").unwrap();
        }
        let path = root.join("diagnostics.zip");
        write_diagnostics_archive(
            &path,
            serde_json::json!({
                "desktop": {"status": "Failed", "version": "0.3.70", "owned": true,
                    "detail": "private-error", "runtimePath": "C:\\Users\\private-user\\runtime",
                    "dataPath": "private-data", "logPath": "private-log", "sourceModified": false},
                "notice": DIAGNOSTICS_PRIVACY_NOTICE,
                "privacy": {"rawLogsIncluded": false, "generationRequestPayloadsIncluded": false}
            }),
            serde_json::json!({"tasks": {"task-id": {"ImageEdits": {
                "task_status": "Failed", "error_type": "RuntimeError", "error_message": "private-error",
                "task_params": {"prompt": "private-prompt", "image_data": "private-image"}
            }}}, "error": "private-error", "nodeMemory": {"node-id": {"available": 2048}},
                "topology": {"node-id": {"address": "192.0.2.1", "label": "hf-fixture-secret"}}}),
            "Fixture adapter 192.0.2.1 credential=hf-fixture-secret",
            Some("hf-fixture-secret"),
        ).unwrap();
        let mut archive = zip::ZipArchive::new(std::fs::File::open(path).unwrap()).unwrap();
        assert_eq!(archive.len(), 4);
        let mut names = vec![];
        for index in 0..archive.len() {
            let mut entry = archive.by_index(index).unwrap();
            names.push(entry.name().to_owned());
            let mut content = String::new();
            entry.read_to_string(&mut content).unwrap();
            assert!(!content.contains("private-"), "{}", entry.name());
            assert!(!content.contains("hf-fixture-secret"), "{}", entry.name());
            match entry.name() {
                "metadata.json" => {
                    let value: Value = serde_json::from_str(&content).unwrap();
                    assert_eq!(value["desktop"]["status"], "Failed");
                    assert_eq!(value["desktop"]["owned"], true);
                    assert_eq!(value["desktop"]["version"], "0.3.70");
                    assert_eq!(value["privacy"]["rawLogsIncluded"], false);
                    assert_eq!(value["privacy"]["generationRequestPayloadsIncluded"], false);
                }
                "cluster-state.json" => {
                    let value: Value = serde_json::from_str(&content).unwrap();
                    assert_eq!(
                        value["tasks"]["task-id"]["ImageEdits"]["task_status"],
                        "Failed"
                    );
                    assert_eq!(value["nodeMemory"]["node-id"]["available"], 2048);
                }
                "network.txt" => assert!(content.contains("192.0.2.1")),
                "PRIVACY.txt" => {}
                name => panic!("Unexpected archive entry: {name}"),
            }
        }
        names.sort();
        assert_eq!(
            names,
            [
                "PRIVACY.txt",
                "cluster-state.json",
                "metadata.json",
                "network.txt"
            ]
        );
        assert_eq!(std::fs::read_dir(logs).unwrap().count(), 21);
        assert!(root
            .canonicalize()
            .unwrap()
            .starts_with(allowed.canonicalize().unwrap()));
        std::fs::remove_dir_all(root).unwrap();
    }
}
