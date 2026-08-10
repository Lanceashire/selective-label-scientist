/** Typed ECOMIC tools and secure model/API settings for Pi. */
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Key, matchesKey } from "@earendil-works/pi-tui";
import { PROVIDERS, checkConfiguration, loadNonSecretConfig, redactSecret, saveCredential, saveNonSecretConfig } from "./settings.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
function callRuntime(action: string, payload: Record<string, unknown>) {
  const result = spawnSync(process.env.ECOMIC_PYTHON || "python", ["-m", "agent_backend.rpc"], { cwd: root, input: `${JSON.stringify({ action, payload })}\n`, encoding: "utf8", windowsHide: true });
  if (result.error) throw result.error;
  const output = JSON.parse(result.stdout.trim().split(/\r?\n/).pop() || "{}");
  if (output.status === "ERROR") throw new Error(output.message || "ResearchRuntime 调用失败");
  return output;
}

async function secretInput(ctx: any, title: string) {
  return ctx.ui.custom<string | null>((tui: any, theme: any, _keyboard: any, done: any) => {
    let value = "";
    return {
      render: (width: number) => [theme.fg("accent", `◆ ${title}`), "", theme.fg("text", `  ${"*".repeat(value.length)}`), "", theme.fg("dim", "  Enter 确认 · Esc 取消（密钥不会回显或写入日志）"), theme.fg("accent", "─".repeat(Math.max(1, width - 1)))],
      handleInput: (data: string) => {
        if (matchesKey(data, Key.enter)) return done(value);
        if (matchesKey(data, Key.escape)) return done(null);
        if (matchesKey(data, Key.backspace)) { value = value.slice(0, -1); tui.requestRender(); return; }
        if (data.length === 1 && data >= " ") { value += data; tui.requestRender(); }
      },
      invalidate: () => {},
    };
  });
}

export default function (pi: ExtensionAPI) {
  const session = Type.Object({ session_id: Type.String(), state_dir: Type.Optional(Type.String()) });
  const register = (name: string, parameters: any) => pi.registerTool(defineTool({
    name: `ecomic_${name}`, label: `ECOMIC: ${name}`,
    description: `Audited ECOMIC scientific tool: ${name}. Oracle labels and final metrics are never agent supplied.`,
    parameters,
    async execute(_id, parameters) {
      const result = callRuntime(name, parameters as Record<string, unknown>);
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }], details: { action: name, result } };
    },
  }));
  register("load_dataset", Type.Object({ path: Type.String(), description: Type.Optional(Type.String()), state_dir: Type.Optional(Type.String()) }));
  register("confirm_decision_mapping", Type.Object({ ...session.properties, decision_column: Type.String(), observed_values: Type.Array(Type.String()), non_observed_values: Type.Array(Type.String()), target_column: Type.Optional(Type.String()), cost_column: Type.Optional(Type.String()), decision_time: Type.Optional(Type.String()), outcome_time: Type.Optional(Type.String()) }));
  register("confirm_observation_action", Type.Object({ ...session.properties, reversible: Type.Boolean(), simulatable: Type.Boolean(), description: Type.String() }));
  register("create_hypothesis", Type.Object({ ...session.properties, content: Type.String() }));
  register("plan_experiment", Type.Object({ ...session.properties, hypothesis_id: Type.String(), policy: Type.String(), budget: Type.Number(), rounds: Type.Integer({ minimum: 1 }) }));
  register("run_experiment", Type.Object({ ...session.properties, plan_id: Type.String(), policy: Type.String(), budget: Type.Number(), seed: Type.Integer(), rounds: Type.Integer({ minimum: 1 }) }));
  register("lock_run_plan", Type.Object({ ...session.properties, run_id: Type.String() }));
  register("finalize_evaluation", Type.Object({ ...session.properties, run_id: Type.String() }));
  register("observe_state", session);
  register("resume_environment", session);
  register("generate_report", session);
  register("claim_guard", Type.Object({ ...session.properties, claim: Type.String(), evidence_run_ids: Type.Array(Type.String()), strength: Type.Optional(Type.String()) }));

  pi.registerCommand("ecomic-settings", {
    description: "模型与 API 设置（密钥默认仅保存在本次 Pi 会话内）",
    handler: async (_args, ctx) => {
      const choices = Object.entries(PROVIDERS).map(([id, provider]) => `${id} · ${provider.label}`);
      const chosen = await ctx.ui.select("选择模型服务商", choices);
      if (!chosen) return;
      const provider = chosen.split(" · ")[0];
      const current = loadNonSecretConfig();
      const model = await ctx.ui.input("模型 ID", current.model || "例如 deepseek-chat");
      if (!model) return;
      const baseUrl = await ctx.ui.input("API Base URL（留空使用 Pi 默认值）", current.base_url || "");
      const key = await secretInput(ctx, `${PROVIDERS[provider].label} API Key`);
      if (key === null) return;
      const validation = checkConfiguration({ provider, model, base_url: baseUrl || null }, key);
      if (!validation.ok) { ctx.ui.notify(`配置未通过：${validation.message}`, "error"); return; }
      const saveLocally = await ctx.ui.confirm("保存凭据", `当前 Key：${redactSecret(key)}\n是否保存至 ~/.ecomic/credentials.env？选择“否”仅在本次会话内使用。`);
      saveNonSecretConfig({ provider, model, base_url: baseUrl || null });
      if (saveLocally) { saveCredential(provider, key); ctx.ui.notify("已保存至本机私有凭据文件；未写入项目、SQLite、报告或日志。", "info"); }
      else { process.env[PROVIDERS[provider].keyEnv] = key; ctx.ui.notify("已仅在当前 Pi 进程内配置 API Key。", "info"); }
      const modelInfo = ctx.modelRegistry.find(PROVIDERS[provider].piProvider, model);
      if (!modelInfo) ctx.ui.notify("Pi 当前模型目录中未找到该模型；可保存配置，但开始正式 Agent 前应重启 Pi 并检查模型 ID。", "warning");
      else ctx.ui.notify("配置检查通过。真实连接测试会发送最小请求，且可能消耗少量 Token；请在模型已选中后使用 Pi 的连接流程。", "info");
    },
  });
}
