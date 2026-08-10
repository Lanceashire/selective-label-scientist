/** SQLite-backed session picker for the ECOMIC Pi workbench. */
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
function rpc(action: string, payload: Record<string, unknown>) {
  const result = spawnSync(process.env.ECOMIC_PYTHON || "python", ["-m", "agent_backend.rpc"], { cwd: root, input: `${JSON.stringify({ action, payload })}\n`, encoding: "utf8", windowsHide: true });
  if (result.error) throw result.error;
  const output = JSON.parse(result.stdout.trim().split(/\r?\n/).pop() || "{}");
  if (output.status === "ERROR") throw new Error(output.message || "运行时调用失败");
  return output;
}

export default function (pi: ExtensionAPI) {
  pi.registerCommand("ecomic-history", {
    description: "从 SQLite 会话清单选择、恢复和查看历史 ECOMIC 研究",
    handler: async (_args, ctx) => {
      try {
        const sessions: any[] = (rpc("list_sessions", {}) as any).sessions || [];
        if (!sessions.length) { ctx.ui.notify("尚无历史研究。", "info"); return; }
        const options = sessions.map((item) => `${item.session_id} · ${item.status} · ${String(item.updated_at).slice(0, 19)}`);
        const chosen = await ctx.ui.select("历史研究", options);
        if (!chosen) return;
        const sessionId = chosen.split(" · ")[0];
        const state: any = rpc("observe_state", { session_id: sessionId });
        let resumeText = "尚无实验快照";
        try {
          const snapshot: any = rpc("resume_environment", { session_id: sessionId });
          resumeText = `最近 Run：${snapshot.run_id || "无"} · 下一轮：${snapshot.round ?? "未知"}`;
        } catch { /* A new session legitimately has no snapshot. */ }
        ctx.ui.setWidget("ecomic-history", ["ECOMIC 历史研究", `Session：${sessionId}`, `状态：${state.status}`, `假设：${state.hypotheses} · 计划：${state.plans} · Runs：${state.runs}`, resumeText, "使用 /ecomic-report 导出该研究的报告。"], { placement: "aboveEditor" });
        ctx.ui.notify("历史研究已载入。请使用工作台继续；恢复后的动态轮次由确定性 replay 配方重建。", "info");
      } catch (error: any) { ctx.ui.notify(`恢复失败：${String(error?.message || error).replace(/Bearer\s+[^\s]+/gi, "Bearer [REDACTED]")}`, "error"); }
    },
  });
}
