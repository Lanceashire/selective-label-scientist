import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { DesktopBridge, type DatasetSession } from "./bridge";

type Run = { run_id:string; policy:string; budget:number; rounds:number; feedback_count:number; budget_utilization:number; status:string };
type ChartData = {
  research_mode: boolean;
  runs: Run[];
  feedback_trajectory: { run_id:string; policy:string; round:number; feedback_count:number; budget:number }[];
  hypothesis_timeline: { hypothesis_id:string; order:number; content:string }[];
  policy_comparison: { policy:string; budget:number; rounds:number; feedback_count:number; budget_utilization:number }[];
  final_metrics: Record<string, number> | null;
  feedback_trajectory_total_points?: number;
  feedback_trajectory_downsampled?: boolean;
  chart_point_limit?: number;
  hypothesis_timeline_downsampled?: boolean;
  runs_downsampled?: boolean;
};

const MAX_RENDERED_TRAJECTORY_POINTS = 2_000;

function downsampleTrajectory<T>(points: T[], limit = MAX_RENDERED_TRAJECTORY_POINTS): T[] {
  if (points.length <= limit) return points;
  return Array.from({ length: limit }, (_, index) => points[Math.round(index * (points.length - 1) / (limit - 1))]);
}

function EmptyChart({ text }: { text: string }) { return <p className="chart-empty">{text}</p>; }

function parseChartData(value: unknown): ChartData {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Backend returned malformed chart data.");
  const data = value as Record<string, unknown>;
  if (typeof data.research_mode !== "boolean" || !Array.isArray(data.runs) || !Array.isArray(data.policy_comparison)) throw new Error("Backend returned malformed chart data.");
  if (data.feedback_trajectory !== undefined && !Array.isArray(data.feedback_trajectory)) throw new Error("Backend returned malformed feedback trajectory.");
  if (data.hypothesis_timeline !== undefined && !Array.isArray(data.hypothesis_timeline)) throw new Error("Backend returned malformed hypothesis timeline.");
  if (data.final_metrics !== null && data.final_metrics !== undefined && (typeof data.final_metrics !== "object" || Array.isArray(data.final_metrics))) throw new Error("Backend returned malformed chart metrics.");
  return { ...data, feedback_trajectory: data.feedback_trajectory ?? [], hypothesis_timeline: data.hypothesis_timeline ?? [], final_metrics: data.final_metrics ?? null, feedback_trajectory_total_points: typeof data.feedback_trajectory_total_points === "number" ? data.feedback_trajectory_total_points : undefined, feedback_trajectory_downsampled: data.feedback_trajectory_downsampled === true, chart_point_limit: typeof data.chart_point_limit === "number" ? data.chart_point_limit : undefined, hypothesis_timeline_downsampled: data.hypothesis_timeline_downsampled === true, runs_downsampled: data.runs_downsampled === true } as ChartData;
}

export function ExperimentCharts({ session }: { session: DatasetSession }) {
  const [data, setData] = useState<ChartData | null>(null);
  const [loadState, setLoadState] = useState<"loading" | "success" | "error">("loading");
  const [error, setError] = useState("");
  const load = async () => {
    setLoadState("loading"); setError("");
    try { const result = await DesktopBridge.call<unknown>("chart_data", { session_id: session.session_id }); setData(parseChartData(result)); setLoadState("success"); }
    catch (reason) { setData(null); setError(reason instanceof Error ? reason.message : "Experiment data could not be loaded."); setLoadState("error"); }
  };
  useEffect(() => { void load(); }, [session.session_id]);
  if (loadState === "loading") return <section className="card"><h2>实验结果</h2><p>正在读取研究可见数据…</p></section>;
  if (loadState === "error") return <section className="card"><h2>实验数据加载失败</h2><p className="form-notice">{error}</p><button className="primary" onClick={() => void load()}>重新加载</button></section>;
  if (!data) return <section className="card"><h2>实验结果</h2><p>暂无可显示的实验数据。</p></section>;
  const hasRuns = data.runs.length > 0;
  const feedbackTrajectory = data.feedback_trajectory ?? [];
  const renderedTrajectory = downsampleTrajectory(feedbackTrajectory);
  const frontendDownsampled = renderedTrajectory.length !== feedbackTrajectory.length;
  const hypothesisTimeline = data.hypothesis_timeline ?? [];
  const final = data.final_metrics;
  return <section className="chart-page">
    <div className="provider-heading"><div><p className="kicker">EXPERIMENT RESULTS</p><h2>实验结果与策略比较</h2><p>{data.research_mode ? "研究模式：仅展示可审计的反馈、预算和策略过程；最终外部指标仍由 Oracle 隔离。" : "最终评价已揭示：过程记录保持只读，外部评价仅在下方显示。"}</p></div></div>
    {(data.feedback_trajectory_downsampled || frontendDownsampled || data.hypothesis_timeline_downsampled || data.runs_downsampled) && <p className="form-notice" role="status">为保持桌面流畅，长实验的图表已降采样显示{data.feedback_trajectory_total_points ? `（原始轨迹 ${data.feedback_trajectory_total_points.toLocaleString()} 点）` : ""}；完整轮次记录仍保存在本地 artifact。</p>}
    <div className="chart-grid">
      <section className="card"><h3>Feedback Count vs Budget</h3>{hasRuns ? <ResponsiveContainer width="100%" height={240}><BarChart data={data.policy_comparison}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="policy"/><YAxis allowDecimals={false}/><Tooltip/><Legend/><Bar dataKey="feedback_count" name="Feedback Count" fill="#56c2a6"/></BarChart></ResponsiveContainer> : <EmptyChart text="尚无实验运行。"/>}</section>
      <section className="card"><h3>Budget Utilization vs Policy</h3>{hasRuns ? <ResponsiveContainer width="100%" height={240}><BarChart data={data.policy_comparison}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="policy"/><YAxis domain={[0, 1]} tickFormatter={(value) => `${Math.round(Number(value) * 100)}%`}/><Tooltip formatter={(value) => `${(Number(value) * 100).toFixed(1)}%`}/><Legend/><Bar dataKey="budget_utilization" name="Budget Utilization" fill="#f4ae5e"/></BarChart></ResponsiveContainer> : <EmptyChart text="尚无预算利用记录。"/>}</section>
      <section className="card"><h3>Policy Comparison</h3>{hasRuns ? <ResponsiveContainer width="100%" height={240}><BarChart data={data.policy_comparison}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="policy"/><YAxis allowDecimals={false}/><Tooltip/><Legend/><Bar dataKey="rounds" name="Rounds" fill="#8b7cff"/><Bar dataKey="feedback_count" name="Feedback Count" fill="#56c2a6"/></BarChart></ResponsiveContainer> : <EmptyChart text="运行策略将在此处并列比较。"/>}</section>
      <section className="card"><h3>Run Trajectory</h3>{renderedTrajectory.length ? <ResponsiveContainer width="100%" height={240}><LineChart data={renderedTrajectory}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="round"/><YAxis allowDecimals={false}/><Tooltip/><Legend/><Line type="monotone" dataKey="feedback_count" name="Cumulative Feedback" stroke="#8b7cff"/></LineChart></ResponsiveContainer> : <EmptyChart text="尚无轮次轨迹。"/>}</section>
      <section className="card"><h3>Hypothesis Timeline</h3>{hypothesisTimeline.length ? <ResponsiveContainer width="100%" height={220}><BarChart data={hypothesisTimeline}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="order"/><YAxis allowDecimals={false}/><Tooltip formatter={(value, _name, entry) => [String(value), String((entry as { payload?: { content?: string } }).payload?.content ?? "Hypothesis")]}/><Bar dataKey="order" name="Hypothesis Order" fill="#5e9ef4"/></BarChart></ResponsiveContainer> : <EmptyChart text="尚未记录研究假设。"/>}</section>
    </div>
    {!data.research_mode && final && <section className="card final-metrics"><h3>Final ROC-AUC / PR-AUC</h3><p>Final Evaluation</p><dl>{Object.entries(final).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === "number" ? value.toFixed(4) : String(value)}</dd></div>)}</dl></section>}
  </section>;
}