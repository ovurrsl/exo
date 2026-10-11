#![windows_subsystem = "windows"]
#[allow(dead_code)]
mod firewall;
use std::os::windows::process::CommandExt;

fn apply() -> Result<(), String> {
    if std::env::args_os().skip(1).collect::<Vec<_>>() != [std::ffi::OsString::from("--apply")] {
        return Err("This helper accepts only the EXO desktop's fixed --apply action.".into());
    }
    let helper = std::env::current_exe()
        .map_err(|e| e.to_string())?
        .canonicalize()
        .map_err(|e| e.to_string())?;
    let runtime = firewall::helper_runtime_path(&helper)?;
    let program = firewall::verify_runtime(&runtime, firewall::EXPECTED_RUNTIME_SHA256)?;
    let system = firewall::system_directory()?;
    let netsh = system.join("netsh.exe");
    if !netsh.is_file() {
        return Err("The Windows system firewall tool is missing.".into());
    }
    for rule in &firewall::RULES {
        let mut delete = std::process::Command::new(&netsh);
        delete
            .args(firewall::delete_arguments(rule))
            .current_dir(&system)
            .env("PATH", &system)
            .creation_flags(windows_sys::Win32::System::Threading::CREATE_NO_WINDOW);
        let removed = delete
            .output()
            .map_err(|e| format!("Remove {}: {e}", rule.name))?;
        if !matches!(removed.status.code(), Some(0 | 1)) {
            return Err(format!(
                "Could not remove the existing EXO rule {}.",
                rule.name
            ));
        }
        let result = std::process::Command::new(&netsh)
            .args(firewall::add_arguments(rule, &program))
            .current_dir(&system)
            .env("PATH", &system)
            .creation_flags(windows_sys::Win32::System::Threading::CREATE_NO_WINDOW)
            .output()
            .map_err(|e| format!("Add {}: {e}", rule.name))?;
        if !result.status.success() {
            return Err(format!(
                "Could not add {}: {} {}",
                rule.name,
                String::from_utf8_lossy(&result.stdout),
                String::from_utf8_lossy(&result.stderr)
            ));
        }
    }
    Ok(())
}
fn main() {
    if let Err(error) = apply() {
        use std::os::windows::ffi::OsStrExt;
        let text: Vec<u16> = std::ffi::OsStr::new(&error)
            .encode_wide()
            .chain(Some(0))
            .collect();
        let title: Vec<u16> = std::ffi::OsStr::new("EXO firewall setup")
            .encode_wide()
            .chain(Some(0))
            .collect();
        unsafe {
            windows_sys::Win32::UI::WindowsAndMessaging::MessageBoxW(
                std::ptr::null_mut(),
                text.as_ptr(),
                title.as_ptr(),
                windows_sys::Win32::UI::WindowsAndMessaging::MB_OK
                    | windows_sys::Win32::UI::WindowsAndMessaging::MB_ICONERROR,
            );
        }
        std::process::exit(1);
    }
}
