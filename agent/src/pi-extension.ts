import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Type, StringEnum } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const actions = [
  "load_dataset", "inspect_schema", "infer_domain_spec", "audit_selective_labels",
  "confirm_field_mapping", "observe_state", "diagnose_selection", "define_budget",
  "list_applicable_policies", "plan_experiment", "run_experiment", "compare_visible_evidence",
  "revise_hypothesis", "lock_research_plan", "finalize_evaluation", "claim_guard", "generate_report",
] as const;

const parameters = Type.Object({
  data_path: Type.Optional(Type.String({ description: "CSV/Parquet 数据集路径" })),
  description: Type.Optional(Type.String({ description: "标签可见性和数据来源说明" })),
  action: Type.Optional(StringEnum(actions)),
  budget: Type.Optional(Type.Number()),
  claim: Type.Optional(Type.String()),
});

function callBackend(action: string, params: Record<string, unknown>) {
  const payload = { action, payload: { ...params, data_path: params.data_path ? path.resolve(String(params.data_path)) : undefined } };
  const result = spawnSync(process.env.ECOMIC_PYTHON || "python", ["-m", "agent_backend.rpc"], {
    cwd: root,
    input: `${JSON.stringify(payload)}\n`,
    encoding: "utf8",
    windowsHide: true,
  });
  if (result.error) throw result.error;
  const line = result.stdout.trim().split(/\r?\n/).pop() || "{}";
  return JSON.parse(line);
}

const tool = defineTool({
  name: "ecomic_research",
  label: "ECOMIC 科研工具",
  description: `运行 ECOMIC 白名单科研动作：${actions.join(", ")}。不开放任意 shell，不向研究阶段暴露 outer-test。`,
  parameters,
  async execute(_id, params) {
    const action = params.action || "run_experiment";
    const result = callBackend(action, params as Record<string, unknown>);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }], details: { action, result } };
  },
});

export default function (pi: ExtensionAPI) {
  pi.registerTool(tool);
  pi.registerCommand("ecomic", {
    description: "显示 ECOMIC 跨领域科研工具说明",
    handler: async (_args, ctx) => ctx.ui.notify("ECOMIC 工具已启用：使用 ecomic_research 调用白名单科研动作。", "info"),
  });
}

