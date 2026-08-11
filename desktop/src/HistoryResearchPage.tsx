import { useEffect, useState } from "react";
import { BarChart3, FolderOpen, History, LoaderCircle, RefreshCw, Trash2 } from "lucide-react";
import { DesktopBridge, type HistorySession, type ResumedDatasetSession } from "./bridge";

function when(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

export function HistoryResearchPage({ onResume, onExperiments, onReport }: { onResume: (session: ResumedDatasetSession) => void; onExperiments: (session: ResumedDatasetSession) => void; onReport: (session: ResumedDatasetSession) => void }) {
  const [items, setItems] = useState<HistorySession[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState("正在读取本地 SQLite 历史研究…");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const refresh = async () => {
    setBusy("refresh");
    try { const result = await DesktopBridge.listSessions(); setItems(result.sessions); setNotice(result.sessions.length ? `已载入 ${result.sessions.length} 个本地 Session。` : "尚无本地历史研究。"); }
    catch { setNotice("无法读取历史研究。请检查本地科研后端是否正常。 "); }
    finally { setBusy(null); }
  };
  useEffect(() => { void refresh(); }, []);
  const restore = async (item: HistorySession, target: "workbench" | "experiments" | "report") => {
    setBusy(item.session_id); setNotice("正在从 SQLite 快照恢复同一 Session…");
    try { const restored = await DesktopBridge.resumeSession(item.session_id); target === "workbench" ? onResume(restored) : target === "experiments" ? onExperiments(restored) : onReport(restored); }
    catch { setNotice("无法恢复该 Session：原始数据集可能已移动、删除或不再可读取。 "); }
    finally { setBusy(null); }
  };
  const remove = async (item: HistorySession) => {
    setBusy(item.session_id);
    try { await DesktopBridge.deleteSession(item.session_id); setConfirmDelete(null); setItems((current) => current.filter((entry) => entry.session_id !== item.session_id)); setNotice("已删除该 Session 及其生成的研究产物；原始数据集文件未被删除。"); }
    catch { setNotice("删除失败，原始数据和当前研究均未被改动。 "); }
    finally { setBusy(null); }
  };
  return <section className="history-page"><div className="provider-heading"><div><p className="kicker">SESSION HISTORY</p><h2>历史研究</h2><p>所有记录来自本地 SQLite。恢复会使用原 Session ID 与已保存的环境快照，不会新建或从 Round 0 重跑。</p></div><button onClick={() => void refresh()} disabled={busy !== null}><RefreshCw size={16}/> 刷新</button></div><p className="form-notice" role="status">{notice}</p>{items.length === 0 && busy !== "refresh" ? <section className="card empty-history"><History size={26}/><h3>还没有历史研究</h3><p>导入 CSV 或 Parquet 并创建 Session 后，研究记录会自动保存在这里。</p></section> : <div className="history-list">{items.map((item) => <article className="card history-card" key={item.session_id}><div className="history-title"><div><p className="kicker">{item.status}</p><h3>{item.dataset}</h3><small title={item.session_id}>Session · {item.session_id}</small></div><span className={item.final_evaluation_revealed ? "history-final" : "history-research"}>{item.final_evaluation_revealed ? "FINALIZED" : "RESEARCH"}</span></div><dl><div><dt>Domain</dt><dd>{item.domain}</dd></div><div><dt>Model</dt><dd>{item.model}</dd></div><div><dt>Hypotheses / Runs</dt><dd>{item.hypothesis_count} / {item.run_count}</dd></div><div><dt>Updated Time</dt><dd>{when(item.updated_at)}</dd></div></dl><div className="history-actions"><button className="primary" disabled={busy !== null} onClick={() => void restore(item, "workbench")}>{busy === item.session_id ? <LoaderCircle className="spin" size={16}/> : <FolderOpen size={16}/>} 打开 / 恢复</button><button disabled={busy !== null} onClick={() => void restore(item, "experiments")}><BarChart3 size={16}/> 查看实验</button><button disabled={busy !== null} onClick={() => void restore(item, "report")}><FolderOpen size={16}/> 查看报告</button>{confirmDelete === item.session_id ? <><span className="delete-warning">确认删除此 Session？</span><button className="danger" disabled={busy !== null} onClick={() => void remove(item)}>确认删除</button><button disabled={busy !== null} onClick={() => setConfirmDelete(null)}>取消</button></> : <button className="danger" disabled={busy !== null} onClick={() => setConfirmDelete(item.session_id)}><Trash2 size={16}/> 删除</button>}</div></article>)}</div>}</section>;
}