import { useEffect, useState } from "react";
import { Clipboard, Download, FolderOpen, LoaderCircle, RefreshCw } from "lucide-react";
import { save } from "@tauri-apps/plugin-dialog";
import { DesktopBridge, type DatasetSession, type ReportDocument } from "./bridge";

type Block = { type: "h1" | "h2" | "h3" | "li" | "p" | "code"; text: string };
function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = []; let code: string[] | null = null;
  for (const line of source.split(/\r?\n/)) {
    if (line.startsWith("```")) { if (code) { blocks.push({ type:"code", text:code.join("\n") }); code = null; } else code = []; continue; }
    if (code) { code.push(line); continue; }
    if (line.startsWith("### ")) blocks.push({ type:"h3", text:line.slice(4) });
    else if (line.startsWith("## ")) blocks.push({ type:"h2", text:line.slice(3) });
    else if (line.startsWith("# ")) blocks.push({ type:"h1", text:line.slice(2) });
    else if (line.startsWith("- ")) blocks.push({ type:"li", text:line.slice(2) });
    else if (line.trim()) blocks.push({ type:"p", text:line });
  }
  if (code) blocks.push({ type:"code", text:code.join("\n") });
  return blocks;
}
function MarkdownContent({ content }: { content: string }) { return <article className="markdown-report">{parseMarkdown(content).map((block, index) => { const key = `${block.type}-${index}`; if (block.type === "h1") return <h1 key={key}>{block.text}</h1>; if (block.type === "h2") return <h2 key={key}>{block.text}</h2>; if (block.type === "h3") return <h3 key={key}>{block.text}</h3>; if (block.type === "li") return <li key={key}>{block.text}</li>; if (block.type === "code") return <pre key={key}>{block.text}</pre>; return <p key={key}>{block.text}</p>; })}</article>; }

export function ReportViewer({ session }: { session: DatasetSession }) {
  const [document, setDocument] = useState<ReportDocument | null>(null);
  const [busy, setBusy] = useState<"load" | "export" | "open" | null>("load");
  const [notice, setNotice] = useState("正在读取 Session 报告…");
  const load = async () => { setBusy("load"); try { const value = await DesktopBridge.readReport(session.session_id); setDocument(value); setNotice("报告已从本地 SQLite 研究记录生成并加载。"); } catch { setNotice("无法读取报告。请先完成或恢复该 Session。 "); } finally { setBusy(null); } };
  useEffect(() => { void load(); }, [session.session_id]);
  const copy = async () => { if (!document) return; try { await navigator.clipboard?.writeText(document.content); setNotice("报告正文已复制到剪贴板。"); } catch { setNotice("复制失败；请在报告内手动选择文本。 "); } };
  const exportFile = async () => { if (!document) return; const destination = await save({ defaultPath:`ECOMIC-${session.session_id.slice(-8)}-report.md`, filters:[{ name:"Markdown", extensions:["md"] }] }); if (!destination) return; setBusy("export"); try { const result = await DesktopBridge.exportReport(session.session_id, destination); setNotice(result.status === "EXISTS" ? "选择的文件已是当前报告。" : `已导出：${result.path}`); } catch { setNotice("导出失败：请选择一个可写入的 .md 文件位置。 "); } finally { setBusy(null); } };
  const open = async () => { setBusy("open"); try { await DesktopBridge.openReportLocation(session.session_id); setNotice("已在 Windows 资源管理器中定位报告文件。"); } catch { setNotice("无法打开文件位置，但报告仍可在此窗口阅读和导出。 "); } finally { setBusy(null); } };
  return <section className="report-page"><div className="provider-heading"><div><p className="kicker">RESEARCH REPORT</p><h2>中文科研报告</h2><p>报告由本地 SQLite 的 Session、DomainSpec、实验、证据和 Final Evaluation 生成；不会写入 API Key、Authorization header 或模型私有推理过程。</p></div><div className="report-actions"><button disabled={busy !== null} onClick={() => void load()}><RefreshCw size={16}/> 重新生成</button><button disabled={!document || busy !== null} onClick={() => void copy()}><Clipboard size={16}/> 复制</button><button disabled={!document || busy !== null} onClick={() => void exportFile()}>{busy === "export" ? <LoaderCircle className="spin" size={16}/> : <Download size={16}/>} 导出</button><button disabled={!document || busy !== null} onClick={() => void open()}><FolderOpen size={16}/> 打开文件位置</button></div></div><p className="form-notice" role="status">{notice}</p>{document ? <><p className="report-path">{document.path}</p><section className="card report-document"><MarkdownContent content={document.content}/></section></> : <section className="card"><p>报告加载中…</p></section>}</section>;
}