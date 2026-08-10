/** Follow-up-only Pi tools kept separate so every tool retains a narrow schema. */
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
function rpc(action: string, payload: Record<string, unknown>) {
  const result = spawnSync(process.env.ECOMIC_PYTHON || "python", ["-m", "agent_backend.rpc"], { cwd: root, input: `${JSON.stringify({ action, payload })}\n`, encoding: "utf8", windowsHide: true });
  if (result.error) throw result.error;
  const output = JSON.parse(result.stdout.trim().split(/\r?\n/).pop() || "{}");
  if (output.status === "ERROR") throw new Error(output.message || "ResearchRuntime failed");
  return output;
}
function register(pi: ExtensionAPI, name: string, description: string, parameters: any) {
  pi.registerTool(defineTool({ name: `ecomic_${name}`, label: `ECOMIC: ${name}`, description, parameters, async execute(_id, args) { const result = rpc(name, args as Record<string, unknown>); return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }], details: { action: name, result } }; } }));
}
export default function (pi: ExtensionAPI) {
  const session = { session_id: Type.String(), state_dir: Type.Optional(Type.String()) };
  register(pi, "audit_environment", "Re-run SemanticAuditor on the confirmed, researcher-visible environment.", Type.Object(session));
  register(pi, "revise_hypothesis", "Persist a follow-up hypothesis with an existing same-session parent hypothesis.", Type.Object({ ...session, parent_hypothesis_id: Type.String(), content: Type.String() }));
  register(pi, "compare_visible_evidence", "Compare only research-visible metadata across at least two same-session runs.", Type.Object({ ...session, run_ids: Type.Array(Type.String(), { minItems: 2 }) }));
}
