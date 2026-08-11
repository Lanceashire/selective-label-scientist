import { invoke } from "@tauri-apps/api/core";

export type DesktopHealth = { status: "OK"; backend: string; database: string; agent_host: string; request_count: number };
export const DesktopBridge = {
  call<T>(action: string, payload: Record<string, unknown> = {}) { return invoke<T>("desktop_bridge", { action, payload }); },
  healthCheck() { return this.call<DesktopHealth>("health_check"); }
};
