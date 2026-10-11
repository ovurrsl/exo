import { invoke } from "@tauri-apps/api/core";
export type DesktopCommand =
  | "snapshot"
  | "cluster_state"
  | "get_settings"
  | "save_settings"
  | "start_backend"
  | "stop_backend"
  | "restart_backend"
  | "open_dashboard"
  | "open_location"
  | "copy_api_url"
  | "pick_directory"
  | "show_settings"
  | "hide_window"
  | "resize_panel"
  | "check_update"
  | "install_update"
  | "export_diagnostics"
  | "open_issue"
  | "network_diagnostics"
  | "configure_firewall"
  | "reset_onboarding"
  | "delete_instance"
  | "cancel_download"
  | "retry_download"
  | "uninstall_app"
  | "quit_app";
declare global {
  interface Window {
    __EXO_TEST_BRIDGE__?: (
      command: DesktopCommand,
      args: Record<string, unknown>,
    ) => Promise<unknown>;
  }
}
export function call<T>(
  command: DesktopCommand,
  args: Record<string, unknown> = {},
): Promise<T> {
  // A test-only bridge is enabled exclusively by Vite's development server.
  if (import.meta.env.DEV && window.__EXO_TEST_BRIDGE__)
    return window.__EXO_TEST_BRIDGE__(command, args) as Promise<T>;
  return invoke<T>(command, args);
}
