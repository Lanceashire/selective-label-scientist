import { useEffect, useState } from "react";
import { Bot, LoaderCircle, Play, RefreshCw, ShieldCheck } from "lucide-react";
import { DesktopBridge, type DatasetSession, type ScientistEvent } from "./bridge";

function eventText(event: ScientistEvent) {
  if (event.type === "agent_started") return "Agent 已启动，正在读取受审计科研状态。";
  if (event.type === "agent_completed") return "Agent 已完成本轮科研。";
  if (event.type === "agent_error") return "Agent 后台已停止。研究数据已保留，可重新连接并恢复同一 Session。";
  if (event.type === "experiment_progress") return `实验进度：第 ${event.round ?? 0}/${event.total_rounds ?? 0} 轮。`;
  if (event.type === "tool_start" || event.type === "agent_tool_execution") return `正在执行：${event.tool || "科研工具"}`;
  return `已完成：${event.tool || "科研工具"}`;
}

export function ScientistControl({ session }: { session: DatasetSession }) {
  const [question, setQuestion] = useState("比较低预算下 LRBE-Uncertainty 和 CountOnly-MinCost 的研究可见反馈表现。");
  const [busy, setBusy] = useState(false);
  const [hostStopped, setHostStopped] = useState(false);
  const [notice, setNotice] = useState("请先在“模型与 API”中完成连接与 Tool Calling 验证。Agent 只使用受审计的科研工具。");
  const [events, setEvents] = useState<ScientistEvent[]>([]);

  useEffect(() => {
    let active = true; let stop: (() => void) | undefined;
    const subscribe = DesktopBridge.subscribeScientistEvents;
    if (!subscribe) return () => { active = false; };
    void subscribe((event) => {
      if (!active || (event.session_id && event.session_id !== session.session_id)) return;
      setEvents((previous) => [...previous.slice(-31), event]);
      setNotice(eventText(event));
      if (event.type === "agent_error") { setHostStopped(true); setBusy(false); }
      if (event.type === "agent_started") setHostStopped(false);
    }).then((unlisten) => { if (active) stop = unlisten; else unlisten(); }).catch(() => undefined);
    return () => { active = false; stop?.(); };
  }, [session.session_id]);

  const run = async () => {
    if (!question.trim()) { setNotice("请输入科研问题。"); return; }
    setBusy(true); setHostStopped(false); setEvents([]);
    setNotice("Pi Scientist Agent 正在启动并读取当前 Session 的受审计状态…");
    try {
      const result = await DesktopBridge.startScientist(session.session_id, question.trim());
      const completed = result.events.filter((event) => event.type === "tool_end").map((event) => event.tool).filter(Boolean).join(" → ");
      setNotice(completed ? `Agent 本轮已完成：${completed}` : "Agent 已结束；请在实验记录中查看持久化结果。");
    } catch { setHostStopped(true); setNotice("Agent 后台已停止。研究数据已保留，可重新连接并恢复同一 Session。"); }
    finally { setBusy(false); }
  };

  return <section className="scientist-control"><div className="provider-heading"><div><p className="kicker">PI SCIENTIST AGENT</p><h2>开始受控科研</h2><p>Session：{session.session_id}。Agent 只能调用 ECOMIC typed tools，Oracle 标签和最终指标始终隔离。</p></div><div className="security-pill"><ShieldCheck size={18}/> Oracle LOCKED</div></div><section className="card scientist-card"><label>科研问题<textarea aria-label="科研问题" value={question} onChange={(event) => setQuestion(event.target.value)} /></label><button className="primary" disabled={busy} onClick={() => void run()}>{busy ? <LoaderCircle className="spin" size={17}/> : hostStopped ? <RefreshCw size={17}/> : <Play size={17}/>} {busy ? "Agent 研究中…" : hostStopped ? "重新连接并恢复研究" : "启动 Pi Scientist Agent"}</button><p role="status" className="form-notice"><Bot size={15}/> {notice}</p>{events.length > 0 && <section className="agent-event-stream" aria-label="实时科研事件" aria-live="polite"><h3>实时科研事件</h3><ol>{events.slice(-8).map((event, index) => <li key={`${event.type}-${event.tool || "agent"}-${index}`}><span>{event.type === "tool_start" ? "进行中" : event.type === "agent_error" ? "异常" : "已记录"}</span>{eventText(event)}</li>)}</ol></section>}</section></section>;
}