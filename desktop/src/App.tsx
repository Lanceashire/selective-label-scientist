import { lazy, Suspense, useEffect, useState } from "react";
import { Activity, BarChart3, Bot, Database, FileText, FlaskConical, History, Moon, PanelLeft, PlusCircle, Settings, Sun } from "lucide-react";
import { DesktopBridge, type DatasetSession, type DesktopHealth } from "./bridge";
import { DatasetImportPage } from "./DatasetImportPage";
import { DomainSpecWizard } from "./DomainSpecWizard";
import { ProviderSettingsPage } from "./ProviderSettingsPage";
import { ResearchWorkbench } from "./ResearchWorkbench";
import { HistoryResearchPage } from "./HistoryResearchPage";
import { ReportViewer } from "./ReportViewer";
const ExperimentCharts = lazy(() => import("./ExperimentCharts").then((module) => ({ default: module.ExperimentCharts })));

type Page = "home" | "new" | "datasets" | "workbench" | "experiments" | "history" | "providers" | "settings" | "report";
const pages: { id: Page; label: string; icon: typeof Activity; hint: string }[] = [
  { id: "home", label: "首页", icon: Activity, hint: "概览、后端状态与继续研究" }, { id: "new", label: "新建研究", icon: PlusCircle, hint: "导入数据并创建新的科研 Session" },
  { id: "datasets", label: "数据集", icon: Database, hint: "查看导入数据的概要与语义候选" }, { id: "workbench", label: "科研工作台", icon: FlaskConical, hint: "数据环境、研究时间线与当前证据" },
  { id: "experiments", label: "实验记录", icon: BarChart3, hint: "策略运行、轨迹与可见证据" }, { id: "history", label: "历史研究", icon: History, hint: "恢复已持久化的 SQLite Session" },
  { id: "providers", label: "模型与 API", icon: Bot, hint: "配置 Provider、模型和安全凭据" }, { id: "settings", label: "系统设置", icon: Settings, hint: "本地运行时与界面设置" },
];

export function App() {
  const [page, setPage] = useState<Page>("home"); const [dark, setDark] = useState(true); const [compact, setCompact] = useState(false);
  const [session, setSession] = useState<DatasetSession | null>(null); const [reportSessionId, setReportSessionId] = useState<string | null>(null); const [confirmed, setConfirmed] = useState(false);
  useEffect(() => { document.documentElement.dataset.theme = dark ? "dark" : "light"; }, [dark]);
  const selected = pages.find((item) => item.id === page) ?? { id: "report" as Page, label: "科研报告", icon: FileText, hint: "查看与导出 Session 中文科研报告" };
  return <main className={compact ? "app compact" : "app"}><aside className="sidebar" aria-label="主导航"><div className="brand"><span className="brand-mark">E</span>{!compact && <span>ECOMIC <small>DESKTOP</small></span>}<button title="收起导航" onClick={() => setCompact(!compact)}><PanelLeft size={18}/></button></div><nav>{pages.map((item) => { const Icon = item.icon; return <button key={item.id} className={page === item.id ? "nav-item active" : "nav-item"} title={item.label} onClick={() => setPage(item.id)}><Icon size={19}/>{!compact && <span>{item.label}</span>}</button>; })}</nav><div className="sidebar-bottom"><span className="status-dot"/> {!compact && "本地研究模式"}</div></aside><section className="shell"><header className="topbar"><div><p className="eyebrow">ECOMIC Desktop / {selected.label}</p><h1>{selected.label}</h1></div><button className="theme-button" aria-label="切换主题" onClick={() => setDark(!dark)}>{dark ? <Sun size={18}/> : <Moon size={18}/>} {dark ? "浅色" : "深色"}</button></header><section className="content" key={page}><PageContent page={page} hint={selected.hint} session={session} reportSessionId={reportSessionId} confirmed={confirmed} onNew={() => setPage("new")} onImported={(next) => { setSession(next); setConfirmed(false); setPage("workbench"); }} onConfirmed={() => setConfirmed(true)} onResume={(next) => { setSession(next); setConfirmed(Boolean((next.domain_spec.historical_decision as { confirmed?: boolean } | undefined)?.confirmed && (next.domain_spec.observation_action as { confirmed?: boolean } | undefined)?.confirmed)); setPage("workbench"); }} onExperiments={(next) => { setSession(next); setConfirmed(Boolean((next.domain_spec.historical_decision as { confirmed?: boolean } | undefined)?.confirmed && (next.domain_spec.observation_action as { confirmed?: boolean } | undefined)?.confirmed)); setPage("experiments"); }} onReport={(sessionId) => { setReportSessionId(sessionId); setPage("report"); }}/></section><footer className="statusbar"><span><span className="status-dot"/> 科研后端：本地 Bridge</span><span>数据库：本地 SQLite</span><span>Agent Host：{confirmed ? "就绪" : "等待语义确认"}</span><span className="oracle">Oracle LOCKED</span></footer></section></main>;
}

function PageContent({ page, hint, session, reportSessionId, confirmed, onNew, onImported, onConfirmed, onResume, onExperiments, onReport }: { page: Page; hint: string; session: DatasetSession | null; reportSessionId: string | null; confirmed: boolean; onNew: () => void; onImported: (session: DatasetSession) => void; onConfirmed: () => void; onResume: (session: DatasetSession) => void; onExperiments: (session: DatasetSession) => void; onReport: (session_id: string) => void }) {
  if (page === "providers") return <ProviderSettingsPage/>;
  if (page === "new" || page === "datasets") return <DatasetImportPage onImported={onImported}/>;
  if (page === "workbench" && session) return confirmed ? <ResearchWorkbench session={session}/> : <DomainSpecWizard session={session} onConfirmed={onConfirmed}/>;
  if (page === "experiments" && session) return <Suspense fallback={<section className="card"><p>正在加载实验图表…</p></section>}><ExperimentCharts session={session}/></Suspense>;
  if (page === "history") return <HistoryResearchPage onResume={onResume} onExperiments={onExperiments} onReport={onReport}/>;
  if (page === "report" && reportSessionId) return <ReportViewer session={{ session_id: reportSessionId }}/>;
  if (page === "home") return <><section className="hero"><span className="kicker">选择性标签 · AI for Science</span><h2>把历史决策中的“不可见标签”变成可审计的科研流程。</h2><p>从数据导入、DomainSpec 确认、受控 Scientist Agent，到最终评价与中文报告，全部在一个本地桌面工作区内完成。</p><div className="actions"><button className="primary" onClick={onNew}>新建研究</button></div></section><section className="cards"><HealthCard/><StatusCard title="当前研究" value={session ? "已创建 Session" : "尚未选择"} note={session ? session.session_id : "从“新建研究”导入 CSV / Parquet"}/><StatusCard title="最终评价" value="Oracle LOCKED" note="研究阶段不显示 outer metrics"/></section></>;
  return <section className="placeholder"><p className="kicker">{page.toUpperCase()}</p><h2>{hint}</h2><p>该模块将在后续科研工作流中接入真实 Session 数据。</p><div className="empty-icon"><FileText size={28}/></div></section>;
}

function displayRuntimeStatus(value: string, labels: Record<string, string>): string {
  return labels[value.toLowerCase()] ?? value;
}
function HealthCard() {
  const [health, setHealth] = useState<DesktopHealth | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const check = async () => {
    setBusy(true);
    setError(null);
    try {
      setHealth(await DesktopBridge.healthCheck());
    } catch {
      setHealth(null);
      setError("后端不可用，请检查本地科研后端后重试。");
    } finally {
      setBusy(false);
    }
  };
  const backend = health ? displayRuntimeStatus(health.backend, { ready: "正常", busy: "忙碌", restarting: "重启中", error: "异常" }) : null;
  const database = health ? displayRuntimeStatus(health.database, { ready: "正常", busy: "忙碌", error: "异常" }) : null;
  const agentHost = health ? displayRuntimeStatus(health.agent_host, { idle: "未启动", running: "运行中", cancelling: "正在停止", error: "异常" }) : null;
  return <article className="card"><p>科研后端</p><h3>{backend ?? (error ? "后端不可用" : "待连接")}</h3><small>{health ? `数据库：${database} · Agent Host：${agentHost}` : error ?? "通过 Tauri IPC 检查本地 Sidecar"}</small><button className="primary health-button" disabled={busy} onClick={() => void check()}>{busy ? "检查中…" : error ? "重新检查后端" : "后端状态"}</button></article>;
}
function StatusCard({ title, value, note }: { title: string; value: string; note: string }) { return <article className="card"><p>{title}</p><h3>{value}</h3><small>{note}</small></article>; }
