//! Narrow, install-relative firewall contract shared by the UI and helper.
//! Never executes EXO or user supplied commands with elevation.
use sha2::{Digest, Sha256};
use std::{
    ffi::{OsStr, OsString},
    io::Read,
    os::windows::ffi::{OsStrExt, OsStringExt},
    path::{Path, PathBuf},
};

pub const EXPECTED_RUNTIME_SHA256: Option<&str> =
    option_env!("EXO_WINDOWS_FIREWALL_RUNTIME_SHA256");

pub struct Rule {
    pub name: &'static str,
    pub protocol: &'static str,
    pub ports: &'static str,
}
pub const RULES: [Rule; 3] = [
    Rule {
        name: "EXO.Windows.Discovery",
        protocol: "UDP",
        ports: "52413",
    },
    Rule {
        name: "EXO.Windows.Control",
        protocol: "TCP",
        ports: "52414,52415",
    },
    Rule {
        name: "EXO.Windows.MlxRing",
        protocol: "TCP",
        ports: "49152-65535",
    },
];

pub fn add_arguments(rule: &Rule, program: &Path) -> Vec<OsString> {
    vec![
        "advfirewall".into(),
        "firewall".into(),
        "add".into(),
        "rule".into(),
        format!("name={}", rule.name).into(),
        "dir=in".into(),
        "action=allow".into(),
        {
            let mut value = OsString::from("program=");
            // Firewall's application path uses ordinary Win32 spelling;
            // canonicalize() supplies a verbatim prefix on Windows.
            let wide: Vec<u16> = program.as_os_str().encode_wide().collect();
            if wide.starts_with(&[92, 92, 63, 92, 85, 78, 67, 92]) {
                value.push(OsString::from_wide(
                    &[&[92u16, 92][..], &wide[8..]].concat(),
                ));
            } else if wide.starts_with(&[92, 92, 63, 92]) {
                value.push(OsString::from_wide(&wide[4..]));
            } else {
                value.push(program);
            }
            value
        },
        format!("protocol={}", rule.protocol).into(),
        format!("localport={}", rule.ports).into(),
        "remoteip=localsubnet".into(),
        "profile=private,domain".into(),
        "enable=yes".into(),
    ]
}
pub fn delete_arguments(rule: &Rule) -> Vec<OsString> {
    ["advfirewall", "firewall", "delete", "rule"]
        .into_iter()
        .map(OsString::from)
        .chain(std::iter::once(format!("name={}", rule.name).into()))
        .collect()
}
pub fn helper_runtime_path(helper: &Path) -> Result<PathBuf, String> {
    if helper.file_name().is_none_or(|name| {
        !name
            .to_string_lossy()
            .eq_ignore_ascii_case("exo-firewall-helper.exe")
    }) {
        return Err("Unexpected firewall helper filename.".into());
    }
    let directory = helper.parent().ok_or("Missing helper directory")?;
    if directory
        .file_name()
        .is_none_or(|name| !name.to_string_lossy().eq_ignore_ascii_case("firewall"))
    {
        return Err("The firewall helper must be in its installed firewall directory.".into());
    }
    Ok(directory
        .parent()
        .ok_or("Missing installation directory")?
        .join("runtime"))
}
pub fn system_directory() -> Result<PathBuf, String> {
    let mut buffer = vec![0u16; 32768];
    let length = unsafe {
        windows_sys::Win32::System::SystemInformation::GetSystemDirectoryW(
            buffer.as_mut_ptr(),
            buffer.len() as u32,
        )
    } as usize;
    if length == 0 || length >= buffer.len() {
        return Err("Windows system directory unavailable.".into());
    }
    Ok(PathBuf::from(OsString::from_wide(&buffer[..length])))
}
pub fn verify_runtime(runtime: &Path, expected: Option<&str>) -> Result<PathBuf, String> {
    let expected = expected
        .filter(|hash| hash.len() == 64 && hash.bytes().all(|byte| byte.is_ascii_hexdigit()))
        .ok_or("This build has no validated firewall runtime hash; use a bundled installer.")?;
    let runtime = runtime
        .canonicalize()
        .map_err(|e| format!("Locate runtime: {e}"))?;
    let executable = runtime
        .join("exo.exe")
        .canonicalize()
        .map_err(|e| format!("Locate EXO executable: {e}"))?;
    if executable.parent() != Some(runtime.as_path())
        || executable
            .file_name()
            .is_none_or(|name| !name.to_string_lossy().eq_ignore_ascii_case("exo.exe"))
    {
        return Err("The EXO executable must be directly inside its runtime directory.".into());
    }
    let manifest_path = runtime.join("runtime-manifest.json");
    if std::fs::metadata(&manifest_path)
        .map_err(|e| e.to_string())?
        .len()
        > 16 * 1024 * 1024
    {
        return Err("Runtime manifest is too large.".into());
    }
    let manifest: serde_json::Value =
        serde_json::from_slice(&std::fs::read(manifest_path).map_err(|e| e.to_string())?)
            .map_err(|e| format!("Invalid runtime manifest: {e}"))?;
    if manifest["schema"] != 2
        || manifest["runtime_gates"]["passed"] != true
        || manifest["runtime_gates"]["frozen"] != true
        || manifest["runtime_gates"]["device"] != "gpu"
        || manifest["binary_sha256"]["exo.exe"]
            .as_str()
            .is_none_or(|hash| !hash.eq_ignore_ascii_case(expected))
        || manifest["file_sha256"]["exo.exe"]
            .as_str()
            .is_none_or(|hash| !hash.eq_ignore_ascii_case(expected))
    {
        return Err(
            "The runtime manifest does not match this helper's validated CUDA build.".into(),
        );
    }
    let mut file = std::fs::File::open(&executable).map_err(|e| e.to_string())?;
    let mut digest = Sha256::new();
    let mut buffer = [0u8; 65536];
    loop {
        let length = file.read(&mut buffer).map_err(|e| e.to_string())?;
        if length == 0 {
            break;
        }
        digest.update(&buffer[..length]);
    }
    if !format!("{:x}", digest.finalize()).eq_ignore_ascii_case(expected) {
        return Err("EXO executable hash changed; reinstall a verified Windows bundle.".into());
    }
    Ok(executable)
}
pub fn elevate_helper(helper: &Path) -> Result<(), String> {
    use windows_sys::Win32::{
        Foundation::{CloseHandle, WAIT_OBJECT_0},
        System::Threading::{GetExitCodeProcess, WaitForSingleObject, INFINITE},
        UI::{
            Shell::{ShellExecuteExW, SEE_MASK_NOCLOSEPROCESS, SHELLEXECUTEINFOW},
            WindowsAndMessaging::SW_HIDE,
        },
    };
    let wide = |value: &OsStr| value.encode_wide().chain(Some(0)).collect::<Vec<_>>();
    let file = wide(helper.as_os_str());
    let verb = wide(OsStr::new("runas"));
    let arguments = wide(OsStr::new("--apply"));
    let cwd = wide(helper.parent().ok_or("Invalid helper path")?.as_os_str());
    unsafe {
        let mut info: SHELLEXECUTEINFOW = std::mem::zeroed();
        info.cbSize = std::mem::size_of::<SHELLEXECUTEINFOW>() as u32;
        info.fMask = SEE_MASK_NOCLOSEPROCESS;
        info.lpVerb = verb.as_ptr();
        info.lpFile = file.as_ptr();
        info.lpParameters = arguments.as_ptr();
        info.lpDirectory = cwd.as_ptr();
        info.nShow = SW_HIDE;
        if ShellExecuteExW(&mut info) == 0 {
            let error = std::io::Error::last_os_error();
            return Err(if error.raw_os_error() == Some(1223) {
                "Firewall setup was cancelled in the Windows permission prompt.".into()
            } else {
                format!("Open firewall helper: {error}")
            });
        }
        if info.hProcess.is_null() {
            return Err("Windows did not return the helper process.".into());
        }
        let waited = WaitForSingleObject(info.hProcess, INFINITE);
        let mut exit_code = 1;
        let queried = GetExitCodeProcess(info.hProcess, &mut exit_code);
        CloseHandle(info.hProcess);
        if waited != WAIT_OBJECT_0 || queried == 0 || exit_code != 0 {
            return Err(
                "The firewall helper could not finish. Check its Windows error message and retry."
                    .into(),
            );
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn only_installed_helper_layout_resolves_the_runtime() {
        assert_eq!(
            helper_runtime_path(Path::new("C:\\App\\firewall\\exo-firewall-helper.exe")).unwrap(),
            PathBuf::from("C:\\App\\runtime")
        );
        for path in [
            "C:\\App\\exo-firewall-helper.exe",
            "C:\\App\\firewall\\other.exe",
        ] {
            assert!(helper_runtime_path(Path::new(path)).is_err());
        }
    }
    #[test]
    fn fixed_firewall_rules_always_scope_program_ports_profiles_and_subnet() {
        let program = Path::new("C:\\Türkçe & app\\runtime\\exo.exe");
        for rule in &RULES {
            let arguments = add_arguments(rule, program);
            assert!(arguments.contains(&"remoteip=localsubnet".into()));
            assert!(arguments.contains(&"profile=private,domain".into()));
            assert!(arguments.contains(&"program=C:\\Türkçe & app\\runtime\\exo.exe".into()));
            assert!(arguments.contains(&format!("localport={}", rule.ports).into()));
            assert_eq!(
                delete_arguments(rule).last(),
                Some(&format!("name={}", rule.name).into())
            );
        }
        assert_eq!(
            RULES
                .iter()
                .map(|rule| (rule.protocol, rule.ports))
                .collect::<Vec<_>>(),
            [
                ("UDP", "52413"),
                ("TCP", "52414,52415"),
                ("TCP", "49152-65535")
            ]
        );
        assert!(add_arguments(
            &RULES[0],
            Path::new("\\\\?\\C:\\Türkçe & app\\runtime\\exo.exe")
        )
        .contains(&"program=C:\\Türkçe & app\\runtime\\exo.exe".into()));
        assert!(add_arguments(
            &RULES[0],
            Path::new("\\\\?\\UNC\\server\\share\\runtime\\exo.exe")
        )
        .contains(&"program=\\\\server\\share\\runtime\\exo.exe".into()));
    }
    #[test]
    fn missing_pinned_hash_fails_before_touching_any_runtime_or_firewall() {
        assert!(verify_runtime(Path::new("C:\\does-not-exist"), None)
            .unwrap_err()
            .contains("validated firewall runtime hash"));
    }
    #[test]
    fn runtime_validation_rejects_changed_executable_and_failed_manifest_gates() {
        let allowed = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/firewall-tests");
        let root = allowed.join(uuid::Uuid::new_v4().simple().to_string());
        let runtime = root.join("runtime");
        std::fs::create_dir_all(&runtime).unwrap();
        let executable = runtime.join("exo.exe");
        std::fs::write(&executable, b"known frozen fixture").unwrap();
        let expected = format!("{:x}", Sha256::digest(b"known frozen fixture"));
        let manifest = runtime.join("runtime-manifest.json");
        let mut value = serde_json::json!({"schema":2,"runtime_gates":{"passed":true,"frozen":true,"device":"gpu"},"binary_sha256":{"exo.exe":expected},"file_sha256":{"exo.exe":expected}});
        std::fs::write(&manifest, serde_json::to_vec(&value).unwrap()).unwrap();
        assert_eq!(
            verify_runtime(&runtime, Some(&expected)).unwrap(),
            executable.canonicalize().unwrap()
        );
        std::fs::write(&executable, b"changed frozen fixture").unwrap();
        assert!(verify_runtime(&runtime, Some(&expected))
            .unwrap_err()
            .contains("hash changed"));
        value["runtime_gates"]["passed"] = false.into();
        std::fs::write(&manifest, serde_json::to_vec(&value).unwrap()).unwrap();
        assert!(verify_runtime(&runtime, Some(&expected))
            .unwrap_err()
            .contains("manifest"));
        assert!(root
            .canonicalize()
            .unwrap()
            .starts_with(allowed.canonicalize().unwrap()));
        std::fs::remove_dir_all(root).unwrap();
    }
}
