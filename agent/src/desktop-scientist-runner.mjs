/**
 * Desktop entry point for the real Pi Agent Core Scientist.
 * Credentials are inherited through the process environment only; stdout is
 * a safe JSONL event protocol for the Rust bridge and never echoes secrets.
 */
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Agent } from "../../vendor/pi/packages/agent/dist/index.js";
import { Type, streamSimple } from "../../vendor/pi/packages/ai/dist/compat.js";
import { envApiKeyAuth } from "../../vendor/pi/packages/ai/dist/auth/helpers.js";
import { createProvider } from "../../vendor/pi/packages/ai/dist/models.js";
import { openAICompletionsApi } from "../../vendor/pi/packages/ai/dist/api/openai-completions.lazy.js";
import { builtinModels } from "../../vendor/pi/packages/ai/dist/providers/all.js";
import { ECOMIC_SYSTEM_PROMPT } from "./system-prompt.ts";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const providerInfo = Object.freeze({
  openai: ["openai", "OPENAI_API_KEY"], anthropic: ["anthropic", "ANTHROPIC_API_KEY"],
  deepseek: ["deepseek", "DEEPSEEK_API_KEY"], google: ["google", "GEMINI_API_KEY"],
  openrouter: ["openrouter", "OPENROUTER_API_KEY"], moonshot: ["moonshotai-cn", "MOONSHOT_API_KEY"],
  qwen: ["qwen-token-plan-cn", "QWEN_TOKEN_PLAN_CN_API_KEY"], minimax: ["minimax-cn", "MINIMAX_API_KEY"],
  custom_openai_compatible: ["ecomic-custom", "ECOMIC_CUSTOM_API_KEY"],
});
function emit(value) { process.stdout.write(`${JSON.stringify(value)}\n`); }
function rpc(action, payload) {
  const result = spawnSync(process.env.ECOMIC_PYTHON || "python", ["-m", "agent_backend.rpc"], { cwd: root, input: `${JSON.stringify({ action, payload: { ...payload, state_dir: process.env.ECOMIC_STATE_DIR } })}\n`, encoding: "utf8", windowsHide: true });
  if (result.error) throw result.error;
  const output = JSON.parse(result.stdout.trim().split(/\r?\n/).pop() || "{}");
  if (output.status === "ERROR") throw new Error(output.message || "ECOMIC runtime failed");
  return output;
}
function customProvider(modelId, baseUrl) {
  return createProvider({ id: "ecomic-custom", name: "ECOMIC Custom OpenAI-Compatible", baseUrl, auth: { apiKey: envApiKeyAuth("ECOMIC Custom API key", ["ECOMIC_CUSTOM_API_KEY"]) }, models: [{ id: modelId, name: modelId, api: "openai-completions", provider: "ecomic-custom", baseUrl, reasoning: false, input: ["text"], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 128000, maxTokens: 4096 }], api: openAICompletionsApi() });
}
function modelForEnvironment() {
  const provider = process.env.ECOMIC_PROVIDER || ""; const modelId = process.env.ECOMIC_MODEL || ""; const baseUrl = process.env.ECOMIC_BASE_URL?.trim();
  const info = providerInfo[provider]; if (!info || !modelId || !process.env[info[1]]) throw new Error("模型配置或 Windows 凭据不可用");
  const models = builtinModels(); if (provider === "custom_openai_compatible") { if (!baseUrl) throw new Error("自定义 Provider 缺少 Base URL"); models.setProvider(customProvider(modelId, baseUrl)); }
  const found = models.getModel(info[0], modelId); if (!found) throw new Error("Pi 不支持当前 Model ID");
  return baseUrl && provider !== "custom_openai_compatible" ? { ...found, baseUrl } : found;
}
function tool(name, parameters) {
  return { name: `ecomic_${name}`, label: `ECOMIC: ${name}`, description: `Audited ECOMIC scientific tool: ${name}. Never access Oracle labels or provide evaluator metrics.`, parameters, executionMode: "sequential", execute: async (_id, args) => { emit({ type: "tool_start", tool: name }); const result = rpc(name, args); emit({ type: "tool_end", tool: name, status: "COMPLETED" }); return { content: [{ type: "text", text: JSON.stringify(result) }], details: { action: name } }; } };
}
const session = Type.Object({ session_id: Type.String(), state_dir: Type.Optional(Type.String()) });
function createDesktopScientist(model, apiKey, sessionId) {
  const tools = [
    tool("observe_state", session), tool("audit_environment", session), tool("resume_environment", session), tool("generate_report", session),
    tool("create_hypothesis", Type.Object({ ...session.properties, content: Type.String() })),
    tool("revise_hypothesis", Type.Object({ ...session.properties, parent_hypothesis_id: Type.String(), content: Type.String() })),
    tool("plan_experiment", Type.Object({ ...session.properties, hypothesis_id: Type.String(), policy: Type.String(), budget: Type.Number(), rounds: Type.Integer({ minimum: 1 }) })),
    tool("run_experiment", Type.Object({ ...session.properties, plan_id: Type.String(), policy: Type.String(), budget: Type.Number(), seed: Type.Integer(), rounds: Type.Integer({ minimum: 1 }) })),
    tool("compare_visible_evidence", Type.Object({ ...session.properties, run_ids: Type.Array(Type.String(), { minItems: 2 }) })),
    tool("lock_run_plan", Type.Object({ ...session.properties, run_id: Type.String() })), tool("finalize_evaluation", Type.Object({ ...session.properties, run_id: Type.String() })),
    tool("claim_guard", Type.Object({ ...session.properties, claim: Type.String(), evidence_run_ids: Type.Array(Type.String()), strength: Type.Optional(Type.String()) })),
  ];
  return new Agent({ initialState: { systemPrompt: `${ECOMIC_SYSTEM_PROMPT}\nUse only typed ECOMIC tools. Begin with observe_state and audit_environment. The DomainSpec has already been manually confirmed. Persist hypotheses, make plans, inspect evidence, revise only when evidence justifies it, and end honestly as INCONCLUSIVE when appropriate. Never access Oracle labels or submit final metrics.`, model, tools, thinkingLevel: "medium" }, streamFn: streamSimple, getApiKey: () => apiKey, sessionId: `desktop-${sessionId}`, toolExecution: "sequential", beforeToolCall: async ({ toolCall, args }) => (/oracle|hidden[._-]?label|shell|bash/i.test(toolCall.name) || (toolCall.name === "ecomic_finalize_evaluation" && "metrics" in args)) ? { block: true, reason: "Oracle, shell, and injected metrics are forbidden", terminate: true } : undefined });
}
async function main() {
  const sessionId = process.env.ECOMIC_SESSION_ID || ""; const question = process.env.ECOMIC_RESEARCH_QUESTION || ""; const provider = process.env.ECOMIC_PROVIDER || ""; const info = providerInfo[provider];
  if (!sessionId || !question.trim() || !info) throw new Error("缺少研究 Session、问题或模型配置");
  const agent = createDesktopScientist(modelForEnvironment(), process.env[info[1]], sessionId);
  agent.subscribe((event) => { if (event.type === "tool_execution_start") emit({ type: "agent_tool_execution", tool: event.toolName }); });
  emit({ type: "agent_started", session_id: sessionId });
  await agent.prompt(`Current ECOMIC session_id is ${sessionId}. Research question: ${question}.`);
  if (agent.state.errorMessage) throw new Error(agent.state.errorMessage);
  emit({ type: "agent_completed", session_id: sessionId });
}
main().catch((error) => { emit({ type: "agent_error", message: "Scientist Agent 运行失败，请检查模型连接或研究配置。" }); process.exitCode = 1; });
