import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

export type DesktopHealth = { status: "OK"; backend: string; database: string; agent_host: string; request_count: number };
export type ProviderId = "openai" | "anthropic" | "deepseek" | "google" | "openrouter" | "moonshot" | "qwen" | "minimax" | "custom_openai_compatible";
export type ProviderDefinition = { id: ProviderId; label: string; requires_base_url: boolean };
export type ProviderProfile = { provider: ProviderId; label: string; model_id: string; base_url: string | null; configured: boolean; masked_key: string | null; tool_calling_verified: boolean; last_connection_test: string | null; is_default: boolean };
export type ProviderStatus = { providers: ProviderDefinition[]; profiles: ProviderProfile[]; default_provider: ProviderId | null };
export type ProviderDraft = { provider: ProviderId; model_id: string; base_url?: string; api_key?: string; set_default?: boolean };
export type ConnectionTestResult = { status: "SUCCESS" | "ERROR"; kind: "success" | "unauthorized" | "not_found" | "rate_limited" | "timeout" | "network" | "malformed" | "unknown"; tool_calling_verified: boolean; message: string };
export type ColumnProfile = { dtype: string; missing_count: number; missing_rate: number; unique_count: number; top_values: Record<string, number> };
export type DatasetPreview = { path: string; sha256: string; format: string; size_bytes: number; schema: { row_count: number; column_count: number; columns: Record<string, ColumnProfile>; sample_limit_for_llm: number }; sample: Record<string, string | null>[] };
export type DatasetSession = { session_id: string; schema: DatasetPreview["schema"]; candidates: Record<string, { column: string; confidence: number }[]>; domain_spec: Record<string, unknown>; status: string };
export type ResearchSession = { session_id: string; status: string; research_plan_locked: number | boolean; final_evaluation_revealed: number | boolean; hypotheses: { hypothesis_id: string; content: string; status: string; version: number }[]; plans: { plan_id: string; recipe_json: string }[]; runs: { run_id: string; policy: string; budget: number; status: string; round_end: number }[] };
export type ScientistEvent = { type: "agent_started" | "agent_completed" | "agent_error" | "agent_tool_execution" | "tool_start" | "tool_end" | "experiment_progress"; session_id?: string; tool?: string; status?: string; run_id?: string; round?: number; total_rounds?: number; message?: string };
export type HistorySession = { session_id:string; status:string; dataset:string; dataset_path:string | null; domain:string; model:string; hypothesis_count:number; run_count:number; updated_at:string; created_at:string; final_evaluation_revealed:boolean };
export type ResumedDatasetSession = DatasetSession & { snapshot: { round_index:number; state: { remaining_budget?:number; visible_label_count?:number; candidate_remaining?:number } } | null; research_plan_locked:boolean; final_evaluation_revealed:boolean };
export type ReportDocument = { session_id:string; path:string; content:string };

export const DesktopBridge = {
  call<T>(action: string, payload: Record<string, unknown> = {}) { return invoke<T>("desktop_bridge", { action, payload }); },
  healthCheck() { return this.call<DesktopHealth>("health_check"); },
  inspectDataset(path: string) { return this.call<DatasetPreview>("inspect_dataset", { path }); },
  loadDataset(path: string, description: string) { return this.call<DatasetSession>("load_dataset", { path, description }); },
  listSessions() { return this.call<{ sessions: HistorySession[] }>("list_sessions"); },
  resumeSession(session_id: string) { return this.call<ResumedDatasetSession>("resume_session", { session_id }); },
  deleteSession(session_id: string) { return this.call<{ status: "DELETED"; session_id: string }>("delete_session", { session_id }); },
  readReport(session_id: string) { return this.call<ReportDocument>("read_report", { session_id }); },
  exportReport(session_id: string, destination: string) { return this.call<{ status: "EXPORTED" | "EXISTS"; path:string }>("export_report", { session_id, destination }); },
  openReportLocation(session_id: string) { return this.call<{ status: "OPENED"; session_id:string }>("report_open_location", { session_id }); },  getSession(session_id: string) { return this.call<ResearchSession>("get_session", { session_id }); },
  chartData(session_id: string) { return this.call<unknown>("chart_data", { session_id }); },
  startScientist(session_id: string, question: string) { return this.call<{ status: "COMPLETED"; session_id: string; events: { type: string; tool?: string }[] }>("scientist_start", { session_id, question }); },
  subscribeScientistEvents(handler: (event: ScientistEvent) => void) { return listen<ScientistEvent>("scientist-event", (event) => handler(event.payload)); },
  providerStatus() { return this.call<ProviderStatus>("provider_status"); },
  saveProvider(draft: ProviderDraft) { return this.call<{ status: "SAVED"; provider: ProviderId; configured: boolean; masked_key: string }>("provider_save", draft); },
  deleteProvider(provider: ProviderId) { return this.call<{ status: "DELETED"; provider: ProviderId }>("provider_delete", { provider }); },
  setDefaultProvider(provider: ProviderId) { return this.call<{ status: "DEFAULT_UPDATED"; provider: ProviderId }>("provider_set_default", { provider }); },
  validateProvider(provider: ProviderId) { return this.call<{ status: "READY_FOR_CONNECTION_TEST"; message: string }>("provider_validate", { provider }); },
  testProviderConnection(provider: ProviderId) { return this.call<ConnectionTestResult>("provider_test_connection", { provider }); },
};
