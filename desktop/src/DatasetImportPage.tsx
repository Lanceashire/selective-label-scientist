import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { Database, FileUp, LoaderCircle, ShieldCheck } from "lucide-react";
import { DesktopBridge, type DatasetPreview, type DatasetSession } from "./bridge";

type Props = { onImported?: (session: DatasetSession, preview: DatasetPreview) => void };

function errorMessage(error: unknown) {
  return typeof error === "string" ? error : error instanceof Error ? error.message : "数据集处理失败，请检查文件格式与编码。";
}

export function DatasetImportPage({ onImported }: Props) {
  const [path, setPath] = useState("");
  const [description, setDescription] = useState("");
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [notice, setNotice] = useState("支持 CSV、Parquet；桌面端只接收摘要、统计信息和有限样本，不会传输整张数据表。");
  const [busy, setBusy] = useState(false);

  const acceptPath = (candidate?: string) => {
    if (!candidate) return;
    if (!/\.(csv|parquet|pq)$/i.test(candidate)) {
      setNotice("仅支持 CSV 或 Parquet 文件。");
      return;
    }
    setPath(candidate);
    setPreview(null);
    setNotice("已选择文件，可先预检再创建研究 Session。");
  };

  const choose = async () => {
    const chosen = await open({ multiple: false, directory: false, filters: [{ name: "数据集", extensions: ["csv", "parquet", "pq"] }] });
    if (typeof chosen === "string") acceptPath(chosen);
  };

  const drop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const item = event.dataTransfer.files.item(0) as (File & { path?: string }) | null;
    // Native Tauri drops expose `path`; browser fallback intentionally keeps the page safe.
    acceptPath(item?.path);
  };

  const inspect = async () => {
    if (!path.trim()) { setNotice("请先选择 CSV 或 Parquet 文件。"); return; }
    setBusy(true);
    try {
      const result = await DesktopBridge.inspectDataset(path.trim());
      setPreview(result);
      setNotice("数据预检完成。确认摘要后可创建新的研究 Session。");
    } catch (error) {
      setPreview(null);
      setNotice(errorMessage(error));
    } finally { setBusy(false); }
  };

  const create = async () => {
    if (!preview) { setNotice("请先完成数据预检。"); return; }
    setBusy(true);
    try {
      const session = await DesktopBridge.loadDataset(preview.path, description);
      setNotice(`已创建研究 Session：${session.session_id}`);
      onImported?.(session, preview);
    } catch (error) { setNotice(errorMessage(error)); }
    finally { setBusy(false); }
  };

  const columns = preview ? Object.entries(preview.schema.columns) : [];
  return <section className="dataset-import">
    <div className="provider-heading"><div><p className="kicker">DATASET IMPORT</p><h2>导入研究数据集</h2><p>导入后先展示哈希、Schema、缺失率、Top Values 与字段候选；确认后才创建 SQLite 研究 Session。</p></div><div className="security-pill"><ShieldCheck size={18}/> 本地 DuckDB 预检</div></div>
    <section className="card dataset-form">
      <div className="dataset-dropzone" role="button" tabIndex={0} aria-label="拖拽数据集到这里" onDragOver={(event) => event.preventDefault()} onDrop={drop} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") void choose(); }}>
        <FileUp size={22}/><strong>拖拽 CSV / Parquet 文件到这里</strong><span>或使用下方文件选择器；数据预览只保留必要的有限样本。</span>
      </div>
      <label>文件路径<input aria-label="数据集路径" value={path} onChange={(event) => { setPath(event.target.value); setPreview(null); }} placeholder="选择 .csv / .parquet 文件" /></label>
      <button onClick={() => void choose()} disabled={busy}><FileUp size={16}/> 选择文件</button>
      <label>业务语义说明（可选）<textarea aria-label="业务语义说明" value={description} onChange={(event) => setDescription(event.target.value)} placeholder="例如：历史审核决策决定后续风险标签是否可见" /></label>
      <div className="form-actions"><button className="primary" onClick={() => void inspect()} disabled={busy}>{busy ? <LoaderCircle className="spin" size={16}/> : <Database size={16}/>} 预检数据集</button><button className="connection-button" onClick={() => void create()} disabled={busy || !preview}>创建研究 Session</button></div>
      <p className="form-notice" role="status">{notice}</p>
    </section>
    {preview && <section className="dataset-preview"><div className="dataset-metadata card"><h3>数据集概要</h3><dl><div><dt>文件</dt><dd>{preview.path}</dd></div><div><dt>格式</dt><dd>{preview.format.toUpperCase()}</dd></div><div><dt>大小</dt><dd>{(preview.size_bytes / 1024 / 1024).toFixed(2)} MB</dd></div><div><dt>SHA-256</dt><dd className="hash">{preview.sha256}</dd></div><div><dt>行 / 列</dt><dd>{preview.schema.row_count.toLocaleString()} / {preview.schema.column_count}</dd></div></dl></div><section className="card"><h3>字段 Profile</h3><div className="profile-table"><table><thead><tr><th>字段</th><th>类型</th><th>缺失率</th><th>唯一值</th><th>Top Values</th></tr></thead><tbody>{columns.map(([name, column]) => <tr key={name}><td>{name}</td><td>{column.dtype}</td><td>{(column.missing_rate * 100).toFixed(2)}%</td><td>{column.unique_count.toLocaleString()}</td><td>{Object.entries(column.top_values).slice(0, 3).map(([value, count]) => `${value} (${count})`).join(" · ") || "—"}</td></tr>)}</tbody></table></div></section></section>}
  </section>;
}
