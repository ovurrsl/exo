#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
#[cfg(not(windows))]
compile_error!("EXO Windows desktop is a Windows-only workspace.");
mod commands;
mod desktop;
#[allow(dead_code)]
mod firewall;
mod native;
mod settings;
use std::sync::Arc;
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager,
};

fn popover_position(
    icon_x: i32,
    icon_y: i32,
    width: i32,
    height: i32,
    work: (i32, i32, i32, i32),
) -> (i32, i32) {
    let (left, top, right, bottom) = work;
    let x = (icon_x - width / 2).clamp(left, (right - width).max(left));
    let y = (icon_y - height - 8).clamp(top, (bottom - height).max(top));
    (x, y)
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            commands::snapshot,
            commands::cluster_state,
            commands::get_settings,
            commands::save_settings,
            commands::start_backend,
            commands::stop_backend,
            commands::restart_backend,
            commands::open_dashboard,
            commands::open_location,
            commands::copy_api_url,
            commands::pick_directory,
            commands::show_settings,
            commands::hide_window,
            commands::resize_panel,
            commands::check_update,
            commands::install_update,
            commands::export_diagnostics,
            commands::open_issue,
            commands::network_diagnostics,
            commands::configure_firewall,
            commands::reset_onboarding,
            commands::delete_instance,
            commands::cancel_download,
            commands::retry_download,
            commands::uninstall_app,
            commands::quit_app
        ])
        .setup(|app| {
            let desktop = Arc::new(
                desktop::Desktop::new(app.handle().clone()).map_err(std::io::Error::other)?,
            );
            app.manage(desktop.clone());
            let dashboard =
                MenuItem::with_id(app, "dashboard", "Web Dashboard", true, None::<&str>)?;
            let settings_item =
                MenuItem::with_id(app, "settings", "Settings…", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit EXO", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&dashboard, &settings_item, &quit])?;
            TrayIconBuilder::with_id("exo")
                .icon(
                    app.default_window_icon()
                        .ok_or("Missing tray icon")?
                        .clone(),
                )
                .tooltip("EXO Windows")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        rect,
                        ..
                    } = event
                    {
                        if let Some(window) = tray.app_handle().get_webview_window("main") {
                            if window.is_visible().unwrap_or(false) {
                                let _ = window.hide();
                            } else {
                                let physical = rect
                                    .position
                                    .to_physical::<i32>(window.scale_factor().unwrap_or(1.0));
                                if let Ok(Some(monitor)) =
                                    window.monitor_from_point(physical.x as f64, physical.y as f64)
                                {
                                    let work = monitor.work_area();
                                    let scale = monitor.scale_factor();
                                    let width =
                                        ((340.0 * scale) as i32).min(work.size.width as i32);
                                    let logical_height = window
                                        .inner_size()
                                        .map(|size| {
                                            f64::from(size.height)
                                                / window.scale_factor().unwrap_or(1.0)
                                        })
                                        .unwrap_or(650.0)
                                        .clamp(220.0, 650.0);
                                    let height = ((logical_height * scale).round() as i32)
                                        .min(work.size.height as i32);
                                    let (x, y) = popover_position(
                                        physical.x,
                                        physical.y,
                                        width,
                                        height,
                                        (
                                            work.position.x,
                                            work.position.y,
                                            work.position.x + work.size.width as i32,
                                            work.position.y + work.size.height as i32,
                                        ),
                                    );
                                    let _ = window.set_position(tauri::PhysicalPosition::new(x, y));
                                    let _ = window.set_size(tauri::PhysicalSize::new(
                                        width as u32,
                                        height as u32,
                                    ));
                                }
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                    }
                })
                .on_menu_event(|app, event| {
                    let desktop = app.state::<Arc<desktop::Desktop>>().inner().clone();
                    let app = app.clone();
                    match event.id.as_ref() {
                        "settings" => {
                            tauri::async_runtime::spawn(async move {
                                let _ = commands::settings_window(app).await;
                            });
                        }
                        "dashboard" => {
                            tauri::async_runtime::spawn(async move {
                                let _ = commands::dashboard_url(&desktop, "").await;
                            });
                        }
                        "quit" => {
                            tauri::async_runtime::spawn(async move {
                                let _ = desktop.stop().await;
                                app.exit(0);
                            });
                        }
                        _ => {}
                    }
                })
                .build(app)?;
            desktop.clone().launch_tasks();
            if !std::env::args().any(|argument| argument == "--background") {
                if let Some(window) = app.get_webview_window("main") {
                    window.show()?;
                }
            }
            Ok(())
        })
        .on_window_event(|window, event| match event {
            tauri::WindowEvent::CloseRequested { api, .. } => {
                api.prevent_close();
                let _ = window.hide();
            }
            tauri::WindowEvent::Focused(false) if window.label() == "main" => {
                let desktop = window.app_handle().state::<Arc<desktop::Desktop>>();
                if !desktop
                    .dialog_active
                    .load(std::sync::atomic::Ordering::SeqCst)
                {
                    let _ = window.hide();
                }
            }
            _ => {}
        })
        .build(tauri::generate_context!())
        .expect("Unable to initialize EXO desktop");
    app.run(|app, event| {
        if let tauri::RunEvent::ExitRequested { api, .. } = event {
            let desktop = app.state::<Arc<desktop::Desktop>>().inner().clone();
            if desktop.snapshot().owned {
                api.prevent_exit();
                let app = app.clone();
                tauri::async_runtime::spawn(async move {
                    let _ = desktop.stop().await;
                    app.exit(0);
                });
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::popover_position;
    #[test]
    fn tray_popover_fits_negative_monitor_coordinates_and_scaled_edges() {
        assert_eq!(
            popover_position(-10, 1040, 540, 975, (-1920, 0, 0, 1040)),
            (-540, 57)
        );
        assert_eq!(
            popover_position(1900, 40, 360, 650, (0, 40, 1920, 1080)),
            (1560, 40)
        );
    }
}
