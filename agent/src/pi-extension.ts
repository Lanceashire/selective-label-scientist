import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const toolNames = ["load_dataset", "inspect_schema", "infer_domain_spec", "audit_selective_labels", "confirm_field_mapping", "observe_state", "diagnose_selection", "define_budget", "list_applicable_policies", "plan_experiment", "run_experiment", "compare_visible_evidence", "revise_hypothesis", "lock_research_plan", "finalize_evaluation", "claim_guard", "generate_report"] as const;
const parameters = Type.Object({ data_path: Type.Optional(Type.String()), run_dir: Type.Optional(Type.String()), description: Type.Optional(Type.String()), budget: Type.Optional(Type.Number()), claim: Type.Optional(Type.String()), overrides: Type.Optional(Type.Object({})) });

function callBackend(action: string, params: Record<string, unknown>) {
  const payload = { action, payload: { ...params, data_path: params.data_path ? path.resolve(String(params.data_path)) : undefined } };
  const result = spawnSync(process.env.ECOMIC_PYTHON || "python", ["-m", "agent_backend.rpc"], { cwd: root, input: `${JSON.stringify(payload)}\n`, encoding: "utf8", windowsHide: true });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(result.stderr || `backend failed: ${result.status}`);
  return JSON.parse(result.stdout.trim().split(/\r?\n/).pop() || "{}");
}

export default function (pi: ExtensionAPI) {
  for (const name of toolNames) {
    pi.registerTool(defineTool({
      name: `ecomic_${name}`,
      label: `ECOMIC: ${name}`,
      description: `ECOMIC allow-listed research tool: ${name}. It cannot execute arbitrary shell commands or expose oracle labels during research.`,
      parameters,
      async execute(_id, params) {
        const result = callBackend(name, params as Record<string, unknown>);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }], details: { action: name, result } };
      },
    }));
  }
  pi.registerCommand("ecomic", { description: "Show ECOMIC selective-label scientist help", handler: async (_args, ctx) => ctx.ui.notify("ECOMIC tools are registered separately and are audit logged.", "info") });
}
