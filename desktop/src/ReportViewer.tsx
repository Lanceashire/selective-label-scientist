import { useEffect, useState } from "react";
import { Clipboard, Download, FolderOpen, LoaderCircle, RefreshCw } from "lucide-react";
import { save } from "@tauri-apps/plugin-dialog";
import { DesktopBridge, type ReportDocument } from "./bridge";

type Block = { type: "h1" | "h2" | "h3" | "li" | "p" | "code"; text: string };
type LoadState = "loading" | "success" | "error";

function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = [];
  let code: string[] | null = null;
  for (const line of source.split(/\r?\n/)) {
    if (line.startsWith("```")) { if (code) { blocks.push({ type: "code", text: code.join("\n") }); code = null; } else code = []; continue; }
    if (code) { code.push(line); continue; }
    if (line.startsWith("### ")) blocks.push({ type: "h3", text: line.slice(4) });
    else if (line.startsWith("## ")) blocks.push({ type: "h2", text: line.slice(3) });
    else if (line.startsWith("# ")) blocks.push({ type: "h1", text: line.slice(2) });
    else if (line.startsWith("- ")) blocks.push({ type: "li", text: line.slice(2) });
    else if (line.trim()) blocks.push({ type: "p", text: line });
  }
  if (code) blocks.push({ type: "code", text: code.join("\n") });
  return blocks;
}

function MarkdownContent({ content }: { content: string }) {
  return <article className="markdown-report">{parseMarkdown(content).map((block, index) => {
    const key = `${block.type}-${index}`;
    if (block.type === "h1") return <h1 key={key}>{block.text}</h1>;
    if (block.type === "h2") return <h2 key={key}>{block.text}</h2>;
    if (block.type === "h3") return <h3 key={key}>{block.text}</h3>;
    if (block.type === "li") return <li key={key}>{block.text}</li>;
    if (block.type === "code") return <pre key={key}>{block.text}</pre>;
    return <p key={key}>{block.text}</p>;
  })}</article>;
}

function message(error: unknown): string { return error instanceof Error ? error.message : "无法读取报告。"; }

export function ReportViewer({ session }: { session: { session_id: string } }) {
  const [document, setDocument] = useState<ReportDocument | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [busy, setBusy] = useState<"export" | "open" | null>(null);
  const [notice, setNotice] = useState("正在读取 Session 报告…");

  const load = async () => {
    setState("loading"); setDocument(null); setNotice("正在读取 Session 报告…");
    try { const value = await DesktopBridge.readReport(session.session_id); setDocument(value); setState("success"); setNotice("报告已从本地研究记录加载。"); }
    catch (error) { setState("error"); setNotice(message(error)); }
  };

  useEffect(() => { void load(); }, [session.session_id]);

  const copy = async () => {
    if (!document) return;
    try { await navigator.clipboard?.writeText(document.content); setNotice("报告正文已复制到剪贴板。"); }
    catch (error) { setNotice(`复制失败：${message(error)}`); }
  };

  const exportFile = async () => {
    if (!document) return;
    const destination = await save({ defaultPath: `ECOMIC-${session.session_id.slice(-8)}-report.md`, filters: [{ name: "Markdown", extensions: ["md"] }] });
    if (!destination) return;
    setBusy("export");
    try { const result = await DesktopBridge.exportReport(session.session_id, destination); setNotice(result.status === "EXISTS" ? "所选文件已是当前报告。" : `已导出：${result.path}`); }
    catch (error) { setNotice(`导出失败：${message(error)}`); }
    finally { setBusy(null); }
  };

  const openLocation = async () => {
    setBusy("open");
    try { await DesktopBridge.openReportLocation(session.session_id); setNotice("已在资源管理器中定位报告文件。"); }
    catch (error) { setNotice(`无法打开文件位置：${message(error)}`); }
    finally { setBusy(null); }
  };

  const actionsDisabled = busy !== null || state === "loading";
  return <section className="report-page">
    <div className="provider-heading"><div><p className="kicker">RESEARCH REPORT</p><h2>中文科研报告</h2><p>报告来自本地 Session artifact；读取报告不依赖原始 CSV 是否仍存在。</p></div>
      <div className="report-actions">
        <button disabled={actionsDisabled} onClick={() => void load()}><RefreshCw size={16}/> 刷新报告</button>
        <button disabled={!document || actionsDisabled} onClick={() => void copy()}><Clipboard size={16}/> 复制</button>
        <button disabled={!document || actionsDisabled} onClick={() => void exportFile()}>{busy === "export" ? <LoaderCircle className="spin" size={16}/> : <Download size={16}/>} 导出</button>
        <button disabled={!document || actionsDisabled} onClick={() => void openLocation()}><FolderOpen size={16}/> 打开文件位置</button>
      </div>
    </div>
    <p className="form-notice" role="status">{notice}</p>
    {state === "loading" && <section className="card"><p>正在加载报告…</p></section>}
    {state === "error" && <section className="card"><h3>报告加载失败</h3><button className="primary" onClick={() => void load()}>重新加载</button></section>}
    {state === "success" && document && <><p className="report-path">{document.path}</p><section className="card report-document"><MarkdownContent content={document.content}/></section></>}
  </section>;
}