import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
function callRuntime(action: string, params: Record<string, unknown>) {
  const result = spawnSync(process.env.ECOMIC_PYTHON || "python", ["-m", "agent_backend.rpc"], { cwd: root, input: `${JSON.stringify({ action, payload: params })}\n`, encoding: "utf8", windowsHide: true });
  if (result.error) throw result.error;
  return JSON.parse(result.stdout.trim().split(/\r?\n/).pop() || "{}");
}
const session = Type.Object({ session_id: Type.String(), state_dir: Type.Optional(Type.String()) });
export default function(pi: ExtensionAPI) {
  const register = (name: string, parameters: any) => pi.registerTool(defineTool({ name: `ecomic_${name}`, label: `ECOMIC: ${name}`, description: "ECOMIC typed research tool. Oracle labels and final metrics are never accepted from the agent.", parameters, async execute(_id, params) { const result = callRuntime(name, params as Record<string, unknown>); return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }], details: { action: name, result } }; } }));
  register("load_dataset", Type.Object({ path: Type.String(), description: Type.Optional(Type.String()), state_dir: Type.Optional(Type.String()) }));
  register("confirm_decision_mapping", Type.Object({ ...session.properties, decision_column: Type.String(), observed_values: Type.Array(Type.String()), non_observed_values: Type.Array(Type.String()), target_column: Type.Optional(Type.String()), cost_column: Type.Optional(Type.String()), decision_time: Type.Optional(Type.String()), outcome_time: Type.Optional(Type.String()), observation_reversible: Type.Boolean(), observation_simulatable: Type.Boolean() }));
  register("create_hypothesis", Type.Object({ ...session.properties, content: Type.String() }));
  register("plan_experiment", Type.Object({ ...session.properties, hypothesis_id: Type.String(), policy: Type.String(), budget: Type.Number(), rounds: Type.Integer({ minimum: 1 }) }));
  register("run_experiment", Type.Object({ ...session.properties, plan_id: Type.String(), policy: Type.String(), budget: Type.Number(), seed: Type.Integer(), rounds: Type.Integer({ minimum: 1 }) }));
  register("lock_research_plan", Type.Object({ ...session.properties, plan_id: Type.String() }));
  // Deliberately only these two fields: no metrics field exists in this schema.
  register("finalize_evaluation", Type.Object({ ...session.properties, run_id: Type.String() }));
  register("observe_state", session);
}
