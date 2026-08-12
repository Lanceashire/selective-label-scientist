import { useEffect, useRef, useState } from "react";
import { Database, LockKeyhole, Route, ShieldCheck } from "lucide-react";
import { DesktopBridge, type DatasetSession, type ResearchSession, type ScientistEvent } from "./bridge";
import { ScientistControl } from "./ScientistControl";
function value(input: unknown) { return Array.isArray(input) ? input.join(", ") : typeof input === "string" ? input : "待确认"; }
function label(event: ScientistEvent) { if (event.type === "experiment_progress") return `实验第 ${event.round}/${event.total_rounds} 轮完成`; if (event.type === "tool_start") return `开始 ${event.tool}`; if (event.type === "tool_end") return `完成 ${event.tool}`; if (event.type === "agent_error") return "Agent 后台已停止"; return event.type.replaceAll("_", " "); }
export function ResearchWorkbench({ session }: { session: DatasetSession }) {
 const [events, setEvents] = useState<ScientistEvent[]>([]);
 const [snapshot, setSnapshot] = useState<ResearchSession | null>(null);
 const [snapshotState, setSnapshotState] = useState<"loading" | "success" | "error">("loading");
 const [snapshotError, setSnapshotError] = useState("");
 const refreshInFlight = useRef(false);
 const refreshQueued = useRef(false);
 const refreshTimer = useRef<number | undefined>(undefined);
 const spec = session.domain_spec as Record<string, any>;
 const decision = spec.historical_decision as Record<string, any> | undefined;
 const refresh = async () => {
  if (refreshInFlight.current) { refreshQueued.current = true; return; }
  refreshInFlight.current = true;
  setSnapshotState("loading");
  try {
   const next = await DesktopBridge.getSession(session.session_id);
   setSnapshot(next);
   setSnapshotState("success");
   setSnapshotError("");
  } catch (error) {
   setSnapshotState("error");
   setSnapshotError(error instanceof Error ? error.message : String(error));
  } finally {
   refreshInFlight.current = false;
   if (refreshQueued.current) { refreshQueued.current = false; window.setTimeout(() => void refresh(), 250); }
  }
 };
 const scheduleRefresh = () => {
  if (refreshTimer.current !== undefined) return;
  refreshTimer.current = window.setTimeout(() => { refreshTimer.current = undefined; void refresh(); }, 250);
 };
 useEffect(() => { let alive = true; let stop: (() => void) | undefined; void refresh(); const subscribe = DesktopBridge.subscribeScientistEvents; if (subscribe) { void Promise.resolve(subscribe((event) => { if (!alive || (event.session_id && event.session_id !== session.session_id)) return; setEvents((items) => [...items.slice(-23), event]); if (["tool_end", "experiment_progress", "agent_completed"].includes(event.type)) scheduleRefresh(); })).then((unlisten) => { if (alive) stop = unlisten; else unlisten(); }).catch((error) => { if (alive) setSnapshotError(`实时事件订阅失败：${error instanceof Error ? error.message : String(error)}`); }); } return () => { alive = false; if (refreshTimer.current !== undefined) window.clearTimeout(refreshTimer.current); stop?.(); }; }, [session.session_id]);
 const progress = [...events].reverse().find((event) => event.type === "experiment_progress"); const latestHypothesis = snapshot?.hypotheses.at(-1); const latestRun = snapshot?.runs.at(-1);
 return <section className="research-workbench">{snapshotState === "error" && <section className="card runtime-error" role="alert"><strong>科研状态加载失败</strong><p>{snapshotError}</p><button onClick={() => void refresh()}>重新加载</button></section>}<div className="workbench-grid"><section className="card environment-panel"><p className="kicker">DATA ENVIRONMENT</p><h2><Database size={20}/> 数据环境</h2><dl><div><dt>Session</dt><dd>{session.session_id}</dd></div><div><dt>Dataset</dt><dd>{session.schema.row_count.toLocaleString()} 行 · {session.schema.column_count} 列</dd></div><div><dt>Domain</dt><dd>{value(spec.domain_name)}</dd></div><div><dt>Decision</dt><dd>{decision?.column || "待确认"} · 已观测：{value(decision?.observed_action_values)}</dd></div><div><dt>Outcome</dt><dd>{value((spec.outcome as Record<string, unknown> | undefined)?.column)}</dd></div><div><dt>Cost / Budget</dt><dd>{value((spec.observation_cost as Record<string, unknown> | undefined)?.column)} / {latestRun?.budget ?? "待计划"}</dd></div></dl><div className="oracle-lock"><LockKeyhole size={16}/> {snapshot?.final_evaluation_revealed ? "Final Evaluation 已揭示" : "Oracle LOCKED · outer metrics 未揭示"}</div></section><section className="card timeline-panel"><p className="kicker">RESEARCH TIMELINE</p><h2><Route size={20}/> 研究时间线</h2>{events.length === 0 ? <p className="empty-timeline">尚无研究事件。输入科研问题后，Agent 的假设、计划、实验与证据会在这里出现。</p> : <ol>{events.slice(-10).map((event, index) => <li key={`${event.type}-${index}`}><span className={event.type === "agent_error" ? "event-bad" : "event-good"}/><div><strong>{label(event)}</strong><small>{event.run_id ? `Run ${event.run_id}` : event.tool || "受审计 Agent 事件"}</small></div></li>)}</ol>}</section><section className="card evidence-panel"><p className="kicker">CURRENT EVIDENCE</p><h2><ShieldCheck size={20}/> 当前证据</h2><div className="evidence-number">{snapshot?.runs.length ?? 0}</div><p>已持久化实验 Runs</p><dl><div><dt>Current Hypothesis</dt><dd>{latestHypothesis?.content || "尚未创建"}</dd></div><div><dt>当前实验</dt><dd>{progress ? `${progress.round}/${progress.total_rounds} 轮` : latestRun ? `${latestRun.policy} · ${latestRun.round_end} 轮` : "尚未开始"}</dd></div><div><dt>Evidence Status</dt><dd>{latestRun ? "RESEARCH-VISIBLE" : "等待可见证据"}</dd></div><div><dt>Plans / Policies</dt><dd>{snapshot ? `${snapshot.plans.length} 个计划 / ${latestRun?.policy || "待 Agent 选择"}` : "加载中"}</dd></div></dl></section></div><section className="workbench-input"><ScientistControl session={session}/></section></section>;
}