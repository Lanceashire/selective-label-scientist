/** SQLite-backed history picker that shares the active workbench session. */
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { setActiveSession } from "./ecomic-workbench.ts";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
function rpc(action: string, payload: Record<string, unknown>) {
  const result = spawnSync(process.env.ECOMIC_PYTHON || "python", ["-m", "agent_backend.rpc"], { cwd: root, input: `${JSON.stringify({ action, payload })}\n`, encoding: "utf8", windowsHide: true });
  if (result.error) throw result.error;
  const output = JSON.parse(result.stdout.trim().split(/\r?\n/).pop() || "{}");
  if (output.status === "ERROR") throw new Error(output.message || "ResearchRuntime failed");
  return output;
}
export default function (pi: ExtensionAPI) {
  pi.registerCommand("ecomic-history", {
    description: "Choose, restore, and inspect a persisted ECOMIC research session.",
    handler: async (_args, ctx) => {
      try {
        const sessions: any[] = (rpc("list_sessions", {}) as any).sessions || [];
        if (!sessions.length) { ctx.ui.notify("No historical research sessions are available.", "info"); return; }
        const chosen = await ctx.ui.select("Historical research", sessions.map((item) => `${item.session_id} / ${item.status} / ${String(item.updated_at).slice(0, 19)}`));
        if (!chosen) return;
        const sessionId = chosen.split(" / ")[0];
        setActiveSession(sessionId);
        const state: any = rpc("observe_state", { session_id: sessionId });
        let resumeText = "No experiment snapshot yet.";
        try { const snapshot: any = rpc("resume_environment", { session_id: sessionId }); resumeText = `Latest run: ${snapshot.run_id || "none"}; next round: ${snapshot.round ?? "unknown"}.`; } catch { /* New sessions may have no snapshot. */ }
        ctx.ui.setStatus("ecomic", `ECOMIC / Session ${sessionId.slice(-8)} / ${state.status}`);
        ctx.ui.setWidget("ecomic-history", ["ECOMIC historical research", `Session: ${sessionId}`, `Status: ${state.status}`, `Hypotheses: ${state.hypotheses}; plans: ${state.plans}; runs: ${state.runs}`, resumeText, "This session is now active. Use /ecomic-run, /ecomic-final, or /ecomic-report."], { placement: "aboveEditor" });
        ctx.ui.notify("Historical research loaded. Deterministic replay reconstructs later dynamic rounds.", "info");
      } catch (error: unknown) { ctx.ui.notify(`Restore failed: ${String((error as { message?: string })?.message || error).replace(/Bearer\s+[^\s]+/gi, "Bearer [REDACTED]")}`, "error"); }
    },
  });
}
