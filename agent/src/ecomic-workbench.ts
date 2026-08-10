/** ECOMIC Chinese workbench. Every state mutation goes through typed ResearchRuntime RPC. */
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
let activeSession: string | undefined;

function rpc(action: string, payload: Record<string, unknown>) {
  const result = spawnSync(process.env.ECOMIC_PYTHON || "python", ["-m", "agent_backend.rpc"], {
    cwd: root,
    input: `${JSON.stringify({ action, payload })}\n`, encoding: "utf8", windowsHide: true,
  });
  if (result.error) throw result.error;
  const output = JSON.parse(result.stdout.trim().split(/\r?\n/).pop() || "{}");
  if (output.status === "ERROR") throw new Error(output.message || "运行时调用失败");
  return output;
}

function safeError(error: unknown) {
  const text = String((error as any)?.message || error || "未知错误");
  if (/401/.test(text)) return "API Key 无效或没有权限";
  if (/404/.test(text)) return "模型或 API Base URL 不存在";
  if (/429/.test(text)) return "请求频率或额度受限";
  if (/timeout/i.test(text)) return "网络连接超时";
  return text.replace(/(Bearer\s+)[^\s]+/gi, "$1[REDACTED]").replace(/(api[_-]?key|token)\s*[:=]\s*[^\s,;]+/gi, "$1=[REDACTED]");
}

async function ask(ctx: any, title: string, placeholder = "") {
  const value = await ctx.ui.input(title, placeholder);
  return value?.trim();
}

function renderHome(ctx: any) {
  ctx.ui.setWidget("ecomic-home", [
    "╔════════════════════════════ ECOMIC ════════════════════════════╗",
    "║        跨领域选择性标签科研智能体 · SQLite 持久化 · Oracle 隔离   ║",
    "╠══════════════════════════════════════════════════════════════════╣",
    `║ 当前 Session：${activeSession || "未开始"}`,
    "║ /ecomic-new-research  导入数据并确认语义",
    "║ /ecomic-run           创建假设并运行真实策略",
    "║ /ecomic-final         从运行记录自动锁定并内部评估",
    "║ /ecomic-history       恢复或查看历史研究",
    "║ /ecomic-report        导出中文科研报告",
    "║ /ecomic-settings      模型与 API 设置",
    "╚══════════════════════════════════════════════════════════════════╝",
  ], { placement: "aboveEditor" });
}

export default function (pi: ExtensionAPI) {
  pi.registerCommand("ecomic-home", { description: "显示 ECOMIC 中文主界面", handler: async (_args, ctx) => renderHome(ctx) });

  pi.registerCommand("ecomic-new-research", {
    description: "导入 CSV/Parquet，确认选择性标签语义，并创建研究 Session",
    handler: async (_args, ctx) => {
      try {
        const file = await ask(ctx, "导入结构化数据集", "CSV 或 Parquet 的绝对路径");
        if (!file) return;
        const description = await ask(ctx, "数据与标签可见性说明", "例如：历史复核决定是否能获得后续标签");
        const created: any = rpc("load_dataset", { path: file, description: description || "" });
        activeSession = created.session_id;
        const inferred = created.domain_spec;
        const decision = await ask(ctx, "确认历史决策字段", inferred.historical_decision?.column || "");
        const target = await ask(ctx, "确认结果标签字段", inferred.outcome?.column || "");
        const cost = await ask(ctx, "确认观察成本字段（可选）", inferred.observation_cost?.column || "");
        const observed = await ask(ctx, "哪些决策值表示可获得后续标签？", "以逗号分隔，例如 yes,approved");
        const hidden = await ask(ctx, "哪些决策值表示标签隐藏？", "以逗号分隔，例如 no,rejected");
        const decisionTime = await ask(ctx, "决策时间字段", "");
        const outcomeTime = await ask(ctx, "结果时间字段", "");
        if (!decision || !target || !observed || !hidden) {
          ctx.ui.notify("关键字段尚未确认；Session 已安全保存，可通过 /ecomic-history 继续。", "warning");
          return;
        }
        const mapped: any = rpc("confirm_decision_mapping", {
          session_id: activeSession, decision_column: decision, target_column: target, cost_column: cost || undefined,
          observed_values: observed.split(",").map((x) => x.trim()).filter(Boolean),
          non_observed_values: hidden.split(",").map((x) => x.trim()).filter(Boolean),
          decision_time: decisionTime || undefined, outcome_time: outcomeTime || undefined,
        });
        const reversible = await ctx.ui.confirm("确认观察动作", "该动作是否可逆？（不可逆则不能运行此离线 replay 实验）");
        const simulatable = await ctx.ui.confirm("确认观察动作", "该动作是否可以由当前数据安全地模拟？");
        const actionDescription = await ask(ctx, "观察动作说明", "例如：离线重放历史记录，不触发真实业务动作");
        const approved: any = rpc("confirm_observation_action", { session_id: activeSession, reversible, simulatable, description: actionDescription || "" });
        const audit = approved.audit;
        ctx.ui.setStatus("ecomic", `ECOMIC · Session ${activeSession.slice(-8)} · ${audit.status}`);
        ctx.ui.notify(`语义审计：${audit.status}。${audit.status === "BLOCKED" ? "请修正时间顺序或语义后再实验。" : "可以创建研究假设。"}`, audit.status === "BLOCKED" ? "error" : "info");
        renderHome(ctx);
      } catch (error) { ctx.ui.notify(`研究初始化失败：${safeError(error)}`, "error"); }
    },
  });

  pi.registerCommand("ecomic-run", {
    description: "由当前 Session 创建假设、计划并运行真实动态选择策略",
    handler: async (_args, ctx) => {
      try {
        if (!activeSession) { ctx.ui.notify("请先执行 /ecomic-new-research，或在 /ecomic-history 中恢复研究。", "warning"); return; }
        const question = await ask(ctx, "研究问题 / 假设", "例如：低预算下不确定性优先是否优于数量优先？");
        if (!question) return;
        const policy = await ctx.ui.select("选择策略", ["LRBE-Uncertainty", "Random", "CountOnly-MinCost"]);
        if (!policy) return;
        const budget = Number(await ask(ctx, "预算", "30"));
        const rounds = Number(await ask(ctx, "轮数", "3"));
        if (!(budget > 0) || !(rounds >= 1)) throw new Error("预算必须大于 0，轮数必须至少为 1");
        const hypothesis: any = rpc("create_hypothesis", { session_id: activeSession, content: question });
        const plan: any = rpc("plan_experiment", { session_id: activeSession, hypothesis_id: hypothesis.hypothesis_id, policy, budget, rounds });
        const run: any = rpc("run_experiment", { session_id: activeSession, plan_id: plan.plan_id, policy, budget, seed: 7, rounds });
        ctx.ui.setWidget("ecomic-workbench", [
          `研究 Session：${activeSession}`, `策略：${policy}`, `Run：${run.run_id}`,
          `完成轮数：${run.observations?.length || 0}`, "Oracle：LOCKED 🔒（最终评估前不可见）",
          "可继续提出后续假设，或使用 /ecomic-final 锁定此 Run 的计划并评估。",
        ], { placement: "aboveEditor" });
        ctx.ui.notify(`实验完成：${run.run_id}。结果已持久化到 SQLite。`, "info");
      } catch (error) { ctx.ui.notify(`实验失败：${safeError(error)}`, "error"); }
    },
  });

  pi.registerCommand("ecomic-final", {
    description: "自动锁定最近运行所属计划，并在内部执行一次 Oracle 最终评估",
    handler: async (_args, ctx) => {
      try {
        if (!activeSession) { ctx.ui.notify("没有当前 Session。请先创建或恢复研究。", "warning"); return; }
        const snapshot: any = rpc("resume_environment", { session_id: activeSession });
        if (!snapshot.run_id) throw new Error("当前 Session 没有可恢复的实验 Run");
        rpc("lock_run_plan", { session_id: activeSession, run_id: snapshot.run_id });
        const final: any = rpc("finalize_evaluation", { session_id: activeSession, run_id: snapshot.run_id });
        ctx.ui.notify(`最终评估完成：${final.status}。指标仅由内部 Oracle 计算，Agent 未提供任何指标。`, "info");
      } catch (error) { ctx.ui.notify(`最终评估失败：${safeError(error)}`, "error"); }
    },
  });

  pi.registerCommand("ecomic-report", {
    description: "从 SQLite source of truth 导出当前 Session 的中文科研报告",
    handler: async (_args, ctx) => {
      try {
        if (!activeSession) { ctx.ui.notify("没有当前 Session。", "warning"); return; }
        const report: any = rpc("generate_report", { session_id: activeSession });
        ctx.ui.notify(`报告已导出：${report.final_report}`, "info");
      } catch (error) { ctx.ui.notify(`报告导出失败：${safeError(error)}`, "error"); }
    },
  });
}
