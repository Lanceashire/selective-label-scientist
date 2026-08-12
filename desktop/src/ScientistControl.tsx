import { useEffect, useState } from "react";
import { Bot, LoaderCircle, Play, RefreshCw, ShieldCheck, Square } from "lucide-react";
import { DesktopBridge, type DatasetSession, type ScientistEvent, type ScientistTaskStatus } from "./bridge";

type ActiveTask = { task_id: string; status: ScientistTaskStatus["status"] };

function eventText(event: ScientistEvent) {
  if (event.type === "agent_started") return "Agent 已启动，正在读取受审计科研状态。";
  if (event.type === "agent_completed" || event.type === "task_completed") return "Agent 已完成本轮科研；结果已写入当前 Session。";
  if (event.type === "agent_cancelling") return "正在安全停止 Agent 与其子进程…";
  if (event.type === "agent_cancelled") return "Agent 已停止；当前 Session 与已有研究记录已保留。";
  if (event.type === "task_failed") return event.message || "Agent 任务失败；当前 Session 已保留。";
  if (event.type === "agent_error") return event.message || "Agent 后台发生错误；当前 Session 已保留。";
  if (event.type === "experiment_progress") return `实验进度：第 ${event.round ?? 0}/${event.total_rounds ?? 0} 轮。`;
  if (event.type === "tool_start" || event.type === "agent_tool_execution") return `正在执行：${event.tool || "科研工具"}`;
  return `已完成：${event.tool || "科研工具"}`;
}

function taskIsActive(task: ActiveTask | null) { return task?.status === "STARTING" || task?.status === "RUNNING" || task?.status === "CANCELLING"; }

export function ScientistControl({ session }: { session: DatasetSession }) {
  const [question, setQuestion] = useState("比较低预算下不同选择性标签策略的研究可见反馈表现。");
  const [task, setTask] = useState<ActiveTask | null>(null);
  const [notice, setNotice] = useState("请先在“模型与 API”中完成连接与 Tool Calling 验证。Agent 只使用受审计的科研工具。");
  const [events, setEvents] = useState<ScientistEvent[]>([]);
  const active = taskIsActive(task);

  useEffect(() => {
    let alive = true;
    let stop: (() => void) | undefined;
    void DesktopBridge.subscribeScientistEvents((event) => {
      if (!alive || (event.session_id && event.session_id !== session.session_id)) return;
      setEvents((previous) => [...previous.slice(-31), event]);
      setNotice(eventText(event));
      if (event.task_id) {
        if (event.type === "agent_started") setTask({ task_id: event.task_id, status: "RUNNING" });
        if (event.type === "agent_cancelling") setTask({ task_id: event.task_id, status: "CANCELLING" });
        if (event.type === "agent_cancelled") setTask({ task_id: event.task_id, status: "CANCELLED" });
        if (event.type === "task_completed" || event.type === "agent_completed") setTask({ task_id: event.task_id, status: "COMPLETED" });
        if (event.type === "task_failed" || event.type === "agent_error") setTask({ task_id: event.task_id, status: event.code === "TASK_TIMEOUT" ? "TIMED_OUT" : "FAILED" });
      }
    }).then((unlisten) => { if (alive) stop = unlisten; else unlisten(); }).catch((error) => { if (alive) setNotice(error instanceof Error ? error.message : "无法订阅 Agent 事件。"); });
    return () => { alive = false; stop?.(); };
  }, [session.session_id]);

  const run = async () => {
    if (!question.trim()) { setNotice("请输入科研问题。"); return; }
    setEvents([]); setNotice("正在创建后台 Scientist 任务…");
    try { const started = await DesktopBridge.startScientist(session.session_id, question.trim()); setTask({ task_id: started.task_id, status: started.status }); setNotice(`Scientist 任务已启动：${started.task_id}`); }
    catch (error) { setTask(null); setNotice(error instanceof Error ? error.message : "Agent 任务无法启动。"); }
  };

  const cancel = async () => {
    if (!task || !active) return;
    setTask({ ...task, status: "CANCELLING" }); setNotice("正在安全停止 Agent 及其子进程…");
    try { const result = await DesktopBridge.cancelScientist(task.task_id); setTask({ task_id: result.task_id, status: result.status }); if (result.status === "CANCELLED") setNotice("Agent 已停止；当前 Session 已保留。"); }
    catch (error) { setNotice(error instanceof Error ? error.message : "无法停止 Agent；请在系统设置中重启本地科研后端。"); }
  };

  return <section className="scientist-control">
    <div className="provider-heading"><div><p className="kicker">PI SCIENTIST AGENT</p><h2>开始受控科研</h2><p>Session：{session.session_id}。Agent 只能调用 ECOMIC typed tools，Oracle 标签和最终指标始终隔离。</p></div><div className="security-pill"><ShieldCheck size={18}/> Oracle LOCKED</div></div>
    <section className="card scientist-card">
      <label>科研问题<textarea aria-label="科研问题" value={question} disabled={active} onChange={(event) => setQuestion(event.target.value)} /></label>
      <div className="form-actions">
        <button className="primary" disabled={active} onClick={() => void run()}>{active ? <LoaderCircle className="spin" size={17}/> : task ? <RefreshCw size={17}/> : <Play size={17}/>} {active ? "Agent 研究中" : task ? "再次启动 Pi Scientist Agent" : "启动 Pi Scientist Agent"}</button>
        {active && <button className="danger" onClick={() => void cancel()}><Square size={17}/> 停止研究</button>}
      </div>
      <p role="status" className="form-notice"><Bot size={15}/> {notice}</p>
      {task && <p className="task-status">任务：{task.task_id} · 状态：{task.status}</p>}
      {events.length > 0 && <section className="agent-event-stream" aria-label="实时科研事件" aria-live="polite"><h3>实时科研事件</h3><ol>{events.slice(-8).map((event, index) => <li key={`${event.type}-${event.tool || "agent"}-${index}`}><span>{event.type === "agent_error" || event.type === "task_failed" ? "异常" : event.type === "agent_cancelling" ? "停止中" : "已记录"}</span>{eventText(event)}</li>)}</ol></section>}
    </section>
  </section>;
}