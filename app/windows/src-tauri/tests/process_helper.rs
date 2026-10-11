//! Test-only child: it never opens a GUI, modifies settings, or runs inference.
use std::{
    ffi::OsStr,
    os::windows::{ffi::OsStrExt, process::CommandExt},
    process::Command,
};
use windows_sys::Win32::{
    Foundation::{CloseHandle, WAIT_OBJECT_0},
    System::Threading::{OpenEventW, WaitForSingleObject, CREATE_NO_WINDOW},
};
fn main() {
    let environment = std::env::var("EXO_WINDOWS_SHUTDOWN_EVENT").expect("Test event");
    let event: Vec<u16> = OsStr::new(&environment)
        .encode_wide()
        .chain(Some(0))
        .collect();
    let handle = unsafe { OpenEventW(0x0010_0000, 0, event.as_ptr()) };
    assert!(!handle.is_null());
    let mut grandchild = Command::new("ping.exe")
        .args(["-n", "60", "127.0.0.1"])
        .creation_flags(CREATE_NO_WINDOW)
        .spawn()
        .expect("Test grandchild");
    if std::env::var_os("EXO_TEST_IGNORE_SHUTDOWN").is_some() {
        std::thread::sleep(std::time::Duration::from_secs(60));
    } else {
        assert_eq!(
            unsafe { WaitForSingleObject(handle, 30_000) },
            WAIT_OBJECT_0
        );
    }
    let _ = grandchild.kill();
    let _ = grandchild.wait();
    unsafe {
        CloseHandle(handle);
    }
}
