use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    path::{Path, PathBuf},
};

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Settings {
    pub schema_version: u32,
    pub namespace: String,
    pub hf_endpoint: String,
    pub offline: bool,
    pub enable_image_models: bool,
    pub fast_synch: bool,
    pub start_on_login: bool,
    pub default_models_directory: String,
    pub additional_models_directories: Vec<String>,
    pub read_only_models_directories: Vec<String>,
    pub custom_environment: BTreeMap<String, String>,
    pub onboarding_completed: bool,
}
impl Default for Settings {
    fn default() -> Self {
        Self {
            schema_version: 1,
            namespace: String::new(),
            hf_endpoint: String::new(),
            offline: false,
            enable_image_models: false,
            fast_synch: true,
            start_on_login: true,
            default_models_directory: String::new(),
            additional_models_directories: vec![],
            read_only_models_directories: vec![],
            custom_environment: BTreeMap::new(),
            onboarding_completed: false,
        }
    }
}
impl Settings {
    fn custom_value(&self, name: &str) -> Option<&str> {
        self.custom_environment
            .iter()
            .find(|(key, _)| key.eq_ignore_ascii_case(name))
            .map(|(_, value)| value.as_str())
    }
    pub fn protected_model_directories(&self, data: &Path, keep_models: bool) -> Vec<PathBuf> {
        let resolve = |raw: &str| {
            let expanded = if raw == "~" || raw.starts_with("~\\") || raw.starts_with("~/") {
                let home = self
                    .custom_value("USERPROFILE")
                    .map(PathBuf::from)
                    .or_else(|| std::env::var_os("USERPROFILE").map(PathBuf::from));
                home.map(|home| {
                    home.join(raw.trim_start_matches('~').trim_start_matches(['\\', '/']))
                })
                .unwrap_or_else(|| data.join(raw))
            } else {
                PathBuf::from(raw)
            };
            let drive = |path: &Path| match path.components().next() {
                Some(std::path::Component::Prefix(prefix)) => match prefix.kind() {
                    std::path::Prefix::Disk(drive) | std::path::Prefix::VerbatimDisk(drive) => {
                        Some(drive.to_ascii_uppercase())
                    }
                    _ => None,
                },
                _ => None,
            };
            let full = if expanded.is_absolute() {
                expanded
            } else if !expanded.has_root()
                && drive(&expanded).is_some()
                && drive(&expanded) == drive(data)
            {
                let prefix = expanded.components().next().expect("Drive prefix");
                data.join(
                    expanded
                        .strip_prefix(prefix.as_os_str())
                        .unwrap_or(&expanded),
                )
            } else {
                data.join(expanded)
            };
            let mut normal = PathBuf::new();
            for component in full.components() {
                match component {
                    std::path::Component::CurDir => {}
                    std::path::Component::ParentDir => {
                        normal.pop();
                    }
                    component => normal.push(component.as_os_str()),
                }
            }
            normal
        };
        let default = data.join("models");
        let same_default = |path: &Path| {
            path.to_string_lossy()
                .replace('/', "\\")
                .trim_start_matches("\\\\?\\")
                .eq_ignore_ascii_case(default.to_string_lossy().trim_start_matches("\\\\?\\"))
        };
        let mut protected: Vec<PathBuf> = self
            .additional_models_directories
            .iter()
            .chain(&self.read_only_models_directories)
            .filter(|path| !path.is_empty())
            .map(|path| resolve(path))
            .collect();
        for raw in self
            .custom_value("EXO_MODELS_DIRS")
            .into_iter()
            .chain(self.custom_value("EXO_MODELS_READ_ONLY_DIRS"))
            .flat_map(|paths| paths.split(';'))
            .filter(|path| !path.is_empty())
        {
            protected.push(resolve(raw));
        }
        for raw in (!self.default_models_directory.is_empty())
            .then_some(self.default_models_directory.as_str())
            .into_iter()
            .chain(self.custom_value("EXO_DEFAULT_MODELS_DIR"))
        {
            let path = resolve(raw);
            if !same_default(&path) {
                protected.push(path);
            }
        }
        if keep_models {
            protected.push(default);
        }
        protected
    }
    pub fn effective_offline(&self) -> bool {
        self.custom_environment
            .iter()
            .find(|(key, _)| key.eq_ignore_ascii_case("EXO_OFFLINE"))
            .map_or(self.offline, |(_, value)| {
                value.eq_ignore_ascii_case("true")
            })
    }
    pub fn load(path: &Path) -> Result<Self, String> {
        if !path.exists() {
            return Ok(Self::default());
        }
        let bytes = std::fs::read(path).map_err(|e| format!("Read settings: {e}"))?;
        let settings: Self =
            serde_json::from_slice(&bytes).map_err(|e| format!("Invalid settings file: {e}"))?;
        settings.validate()?;
        Ok(settings)
    }
    pub fn save(&self, path: &Path) -> Result<(), String> {
        self.validate()?;
        std::fs::create_dir_all(path.parent().ok_or("Invalid settings path")?)
            .map_err(|e| e.to_string())?;
        let temporary = path.with_extension("json.tmp");
        std::fs::write(
            &temporary,
            serde_json::to_vec_pretty(self).map_err(|e| e.to_string())?,
        )
        .map_err(|e| e.to_string())?;
        std::fs::rename(temporary, path).map_err(|e| e.to_string())
    }
    pub fn validate(&self) -> Result<(), String> {
        if self.schema_version != 1 {
            return Err("This settings version is unsupported.".into());
        }
        if self.namespace.contains('\0') {
            return Err("Invalid namespace.".into());
        }
        if !self.hf_endpoint.is_empty() {
            let endpoint =
                url::Url::parse(&self.hf_endpoint).map_err(|_| "Invalid Hugging Face endpoint")?;
            if !matches!(endpoint.scheme(), "https" | "http")
                || endpoint.host_str().is_none()
                || !endpoint.username().is_empty()
                || endpoint.password().is_some()
            {
                return Err("Endpoint must be an HTTP(S) URL.".into());
            }
        }
        for path in self
            .additional_models_directories
            .iter()
            .chain(&self.read_only_models_directories)
            .chain(std::iter::once(&self.default_models_directory))
        {
            if path.contains(['\0', ';']) {
                return Err("Model directories cannot contain a semicolon or NUL.".into());
            }
            if !path.is_empty() && !Path::new(path).is_absolute() {
                return Err("Choose an absolute model directory.".into());
            }
        }
        let mut names = std::collections::BTreeSet::new();
        for (key, value) in &self.custom_environment {
            let valid = key.chars().enumerate().all(|(index, character)| {
                character == '_'
                    || character.is_ascii_alphabetic()
                    || (index > 0 && character.is_ascii_digit())
            });
            if key.is_empty() || !valid || value.contains('\0') {
                return Err(format!("Invalid environment variable: {key}"));
            }
            let normalized = key.to_ascii_uppercase();
            if !names.insert(normalized.clone()) {
                return Err(format!("Duplicate environment variable: {key}"));
            }
            if matches!(
                normalized.as_str(),
                "EXO_WINDOWS_SHUTDOWN_EVENT"
                    | "EXO_HOME"
                    | "EXO_RUNTIME_DIR"
                    | "PATH"
                    | "PYTHONHOME"
                    | "PYTHONPATH"
                    | "EXO_API_PORT"
                    | "EXO_ZENOH_PORT"
                    | "EXO_DISCOVERY_PORT"
            ) {
                return Err(format!("{key} is managed by the desktop."));
            }
            if matches!(
                normalized.as_str(),
                "HF_TOKEN" | "HUGGING_FACE_HUB_TOKEN" | "HUGGINGFACE_HUB_TOKEN"
            ) {
                return Err(
                    "Save HF_TOKEN in the Hugging Face token field; it uses Credential Manager."
                        .into(),
                );
            }
        }
        Ok(())
    }
    pub fn environment(
        &self,
        runtime: &Path,
        data: &Path,
        token: Option<&str>,
        event: &str,
        version: &str,
    ) -> BTreeMap<String, String> {
        let mut result: BTreeMap<String, String> = std::env::vars()
            .map(|(key, value)| (key.to_ascii_uppercase(), value))
            .collect();
        result.insert("EXO_HOME".into(), data.display().to_string());
        result.insert("EXO_RUNTIME_DIR".into(), runtime.display().to_string());
        result.insert(
            "EXO_ZENOH_NAMESPACE".into(),
            if self.namespace.trim().is_empty() {
                version.into()
            } else {
                self.namespace.trim().into()
            },
        );
        result.insert("EXO_OFFLINE".into(), self.offline.to_string());
        result.insert(
            "EXO_ENABLE_IMAGE_MODELS".into(),
            self.enable_image_models.to_string(),
        );
        result.insert("EXO_FAST_SYNCH".into(), self.fast_synch.to_string());
        result.remove("HUGGING_FACE_HUB_TOKEN");
        result.remove("HUGGINGFACE_HUB_TOKEN");
        if let Some(token) = token {
            result.insert("HF_TOKEN".into(), token.into());
        } else {
            result.remove("HF_TOKEN");
        }
        if self.hf_endpoint.trim().is_empty() {
            result.remove("HF_ENDPOINT");
        } else {
            result.insert("HF_ENDPOINT".into(), self.hf_endpoint.trim().into());
        }
        if self.default_models_directory.is_empty() {
            result.remove("EXO_DEFAULT_MODELS_DIR");
        } else {
            result.insert(
                "EXO_DEFAULT_MODELS_DIR".into(),
                self.default_models_directory.clone(),
            );
        }
        result.insert(
            "EXO_MODELS_DIRS".into(),
            self.additional_models_directories.join(";"),
        );
        result.insert(
            "EXO_MODELS_READ_ONLY_DIRS".into(),
            self.read_only_models_directories.join(";"),
        );
        for (key, value) in &self.custom_environment {
            result.insert(key.to_ascii_uppercase(), value.clone());
        }
        result.insert("EXO_WINDOWS_SHUTDOWN_EVENT".into(), event.into());
        let namespace = result
            .get("EXO_ZENOH_NAMESPACE")
            .map(|value| value.trim())
            .filter(|value| !value.is_empty())
            .unwrap_or(version)
            .to_owned();
        result.insert("EXO_ZENOH_NAMESPACE".into(), namespace);
        result
    }
}
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SavedSettings {
    pub settings: Settings,
    pub hf_token_present: bool,
}
pub fn data_directory() -> Result<PathBuf, String> {
    std::env::var_os("LOCALAPPDATA")
        .map(|path| PathBuf::from(path).join("exo"))
        .ok_or("LOCALAPPDATA is not set".into())
}
pub fn token_entry() -> Result<keyring::Entry, String> {
    keyring::Entry::new("io.ovurrsl.exo.windows", "HF_TOKEN").map_err(|e| e.to_string())
}
pub fn read_token() -> Result<Option<String>, String> {
    match token_entry()?.get_password() {
        Ok(token) => Ok((!token.trim().is_empty()).then(|| token.trim().to_owned())),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(error) => Err(format!("Credential Manager: {error}")),
    }
}
pub fn write_token(token: Option<&str>, clear: bool) -> Result<(), String> {
    if !clear && token.is_some_and(|token| token.chars().any(char::is_control)) {
        return Err("The token contains invalid control characters.".into());
    }
    let entry = token_entry()?;
    if clear {
        match entry.delete_credential() {
            Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
            Err(error) => Err(error.to_string()),
        }
    } else if let Some(token) = token.map(str::trim).filter(|value| !value.is_empty()) {
        entry.set_password(token).map_err(|e| e.to_string())
    } else {
        Ok(())
    }
}
pub fn token_changed(
    current: Option<&str>,
    requested: Option<&str>,
    clear: bool,
) -> Result<bool, String> {
    if !clear && requested.is_some_and(|token| token.chars().any(char::is_control)) {
        return Err("The token contains invalid control characters.".into());
    }
    if clear {
        return Ok(current.is_some());
    }
    Ok(requested
        .map(str::trim)
        .filter(|token| !token.is_empty())
        .is_some_and(|token| Some(token) != current))
}
pub fn set_login_startup(enabled: bool) -> Result<(), String> {
    use winreg::{
        enums::{HKEY_CURRENT_USER, KEY_SET_VALUE},
        RegKey,
    };
    let key = RegKey::predef(HKEY_CURRENT_USER)
        .open_subkey_with_flags(
            "Software\\Microsoft\\Windows\\CurrentVersion\\Run",
            KEY_SET_VALUE,
        )
        .map_err(|e| e.to_string())?;
    if enabled {
        let executable = std::env::current_exe().map_err(|e| e.to_string())?;
        key.set_value(
            "EXO Windows",
            &format!("\"{}\" --background", executable.display()),
        )
        .map_err(|e| e.to_string())
    } else {
        match key.delete_value("EXO Windows") {
            Ok(()) => Ok(()),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
            Err(error) => Err(error.to_string()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn unchanged_token_requests_do_not_require_a_save() {
        for (current, requested, clear) in [
            (None, None, false),
            (Some("hf-secret"), None, false),
            (Some("hf-secret"), Some("  "), false),
            (Some("hf-secret"), Some(" hf-secret "), false),
            (None, None, true),
            (None, Some("ignored"), true),
        ] {
            assert!(!token_changed(current, requested, clear).unwrap());
        }
    }
    #[test]
    fn token_changes_and_invalid_requests_are_not_silently_skipped() {
        for (current, requested, clear) in [
            (None, Some("hf-new"), false),
            (Some("hf-old"), Some("hf-new"), false),
            (Some("hf-old"), None, true),
        ] {
            assert!(token_changed(current, requested, clear).unwrap());
        }
        for invalid in ["hf-secret\n", "\thf-secret\t", "\n", "\0"] {
            assert!(token_changed(Some("hf-secret"), Some(invalid), false).is_err());
        }
    }
    #[test]
    fn windows_environment_precedence_and_directories() {
        let mut settings = Settings {
            namespace: "my-cluster".into(),
            additional_models_directories: vec!["C:\\Models".into(), "D:\\Shared models".into()],
            ..Settings::default()
        };
        settings
            .custom_environment
            .insert("exo_zenoh_namespace".into(), "custom-cluster".into());
        let env = settings.environment(
            Path::new("C:\\EXO\\runtime"),
            Path::new("C:\\Data\\exo"),
            Some("secret"),
            "Local\\exo-shutdown-test",
            "1.2.3",
        );
        assert_eq!(env["EXO_ZENOH_NAMESPACE"], "custom-cluster");
        assert_eq!(env["EXO_MODELS_DIRS"], "C:\\Models;D:\\Shared models");
        assert_eq!(env["EXO_OFFLINE"], "false");
        assert_eq!(env["HF_TOKEN"], "secret");
    }
    #[test]
    fn managed_names_and_token_cannot_be_written_to_settings() {
        for key in [
            "exo_windows_shutdown_event",
            "HF_TOKEN",
            "hugging_face_hub_token",
            "HUGGINGFACE_HUB_TOKEN",
            "EXO_HOME",
            "Path",
            "PYTHONPATH",
            "EXO_API_PORT",
        ] {
            let mut settings = Settings::default();
            settings
                .custom_environment
                .insert(key.into(), "value".into());
            assert!(settings.validate().is_err());
        }
    }
    #[test]
    fn blank_namespace_falls_back_without_serializing_credentials() {
        let mut settings = Settings::default();
        settings
            .custom_environment
            .insert("EXO_ZENOH_NAMESPACE".into(), "  ".into());
        let environment = settings.environment(
            Path::new("C:\\runtime"),
            Path::new("C:\\data"),
            Some("hf-secret"),
            "Local\\exo-shutdown-abc",
            "0.3.70",
        );
        assert_eq!(environment["EXO_ZENOH_NAMESPACE"], "0.3.70");
        assert!(!serde_json::to_string(&settings)
            .unwrap()
            .contains("hf-secret"));
    }
    #[test]
    fn offline_custom_environment_also_blocks_updater_requests() {
        let mut settings = Settings::default();
        settings
            .custom_environment
            .insert("exo_offline".into(), "TRUE".into());
        assert!(settings.effective_offline());
    }
    #[test]
    fn uninstall_preserves_custom_environment_model_and_read_only_directories() {
        let data = Path::new("C:\\Users\\example\\AppData\\Local\\exo");
        let mut settings = Settings::default();
        settings.custom_environment.insert(
            "exo_default_models_dir".into(),
            "private\\..\\custom-models".into(),
        );
        settings.custom_environment.insert(
            "EXO_MODELS_READ_ONLY_DIRS".into(),
            "models;read-only;C:drive-relative;D:\\Shared".into(),
        );
        settings
            .custom_environment
            .insert("EXO_MODELS_DIRS".into(), "writable".into());
        let protected = settings.protected_model_directories(data, false);
        for expected in [
            data.join("custom-models"),
            data.join("models"),
            data.join("read-only"),
            data.join("drive-relative"),
            data.join("writable"),
            PathBuf::from("D:\\Shared"),
        ] {
            assert!(protected.contains(&expected), "{expected:?}");
        }
        assert!(!Settings::default()
            .protected_model_directories(data, false)
            .contains(&data.join("models")));
        assert!(Settings::default()
            .protected_model_directories(data, true)
            .contains(&data.join("models")));
    }
}
