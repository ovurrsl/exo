//! Owned Windows process tree. The child is assigned while suspended, avoiding
//! the spawn-before-job race that can leave runner children outside the job.
use std::{
    ffi::OsStr,
    fs::OpenOptions,
    mem::{size_of, zeroed},
    os::windows::{ffi::OsStrExt, io::AsRawHandle},
    path::Path,
    ptr::{null, null_mut},
    time::Duration,
};
use windows_sys::Win32::{
    Foundation::{
        CloseHandle, LocalFree, SetHandleInformation, HANDLE, HANDLE_FLAG_INHERIT, STILL_ACTIVE,
        WAIT_OBJECT_0,
    },
    Security::{
        Authorization::{
            ConvertSidToStringSidW, ConvertStringSecurityDescriptorToSecurityDescriptorW,
        },
        GetTokenInformation, TokenUser, SECURITY_ATTRIBUTES, TOKEN_QUERY, TOKEN_USER,
    },
    System::{
        JobObjects::{
            AssignProcessToJobObject, CreateJobObjectW, JobObjectBasicAccountingInformation,
            JobObjectExtendedLimitInformation, QueryInformationJobObject, SetInformationJobObject,
            TerminateJobObject, JOBOBJECT_BASIC_ACCOUNTING_INFORMATION,
            JOBOBJECT_EXTENDED_LIMIT_INFORMATION, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        },
        Threading::{
            CreateEventW, CreateProcessW, GetCurrentProcess, GetExitCodeProcess, OpenProcessToken,
            ResumeThread, SetEvent, TerminateProcess, WaitForSingleObject, CREATE_NO_WINDOW,
            CREATE_SUSPENDED, CREATE_UNICODE_ENVIRONMENT, PROCESS_INFORMATION,
            STARTF_USESTDHANDLES, STARTUPINFOW,
        },
    },
};
struct Handle(HANDLE);
// Windows kernel handles can be waited, queried and closed across threads.
unsafe impl Send for Handle {}
unsafe impl Sync for Handle {}
impl Handle {
    fn new(value: HANDLE) -> Result<Self, String> {
        if value.is_null() {
            Err(std::io::Error::last_os_error().to_string())
        } else {
            Ok(Self(value))
        }
    }
}
impl Drop for Handle {
    fn drop(&mut self) {
        unsafe {
            CloseHandle(self.0);
        }
    }
}
fn wide(value: impl AsRef<OsStr>) -> Vec<u16> {
    value.as_ref().encode_wide().chain(Some(0)).collect()
}
fn error(context: &str) -> String {
    format!("{context}: {}", std::io::Error::last_os_error())
}

pub fn quote_argument(value: &str) -> String {
    let mut result = String::from("\"");
    let mut slashes = 0;
    for character in value.chars() {
        if character == '\\' {
            slashes += 1;
            continue;
        }
        if character == '"' {
            result.push_str(&"\\".repeat(slashes * 2 + 1));
            result.push('"');
        } else {
            result.push_str(&"\\".repeat(slashes));
            result.push(character);
        }
        slashes = 0;
    }
    result.push_str(&"\\".repeat(slashes * 2));
    result.push('"');
    result
}
unsafe fn current_user_security() -> Result<(*mut std::ffi::c_void, SECURITY_ATTRIBUTES), String> {
    let mut token = null_mut();
    if OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token) == 0 {
        return Err(error("Open user token"));
    }
    let token = Handle::new(token)?;
    let mut required = 0;
    GetTokenInformation(token.0, TokenUser, null_mut(), 0, &mut required);
    // TOKEN_USER contains pointers and therefore requires pointer alignment.
    let mut buffer = vec![0usize; (required as usize).div_ceil(size_of::<usize>())];
    if GetTokenInformation(
        token.0,
        TokenUser,
        buffer.as_mut_ptr().cast(),
        required,
        &mut required,
    ) == 0
    {
        return Err(error("Read user token"));
    }
    let user = &*buffer.as_ptr().cast::<TOKEN_USER>();
    let mut sid = null_mut();
    if ConvertSidToStringSidW(user.User.Sid, &mut sid) == 0 {
        return Err(error("Read user SID"));
    }
    let mut length = 0;
    while *sid.add(length) != 0 {
        length += 1;
    }
    let sid_string = String::from_utf16_lossy(std::slice::from_raw_parts(sid, length));
    LocalFree(sid.cast());
    let descriptor_text = wide(format!("D:P(A;;GA;;;SY)(A;;GA;;;{sid_string})"));
    let mut descriptor = null_mut();
    if ConvertStringSecurityDescriptorToSecurityDescriptorW(
        descriptor_text.as_ptr(),
        1,
        &mut descriptor,
        null_mut(),
    ) == 0
    {
        return Err(error("Build shutdown event ACL"));
    }
    let attributes = SECURITY_ATTRIBUTES {
        nLength: size_of::<SECURITY_ATTRIBUTES>() as u32,
        lpSecurityDescriptor: descriptor,
        bInheritHandle: 0,
    };
    Ok((descriptor, attributes))
}
pub struct EngineProcess {
    process: Handle,
    job: Handle,
    shutdown: Handle,
}
#[derive(Clone, Copy)]
pub struct RuntimePorts {
    pub api: u16,
    pub zenoh: u16,
    pub discovery: u16,
}
impl Default for RuntimePorts {
    fn default() -> Self {
        Self {
            api: 52415,
            zenoh: 52414,
            discovery: 52413,
        }
    }
}
#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct StopOutcome {
    pub graceful: bool,
    pub exit_code: Option<u32>,
}
impl EngineProcess {
    pub fn spawn(
        executable: &Path,
        data: &Path,
        log: &Path,
        environment: &std::collections::BTreeMap<String, String>,
        event_name: String,
        namespace: &str,
        ports: RuntimePorts,
    ) -> Result<Self, String> {
        unsafe {
            let job = Handle::new(CreateJobObjectW(null(), null()))?;
            let mut limits: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = zeroed();
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            if SetInformationJobObject(
                job.0,
                JobObjectExtendedLimitInformation,
                (&limits as *const JOBOBJECT_EXTENDED_LIMIT_INFORMATION).cast(),
                size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            ) == 0
            {
                return Err(error("Set job limits"));
            }
            let (descriptor, attributes) = current_user_security()?;
            let event_wide = wide(&event_name);
            let event = CreateEventW(&attributes, 1, 0, event_wide.as_ptr());
            let event_error = if event.is_null() {
                Some(error("Create shutdown event"))
            } else {
                None
            };
            LocalFree(descriptor);
            if let Some(error) = event_error {
                return Err(error);
            }
            let shutdown = Handle::new(event)?;
            std::fs::create_dir_all(data).map_err(|e| e.to_string())?;
            std::fs::create_dir_all(log.parent().ok_or("Invalid desktop log path")?)
                .map_err(|e| e.to_string())?;
            let output = OpenOptions::new()
                .create(true)
                .append(true)
                .open(log)
                .map_err(|e| e.to_string())?;
            let input = OpenOptions::new()
                .read(true)
                .open("NUL")
                .map_err(|e| e.to_string())?;
            if SetHandleInformation(
                output.as_raw_handle().cast(),
                HANDLE_FLAG_INHERIT,
                HANDLE_FLAG_INHERIT,
            ) == 0
                || SetHandleInformation(
                    input.as_raw_handle().cast(),
                    HANDLE_FLAG_INHERIT,
                    HANDLE_FLAG_INHERIT,
                ) == 0
            {
                return Err(error("Configure hidden process logs"));
            }
            let mut startup: STARTUPINFOW = zeroed();
            startup.cb = size_of::<STARTUPINFOW>() as u32;
            startup.dwFlags = STARTF_USESTDHANDLES;
            startup.hStdOutput = output.as_raw_handle().cast();
            startup.hStdError = output.as_raw_handle().cast();
            startup.hStdInput = input.as_raw_handle().cast();
            let mut process: PROCESS_INFORMATION = zeroed();
            let executable_wide = wide(executable);
            let cwd = wide(data);
            let mut command = wide(format!(
                "{} --namespace {} --api-port {} --zenoh-port {} --discovery-port {}",
                quote_argument(&executable.display().to_string()),
                quote_argument(namespace),
                ports.api,
                ports.zenoh,
                ports.discovery
            ));
            let mut block: Vec<u16> = environment
                .iter()
                .flat_map(|(key, value)| wide(format!("{key}={value}")))
                .collect();
            block.push(0);
            if CreateProcessW(
                executable_wide.as_ptr(),
                command.as_mut_ptr(),
                null(),
                null(),
                1,
                CREATE_NO_WINDOW | CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT,
                block.as_ptr().cast(),
                cwd.as_ptr(),
                &startup,
                &mut process,
            ) == 0
            {
                return Err(error("Start EXO runtime"));
            }
            let owned_process = Handle::new(process.hProcess)?;
            let thread = Handle::new(process.hThread)?;
            if AssignProcessToJobObject(job.0, owned_process.0) == 0 {
                TerminateProcess(owned_process.0, 1);
                return Err(error("Assign EXO process tree to job"));
            }
            if ResumeThread(thread.0) == u32::MAX {
                TerminateJobObject(job.0, 1);
                return Err(error("Resume EXO runtime"));
            }
            Ok(Self {
                process: owned_process,
                job,
                shutdown,
            })
        }
    }
    pub fn exit_code(&self) -> Result<Option<u32>, String> {
        unsafe {
            let mut code = 0;
            if GetExitCodeProcess(self.process.0, &mut code) == 0 {
                return Err(error("Read backend status"));
            }
            Ok((code != STILL_ACTIVE as u32).then_some(code))
        }
    }
    fn active_children(&self) -> Result<u32, String> {
        unsafe {
            let mut info: JOBOBJECT_BASIC_ACCOUNTING_INFORMATION = zeroed();
            if QueryInformationJobObject(
                self.job.0,
                JobObjectBasicAccountingInformation,
                (&mut info as *mut JOBOBJECT_BASIC_ACCOUNTING_INFORMATION).cast(),
                size_of::<JOBOBJECT_BASIC_ACCOUNTING_INFORMATION>() as u32,
                null_mut(),
            ) == 0
            {
                return Err(error("Read process tree"));
            }
            Ok(info.ActiveProcesses)
        }
    }
    pub async fn stop(&self) -> Result<StopOutcome, String> {
        if unsafe { SetEvent(self.shutdown.0) } == 0 {
            return Err(error("Signal EXO shutdown"));
        }
        let deadline = tokio::time::Instant::now() + Duration::from_secs(10);
        while self.active_children()? > 0 && tokio::time::Instant::now() < deadline {
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
        let graceful = self.active_children()? == 0;
        if !graceful && unsafe { TerminateJobObject(self.job.0, 1) } == 0 {
            return Err(error("Terminate EXO process tree"));
        }
        let deadline = tokio::time::Instant::now() + Duration::from_secs(3);
        while (self.active_children()? > 0
            || unsafe { WaitForSingleObject(self.process.0, 0) } != WAIT_OBJECT_0)
            && tokio::time::Instant::now() < deadline
        {
            tokio::time::sleep(Duration::from_millis(50)).await;
        }
        if self.active_children()? > 0 {
            return Err("EXO process tree did not exit.".into());
        }
        Ok(StopOutcome {
            graceful,
            exit_code: self.exit_code()?,
        })
    }
}
#[cfg(test)]
mod tests {
    use super::quote_argument;
    #[test]
    fn quoted_windows_arguments_preserve_unicode_spaces_and_trailing_slashes() {
        assert_eq!(quote_argument("C:\\Türkçe yol\\"), "\"C:\\Türkçe yol\\\\\"");
        assert_eq!(quote_argument("a\"b"), "\"a\\\"b\"");
        assert_eq!(quote_argument("a & b"), "\"a & b\"");
    }
}
