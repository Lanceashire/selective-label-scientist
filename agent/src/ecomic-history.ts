/** SQLite 驱动的中文历史研究恢复界面。 */
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { setActiveSession } from "./ecomic-workbench.ts";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
function rpc(action: string, payload: Record<string, unknown>) { const result = spawnSync(process.env.ECOMIC_PYTHON || "python", ["-m", "agent_backend.rpc"], { cwd: root, input: `${JSON.stringify({ action, payload })}\n`, encoding: "utf8", windowsHide: true }); if (result.error) throw result.error; const output = JSON.parse(result.stdout.trim().split(/\r?\n/).pop() || "{}"); if (output.status === "ERROR") throw new Error(output.message || "ResearchRuntime 调用失败"); return output; }
export default function (pi: ExtensionAPI) { pi.registerCommand("ecomic-history", { description: "从 SQLite 会话清单选择、恢复和查看历史 ECOMIC 研究", handler: async (_args, ctx) => { try {
  const sessions: any[] = (rpc("list_sessions", {}) as any).sessions || []; if (!sessions.length) { ctx.ui.notify("尚无历史研究 Session。", "info"); return; }
  const chosen = await ctx.ui.select("历史研究", sessions.map((item) => `${item.session_id} · ${item.status} · ${String(item.updated_at).slice(0, 19)}`)); if (!chosen) return; const sessionId = chosen.split(" · ")[0]; setActiveSession(sessionId); const state: any = rpc("observe_state", { session_id: sessionId }); let resumeText = "尚无实验快照。"; try { const snapshot: any = rpc("resume_environment", { session_id: sessionId }); resumeText = `最近 Run：${snapshot.run_id || "无"}；下一轮：${snapshot.round ?? "未知"}。`; } catch { /* 新建 Session 合法地没有快照。 */ }
  ctx.ui.setStatus("ecomic", `ECOMIC · Session ${sessionId.slice(-8)} · ${state.status}`); ctx.ui.setWidget("ecomic-history", ["ECOMIC 历史研究", `Session：${sessionId}`, `状态：${state.status}`, `假设：${state.hypotheses} · 计划：${state.plans} · Runs：${state.runs}`, resumeText, "该 Session 已恢复为当前研究，可使用 /ecomic-run、/ecomic-final、/ecomic-report 或 /ecomic-scientist。"], { placement: "aboveEditor" }); ctx.ui.notify("历史研究已载入；后续动态轮次由确定性 replay 配方重建。", "info");
} catch (error: unknown) { ctx.ui.notify(`恢复失败：${String((error as { message?: string })?.message || error).replace(/Bearer\s+[^\s]+/gi, "Bearer [REDACTED]")}`, "error"); } } }); }
