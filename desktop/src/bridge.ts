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
export type DatasetPreview = { path: string; sha256: string; format: string; size_bytes: number; dataset_handle_id?: string; schema: { row_count: number; column_count: number; columns: Record<string, ColumnProfile>; sample_limit_for_llm: number }; sample: Record<string, string | null>[] };
export type PrecheckProgress = { type: "precheck_progress"; request_id: string; stage: "读取文件" | "解析 Schema" | "统计字段" | "生成样本" | "完成"; percent: number };
export type DatasetSession = { session_id: string; schema: DatasetPreview["schema"]; candidates: Record<string, { column: string; confidence: number }[]>; domain_spec: Record<string, unknown>; status: string };
export type ResearchSession = { session_id: string; status: string; research_plan_locked: number | boolean; final_evaluation_revealed: number | boolean; hypotheses: { hypothesis_id: string; content: string; status: string; version: number }[]; plans: { plan_id: string; recipe_json: string }[]; runs: { run_id: string; policy: string; budget: number; status: string; round_end: number }[] };
export type ScientistEvent = { type: "runtime_spawning" | "process_started" | "agent_ready" | "agent_started" | "agent_completed" | "agent_error" | "agent_tool_execution" | "tool_start" | "tool_end" | "experiment_progress" | "agent_cancelling" | "agent_cancelled" | "task_completed" | "task_failed"; task_id?: string; session_id?: string; tool?: string; status?: string; code?: string; run_id?: string; round?: number; total_rounds?: number; message?: string };
export type ScientistTaskStart = { task_id: string; session_id: string; status: "STARTING" };
export type ScientistTaskStatus = { task_id: string; session_id?: string; status: "STARTING" | "RUNNING" | "CANCELLING" | "CANCELLED" | "COMPLETED" | "FAILED" | "TIMED_OUT" };
export type ScientistAgentState = "UNCONFIGURED" | "RUNTIME_MISSING" | "PROVIDER_UNVERIFIED" | "READY" | "STARTING" | "PROCESS_STARTED" | "INITIALIZING" | "RUNNING" | "CANCELLING" | "COMPLETED" | "FAILED" | "TIMED_OUT";
export type PreflightCheck = { id: string; status: "PASS" | "FAIL" | "WARN"; code?: string; message?: string };
export type PreflightResult = { ready: boolean; checks: PreflightCheck[]; session_id: string };
export type RuntimeHealth = { desktop: string; backend: string; database: string; node: string; pi: string; provider: string; agent: string; manifest: Record<string, unknown> };
export type ScientistTaskInfo = { task_id: string; session_id: string; status: string; provider: string; model: string; created_at: number; started_at: number | null; completed_at: number | null; pid: number | null; last_event: string | null; last_error_code: string | null };
export type ScientistActiveTask = { task_id: string; session_id: string; status: string; provider: string; model: string; pid: number | null; last_event: string | null } | null;
export type HistorySession = { session_id:string; status:string; dataset:string; dataset_path:string | null; domain:string; model:string; hypothesis_count:number; run_count:number; updated_at:string; created_at:string; final_evaluation_revealed:boolean };
export type ResumedDatasetSession = DatasetSession & { snapshot: { round_index:number; state: { remaining_budget?:number; visible_label_count?:number; candidate_remaining?:number } } | null; research_plan_locked:boolean; final_evaluation_revealed:boolean };
export type ReportDocument = { session_id:string; path:string; content:string };

type UnknownRecord = Record<string, unknown>;

export class RpcShapeError extends Error {
  constructor(name: string) { super(`Backend response has an invalid ${name} shape. Restart the local research backend and try again.`); this.name = "RpcShapeError"; }
}

function record(value: unknown, name: string): UnknownRecord { if (!value || typeof value !== "object" || Array.isArray(value)) throw new RpcShapeError(name); return value as UnknownRecord; }
function string(value: unknown, name: string): string { if (typeof value !== "string") throw new RpcShapeError(name); return value; }
function number(value: unknown, name: string): number { if (typeof value !== "number" || !Number.isFinite(value)) throw new RpcShapeError(name); return value; }
function bool(value: unknown, name: string): boolean { if (typeof value !== "boolean") throw new RpcShapeError(name); return value; }
function list(value: unknown, name: string): unknown[] { if (!Array.isArray(value)) throw new RpcShapeError(name); return value; }
function nullableRecord(value: unknown, name: string): Record<string, unknown> { if (!value || typeof value !== "object" || Array.isArray(value)) throw new RpcShapeError(name); return value as Record<string, unknown>; }

function parseColumnProfile(value: unknown): ColumnProfile {
  const item = record(value, "ColumnProfile");
  const topValues = nullableRecord(item.top_values, "ColumnProfile.top_values");
  Object.entries(topValues).forEach(([, count]) => number(count, "ColumnProfile.top_values"));
  return { dtype: string(item.dtype, "ColumnProfile.dtype"), missing_count: number(item.missing_count, "ColumnProfile.missing_count"), missing_rate: number(item.missing_rate, "ColumnProfile.missing_rate"), unique_count: number(item.unique_count, "ColumnProfile.unique_count"), top_values: topValues as Record<string, number> };
}

function parseSchema(value: unknown): DatasetPreview["schema"] {
  const item = record(value, "DatasetSchema"); const columns = nullableRecord(item.columns, "DatasetSchema.columns");
  return { row_count: number(item.row_count, "DatasetSchema.row_count"), column_count: number(item.column_count, "DatasetSchema.column_count"), columns: Object.fromEntries(Object.entries(columns).map(([key, column]) => [key, parseColumnProfile(column)])), sample_limit_for_llm: number(item.sample_limit_for_llm, "DatasetSchema.sample_limit_for_llm") };
}

export function parseDatasetPreview(value: unknown): DatasetPreview {
  const item = record(value, "DatasetPreview"); const sample = list(item.sample, "DatasetPreview.sample").map((row) => nullableRecord(row, "DatasetPreview.sample row"));
  return { path: string(item.path, "DatasetPreview.path"), sha256: string(item.sha256, "DatasetPreview.sha256"), format: string(item.format, "DatasetPreview.format"), size_bytes: number(item.size_bytes, "DatasetPreview.size_bytes"), dataset_handle_id: item.dataset_handle_id === undefined ? undefined : string(item.dataset_handle_id, "DatasetPreview.dataset_handle_id"), schema: parseSchema(item.schema), sample: sample as Record<string, string | null>[] };
}

export function parseDatasetSession(value: unknown): DatasetSession {
  const item = record(value, "DatasetSession");
  return { session_id: string(item.session_id, "DatasetSession.session_id"), schema: parseSchema(item.schema), candidates: nullableRecord(item.candidates, "DatasetSession.candidates") as DatasetSession["candidates"], domain_spec: nullableRecord(item.domain_spec, "DatasetSession.domain_spec"), status: string(item.status, "DatasetSession.status") };
}

export function parseHistorySessions(value: unknown): { sessions: HistorySession[] } {
  const item = record(value, "HistorySessions"); const sessions = list(item.sessions, "HistorySessions.sessions").map((entry) => {
    const session = record(entry, "HistorySession");
    return { session_id: string(session.session_id, "HistorySession.session_id"), status: string(session.status, "HistorySession.status"), dataset: string(session.dataset, "HistorySession.dataset"), dataset_path: session.dataset_path === null ? null : string(session.dataset_path, "HistorySession.dataset_path"), domain: string(session.domain, "HistorySession.domain"), model: string(session.model, "HistorySession.model"), hypothesis_count: number(session.hypothesis_count, "HistorySession.hypothesis_count"), run_count: number(session.run_count, "HistorySession.run_count"), updated_at: string(session.updated_at, "HistorySession.updated_at"), created_at: string(session.created_at, "HistorySession.created_at"), final_evaluation_revealed: bool(session.final_evaluation_revealed, "HistorySession.final_evaluation_revealed") };
  }); return { sessions };
}

export function parseReportDocument(value: unknown): ReportDocument { const item = record(value, "ReportDocument"); return { session_id: string(item.session_id, "ReportDocument.session_id"), path: string(item.path, "ReportDocument.path"), content: string(item.content, "ReportDocument.content") }; }

function parseResearchSession<T extends ResearchSession | ResumedDatasetSession>(value: unknown, name: string): T { const item = record(value, name); string(item.session_id, `${name}.session_id`); string(item.status, `${name}.status`); list(item.hypotheses, `${name}.hypotheses`); list(item.plans, `${name}.plans`); list(item.runs, `${name}.runs`); return item as T; }
export const DesktopBridge = {
  call<T>(action: string, payload: Record<string, unknown> = {}) { return invoke<T>("desktop_bridge", { action, payload }); },
  healthCheck() { return this.call<DesktopHealth>("health_check"); },
  restartBackend() { return this.call<{ status: "RESTARTED" }>("backend_restart"); },
  inspectDataset(path: string) { return this.call<unknown>("inspect_dataset", { path }).then(parseDatasetPreview); },
  loadDataset(path: string, description: string, dataset_handle_id?: string) { return this.call<unknown>("load_dataset", { path, description, dataset_handle_id }).then(parseDatasetSession); },
  listSessions() { return this.call<unknown>("list_sessions").then(parseHistorySessions); },
  resumeSession(session_id: string) { return this.call<unknown>("resume_session", { session_id }).then((value) => parseResearchSession<ResumedDatasetSession>(value, "ResumedDatasetSession")); },
  deleteSession(session_id: string) { return this.call<{ status: "DELETED"; session_id: string }>("delete_session", { session_id }); },
  readReport(session_id: string) { return this.call<unknown>("read_report", { session_id }).then(parseReportDocument); },
  exportReport(session_id: string, destination: string) { return this.call<{ status: "EXPORTED" | "EXISTS"; path:string }>("export_report", { session_id, destination }); },
  openReportLocation(session_id: string) { return this.call<{ status: "OPENED"; session_id:string }>("report_open_location", { session_id }); },  getSession(session_id: string) { return this.call<unknown>("get_session", { session_id }).then((value) => parseResearchSession<ResearchSession>(value, "ResearchSession")); },
  chartData(session_id: string) { return this.call<unknown>("chart_data", { session_id }); },
  startScientist(session_id: string, question: string) { return this.call<ScientistTaskStart>("scientist_start", { session_id, question }); },
  cancelScientist(task_id: string) { return this.call<ScientistTaskStatus>("scientist_cancel", { task_id }); },
  scientistStatus(task_id: string) { return this.call<ScientistTaskStatus>("scientist_status", { task_id }); },
  scientistPreflight(session_id: string) { return this.call<PreflightResult>("scientist_preflight", { session_id }); },
  scientistActiveForSession(session_id: string) { return this.call<{ active_task: ScientistActiveTask }>("scientist_active_for_session", { session_id }); },
  listScientistTasks() { return this.call<{ tasks: ScientistTaskInfo[] }>("list_scientist_tasks"); },
  desktopRuntimeHealth() { return this.call<RuntimeHealth>("desktop_runtime_health"); },
  subscribeScientistEvents(handler: (event: ScientistEvent) => void) { return listen<ScientistEvent>("scientist-event", (event) => handler(event.payload)); },
  subscribePrecheckEvents(handler: (event: PrecheckProgress) => void) { return listen<PrecheckProgress>("precheck-event", (event) => handler(event.payload)); },
  providerStatus() { return this.call<ProviderStatus>("provider_status"); },
  saveProvider(draft: ProviderDraft) { return this.call<{ status: "SAVED"; provider: ProviderId; configured: boolean; masked_key: string }>("provider_save", draft); },
  deleteProvider(provider: ProviderId) { return this.call<{ status: "DELETED"; provider: ProviderId }>("provider_delete", { provider }); },
  setDefaultProvider(provider: ProviderId) { return this.call<{ status: "DEFAULT_UPDATED"; provider: ProviderId }>("provider_set_default", { provider }); },
  validateProvider(provider: ProviderId) { return this.call<{ status: "READY_FOR_CONNECTION_TEST"; message: string }>("provider_validate", { provider }); },
  testProviderConnection(provider: ProviderId) { return this.call<ConnectionTestResult>("provider_test_connection", { provider }); },
};
