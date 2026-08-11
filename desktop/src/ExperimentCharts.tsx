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
};

function EmptyChart({ text }: { text: string }) { return <p className="chart-empty">{text}</p>; }

export function ExperimentCharts({ session }: { session: DatasetSession }) {
  const [data, setData] = useState<ChartData | null>(null);
  useEffect(() => {
    void DesktopBridge.call<ChartData>("chart_data", { session_id: session.session_id }).then(setData).catch(() => undefined);
  }, [session.session_id]);
  if (!data) return <section className="card"><h2>实验结果</h2><p>正在读取研究可见数据…</p></section>;

  const hasRuns = data.runs.length > 0;
  const feedbackTrajectory = data.feedback_trajectory ?? [];
  const hypothesisTimeline = data.hypothesis_timeline ?? [];
  const final = data.final_metrics;
  return <section className="chart-page">
    <div className="provider-heading"><div><p className="kicker">EXPERIMENT RESULTS</p><h2>实验结果与策略比较</h2><p>{data.research_mode ? "研究模式：仅展示可审计的反馈、预算和策略过程；最终外部指标仍由 Oracle 隔离。" : "最终评价已揭示：过程记录保持只读，外部评价仅在下方显示。"}</p></div></div>
    <div className="chart-grid">
      <section className="card"><h3>Feedback Count vs Budget</h3>{hasRuns ? <ResponsiveContainer width="100%" height={240}><BarChart data={data.policy_comparison}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="policy"/><YAxis allowDecimals={false}/><Tooltip/><Legend/><Bar dataKey="feedback_count" name="Feedback Count" fill="#56c2a6"/></BarChart></ResponsiveContainer> : <EmptyChart text="尚无实验运行。"/>}</section>
      <section className="card"><h3>Budget Utilization vs Policy</h3>{hasRuns ? <ResponsiveContainer width="100%" height={240}><BarChart data={data.policy_comparison}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="policy"/><YAxis domain={[0, 1]} tickFormatter={(value) => `${Math.round(Number(value) * 100)}%`}/><Tooltip formatter={(value) => `${(Number(value) * 100).toFixed(1)}%`}/><Legend/><Bar dataKey="budget_utilization" name="Budget Utilization" fill="#f4ae5e"/></BarChart></ResponsiveContainer> : <EmptyChart text="尚无预算利用记录。"/>}</section>
      <section className="card"><h3>Policy Comparison</h3>{hasRuns ? <ResponsiveContainer width="100%" height={240}><BarChart data={data.policy_comparison}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="policy"/><YAxis allowDecimals={false}/><Tooltip/><Legend/><Bar dataKey="rounds" name="Rounds" fill="#8b7cff"/><Bar dataKey="feedback_count" name="Feedback Count" fill="#56c2a6"/></BarChart></ResponsiveContainer> : <EmptyChart text="运行策略将在此处并列比较。"/>}</section>
      <section className="card"><h3>Run Trajectory</h3>{feedbackTrajectory.length ? <ResponsiveContainer width="100%" height={240}><LineChart data={feedbackTrajectory}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="round"/><YAxis allowDecimals={false}/><Tooltip/><Legend/><Line type="monotone" dataKey="feedback_count" name="Cumulative Feedback" stroke="#8b7cff"/></LineChart></ResponsiveContainer> : <EmptyChart text="尚无轮次轨迹。"/>}</section>
      <section className="card"><h3>Hypothesis Timeline</h3>{hypothesisTimeline.length ? <ResponsiveContainer width="100%" height={220}><BarChart data={hypothesisTimeline}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="order"/><YAxis allowDecimals={false}/><Tooltip formatter={(value, _name, entry) => [String(value), String((entry as { payload?: { content?: string } }).payload?.content ?? "Hypothesis")]}/><Bar dataKey="order" name="Hypothesis Order" fill="#5e9ef4"/></BarChart></ResponsiveContainer> : <EmptyChart text="尚未记录研究假设。"/>}</section>
    </div>
    {!data.research_mode && final && <section className="card final-metrics"><h3>Final ROC-AUC / PR-AUC</h3><p>Final Evaluation</p><dl>{Object.entries(final).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === "number" ? value.toFixed(4) : String(value)}</dd></div>)}</dl></section>}
  </section>;
}