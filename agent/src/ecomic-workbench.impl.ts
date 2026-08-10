/** Interactive ECOMIC research workbench. All mutations go through typed RPC. */
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const SESSION_KEY = Symbol.for("ecomic.active-session-id");
const currentSession = () => (globalThis as Record<symbol, string | undefined>)[SESSION_KEY];
const setSession = (value: string | undefined) => { (globalThis as Record<symbol, string | undefined>)[SESSION_KEY] = value; };
function rpc(action: string, payload: Record<string, unknown>) {
  const result = spawnSync(process.env.ECOMIC_PYTHON || "python", ["-m", "agent_backend.rpc"], { cwd: root, input: `${JSON.stringify({ action, payload })}\n`, encoding: "utf8", windowsHide: true });
  if (result.error) throw result.error;
  const output = JSON.parse(result.stdout.trim().split(/\r?\n/).pop() || "{}");
  if (output.status === "ERROR") throw new Error(output.message || "ResearchRuntime failed");
  return output;
}
function safeError(error: unknown) { return String((error as { message?: string })?.message || error || "Unknown error").replace(/(Bearer\s+)[^\s]+/gi, "$1[REDACTED]").replace(/(api[_-]?key|token)\s*[:=]\s*[^\s,;]+/gi, "$1=[REDACTED]"); }
async function ask(ctx: any, title: string, placeholder = "") { return (await ctx.ui.input(title, placeholder))?.trim(); }
function renderHome(ctx: any) {
  ctx.ui.setWidget("ecomic-home", ["ECOMIC | Cross-domain selective-label scientist | SQLite persistence | Oracle isolated", `Current session: ${currentSession() || "not started"}`, "/ecomic-new-research  import data and confirm semantics", "/ecomic-run  create a hypothesis and run an auditable policy", "/ecomic-final  lock the latest plan and evaluate internally", "/ecomic-history  restore a previous research session", "/ecomic-report  export the SQLite-grounded research report", "/ecomic-settings and /ecomic-test-connection  configure and verify a model"], { placement: "aboveEditor" });
}
export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (event, ctx) => { ctx.ui.setTitle("ECOMIC - Selective-Label Scientist"); ctx.ui.setStatus("ecomic", `Research workbench / ${event.reason === "new" ? "new session" : "restored"} / Oracle LOCKED`); renderHome(ctx); });
  pi.registerCommand("ecomic-home", { description: "Show the ECOMIC research workbench.", handler: async (_args, ctx) => renderHome(ctx) });
  pi.registerCommand("ecomic-new-research", {
    description: "Import CSV/Parquet and explicitly confirm selective-label semantics.",
    handler: async (_args, ctx) => {
      try {
        const file = await ask(ctx, "Dataset path", "Absolute CSV or Parquet path"); if (!file) return;
        const description = await ask(ctx, "Selection-label semantics", "What historical decision determines whether the outcome is observed?");
        const created: any = rpc("load_dataset", { path: file, description: description || "" }); setSession(created.session_id);
        const inferred = created.domain_spec || {};
        const decision = await ask(ctx, "Historical decision column", inferred.historical_decision?.column || "");
        const target = await ask(ctx, "Outcome/label column", inferred.outcome?.column || "");
        const cost = await ask(ctx, "Observation cost column (optional)", inferred.observation_cost?.column || "");
        const observed = await ask(ctx, "Decision values where outcome is observed", "comma-separated, e.g. yes,approved");
        const hidden = await ask(ctx, "Decision values where outcome is hidden", "comma-separated, e.g. no,rejected");
        const decisionTime = await ask(ctx, "Historical decision-time column (optional)", "");
        const outcomeTime = await ask(ctx, "Outcome-time column (optional)", "");
        if (!decision || !target || !observed || !hidden) { ctx.ui.notify("Session was saved safely, but the required mapping is incomplete. Restore it through /ecomic-history after collecting the field meanings.", "warning"); return; }
        rpc("confirm_decision_mapping", { session_id: currentSession(), decision_column: decision, target_column: target, cost_column: cost || undefined, observed_values: observed.split(",").map((x) => x.trim()).filter(Boolean), non_observed_values: hidden.split(",").map((x) => x.trim()).filter(Boolean), decision_time: decisionTime || undefined, outcome_time: outcomeTime || undefined });
        const reversible = await ctx.ui.confirm("Confirm observation action", "Is the intended observation/replay action reversible?");
        const simulatable = await ctx.ui.confirm("Confirm observation action", "Can it be safely simulated using this dataset?");
        const actionDescription = await ask(ctx, "Observation action description", "For example: offline replay of historical records; no live business action.");
        const approved: any = rpc("confirm_observation_action", { session_id: currentSession(), reversible, simulatable, description: actionDescription || "" });
        ctx.ui.setStatus("ecomic", `ECOMIC / Session ${String(currentSession()).slice(-8)} / ${approved.audit?.status || "mapped"}`);
        ctx.ui.notify(`Semantic audit: ${approved.audit?.status || "completed"}.`, approved.audit?.status === "BLOCKED" ? "error" : "info"); renderHome(ctx);
      } catch (error) { ctx.ui.notify(`Research initialization failed: ${safeError(error)}`, "error"); }
    },
  });
  pi.registerCommand("ecomic-run", { description: "Create a hypothesis, plan, and run an auditable dynamic selection policy.", handler: async (_args, ctx) => {
    try {
      const sessionId = currentSession(); if (!sessionId) { ctx.ui.notify("Create or restore a research session first.", "warning"); return; }
      const question = await ask(ctx, "Research hypothesis", "Example: uncertainty-first selection improves visible evidence under low budget."); if (!question) return;
      const policy = await ctx.ui.select("Policy", ["LRBE-Uncertainty", "Random", "CountOnly-MinCost"]); if (!policy) return;
      const budget = Number(await ask(ctx, "Budget", "30")); const rounds = Number(await ask(ctx, "Rounds", "3"));
      if (!(budget > 0) || !(rounds >= 1)) throw new Error("Budget must be positive and rounds must be at least one.");
      const hypothesis: any = rpc("create_hypothesis", { session_id: sessionId, content: question }); const plan: any = rpc("plan_experiment", { session_id: sessionId, hypothesis_id: hypothesis.hypothesis_id, policy, budget, rounds }); const run: any = rpc("run_experiment", { session_id: sessionId, plan_id: plan.plan_id, policy, budget, seed: 7, rounds });
      ctx.ui.setWidget("ecomic-workbench", [`Session: ${sessionId}`, `Policy: ${policy}`, `Run: ${run.run_id}`, `Rounds completed: ${run.observations?.length || 0}`, "Oracle: LOCKED until final evaluation"], { placement: "aboveEditor" }); ctx.ui.notify(`Experiment ${run.run_id} completed and is persisted in SQLite.`, "info");
    } catch (error) { ctx.ui.notify(`Experiment failed: ${safeError(error)}`, "error"); }
  } });
  pi.registerCommand("ecomic-final", { description: "Lock the most recent plan and run evaluator-owned final assessment.", handler: async (_args, ctx) => { try { const sessionId = currentSession(); if (!sessionId) throw new Error("No active session."); const snapshot: any = rpc("resume_environment", { session_id: sessionId }); if (!snapshot.run_id) throw new Error("No resumable experiment run exists."); rpc("lock_run_plan", { session_id: sessionId, run_id: snapshot.run_id }); const final: any = rpc("finalize_evaluation", { session_id: sessionId, run_id: snapshot.run_id }); ctx.ui.notify(`Final assessment: ${final.status}. Final metrics are evaluator-owned.`, "info"); } catch (error) { ctx.ui.notify(`Final assessment failed: ${safeError(error)}`, "error"); } } });
  pi.registerCommand("ecomic-report", { description: "Export a report generated from the SQLite source of truth.", handler: async (_args, ctx) => { try { const sessionId = currentSession(); if (!sessionId) throw new Error("No active session."); const report: any = rpc("generate_report", { session_id: sessionId }); ctx.ui.notify(`Report exported: ${report.final_report}`, "info"); } catch (error) { ctx.ui.notify(`Report export failed: ${safeError(error)}`, "error"); } } });
}
