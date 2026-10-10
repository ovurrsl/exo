#![cfg(feature = "process-test-helper")]
#[path = "../src/native.rs"]
mod native;
use std::{
    collections::BTreeMap,
    path::Path,
    time::{Duration, Instant},
};
fn environment(event: &str) -> BTreeMap<String, String> {
    let mut result: BTreeMap<String, String> = std::env::vars().collect();
    result.insert("EXO_WINDOWS_SHUTDOWN_EVENT".into(), event.into());
    result
}
async fn cleanup(data: std::path::PathBuf) {
    let temporary = std::env::temp_dir();
    assert!(data.starts_with(&temporary));
    assert!(data
        .file_name()
        .unwrap()
        .to_string_lossy()
        .starts_with("exo-desktop-test-"));
    // Windows may release a terminated process's inherited log handle after
    // job accounting reaches zero. Retry only this verified test directory.
    for attempt in 0..20 {
        match std::fs::remove_dir_all(&data) {
            Ok(()) => return,
            Err(error) if error.raw_os_error() == Some(32) && attempt < 19 => {
                tokio::time::sleep(Duration::from_millis(50)).await
            }
            Err(error) => panic!("Test directory cleanup: {error}"),
        }
    }
}
#[tokio::test]
async fn hidden_process_event_stops_the_entire_owned_tree() {
    let data = std::env::temp_dir().join(format!(
        "exo-desktop-test-{}",
        uuid::Uuid::new_v4().simple()
    ));
    let event = format!("Local\\exo-shutdown-{}", uuid::Uuid::new_v4().simple());
    let engine = native::EngineProcess::spawn(
        Path::new(env!("CARGO_BIN_EXE_exo-process-test-helper")),
        &data,
        &data.join("test.log"),
        &environment(&event),
        event,
        "test namespace",
        native::RuntimePorts::default(),
    )
    .unwrap();
    tokio::time::sleep(Duration::from_millis(250)).await;
    assert!(engine.exit_code().unwrap().is_none());
    let start = Instant::now();
    engine.stop().await.unwrap();
    assert!(start.elapsed() < Duration::from_secs(5));
    assert_eq!(engine.exit_code().unwrap(), Some(0));
    drop(engine);
    cleanup(data).await;
}
#[tokio::test]
async fn unresponsive_process_and_grandchild_are_killed_after_grace_period() {
    let data = std::env::temp_dir().join(format!(
        "exo-desktop-test-{}",
        uuid::Uuid::new_v4().simple()
    ));
    let event = format!("Local\\exo-shutdown-{}", uuid::Uuid::new_v4().simple());
    let mut environment = environment(&event);
    environment.insert("EXO_TEST_IGNORE_SHUTDOWN".into(), "1".into());
    let engine = native::EngineProcess::spawn(
        Path::new(env!("CARGO_BIN_EXE_exo-process-test-helper")),
        &data,
        &data.join("test.log"),
        &environment,
        event,
        "test",
        native::RuntimePorts::default(),
    )
    .unwrap();
    let start = Instant::now();
    engine.stop().await.unwrap();
    assert!(start.elapsed() >= Duration::from_secs(10));
    assert!(start.elapsed() < Duration::from_secs(14));
    assert_eq!(engine.exit_code().unwrap(), Some(1));
    drop(engine);
    cleanup(data).await;
}
