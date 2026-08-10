/** Persisted provider bridge, explicit connection probe, and gated Agent Core entry. */
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { Type, type UserMessage } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { createScientistAgent } from "./scientist-agent.ts";
import { getActiveSession } from "./ecomic-workbench.ts";
import { PROVIDERS, hydrateCredentialToProcess, loadNonSecretConfig, redactText, saveNonSecretConfig } from "./settings.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
function runtimeCall(action: string, payload: Record<string, unknown>): Promise<unknown> {
  const result = spawnSync(process.env.ECOMIC_PYTHON || "python", ["-m", "agent_backend.rpc"], { cwd: root, input: `${JSON.stringify({ action, payload })}\n`, encoding: "utf8", windowsHide: true });
  if (result.error) return Promise.reject(result.error);
  try {
    const output = JSON.parse(result.stdout.trim().split(/\r?\n/).pop() || "{}");
    if (output.status === "ERROR") throw new Error(output.message || "ResearchRuntime failed");
    return Promise.resolve(output);
  } catch (error) { return Promise.reject(error); }
}
function configurePiProvider(pi: ExtensionAPI, config: ReturnType<typeof loadNonSecretConfig>): void {
  const provider = config.provider ? PROVIDERS[config.provider] : undefined;
  if (!provider || !config.base_url) return;
  if (config.provider === "custom_openai_compatible") {
    if (!config.model) return;
    pi.registerProvider(provider.piProvider, {
      name: "ECOMIC Custom OpenAI-Compatible", baseUrl: config.base_url, apiKey: "$ECOMIC_CUSTOM_API_KEY", api: "openai-completions", authHeader: true,
      models: [{ id: config.model, name: config.model, reasoning: false, input: ["text"], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 128000, maxTokens: 4096 }],
    });
    return;
  }
  pi.registerProvider(provider.piProvider, { baseUrl: config.base_url });
}
function connectionError(error: unknown): string {
  const message = redactText(error instanceof Error ? error.message : String(error));
  if (/401|403/.test(message)) return "Authentication failed: the API key is invalid, expired, or lacks model permission.";
  if (/404/.test(message)) return "The configured model or API Base URL was not found.";
  if (/429/.test(message)) return "The provider rate limit or account quota was reached.";
  if (/timeout|timed out|ETIMEDOUT/i.test(message)) return "Network connection timed out.";
  return `Connection failed: ${message}`;
}

export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (_event, ctx) => {
    const config = loadNonSecretConfig();
    if (config.provider) hydrateCredentialToProcess(config.provider);
    configurePiProvider(pi, config);
    if (config.provider && config.model) {
      ctx.ui.setStatus("ecomic-model", `${PROVIDERS[config.provider].label} / ${config.model} / ${config.tool_calling_verified ? "tool calling verified" : "not verified"}`);
    }
  });
  pi.registerCommand("ecomic-test-connection", {
    description: "Run one minimal real Pi connection and tool-calling probe (may consume a few tokens).",
    handler: async (_args, ctx) => {
      const config = loadNonSecretConfig();
      if (!config.provider || !config.model) { ctx.ui.notify("Configure Provider, Model ID, and API Key first with /ecomic-settings.", "warning"); return; }
      const provider = PROVIDERS[config.provider];
      const key = hydrateCredentialToProcess(config.provider);
      if (!key) { ctx.ui.notify("No API Key is available. Enter it in /ecomic-settings or save it in the local private credential file.", "warning"); return; }
      configurePiProvider(pi, config);
      const model = ctx.modelRegistry.find(provider.piProvider, config.model);
      if (!model) { ctx.ui.notify("The model is absent from the active Pi registry. Check Provider/Model ID and restart ECOMIC if needed.", "error"); return; }
      if (!await ctx.ui.confirm("Test live connection", "This sends one minimal tool-calling probe through Pi and may consume a few API tokens. Continue?")) return;
      const message: UserMessage = { role: "user", content: [{ type: "text", text: "Call ecomic_connection_probe exactly once with ok=true. Do not add prose." }], timestamp: Date.now() };
      try {
        const response = await ctx.modelRegistry.complete(model, { messages: [message], tools: [{ name: "ecomic_connection_probe", description: "Harmless ECOMIC connection probe.", parameters: Type.Object({ ok: Type.Boolean() }) }] }, { maxTokens: 32 });
        const toolVerified = response.stopReason === "toolUse" && response.content.some((part) => part.type === "toolCall" && part.name === "ecomic_connection_probe");
        saveNonSecretConfig({ ...config, tool_calling_verified: toolVerified, last_connection_test: new Date().toISOString() });
        ctx.ui.setStatus("ecomic-model", `${provider.label} / ${config.model} / ${toolVerified ? "tool calling verified" : "tool calling not verified"}`);
        ctx.ui.notify(toolVerified ? "Connection and tool calling were verified. You can now run /ecomic-scientist." : "Connection returned, but the model did not make the required tool call. Scientist Agent remains blocked.", toolVerified ? "info" : "warning");
      } catch (error) {
        saveNonSecretConfig({ ...config, tool_calling_verified: false, last_connection_test: new Date().toISOString() });
        ctx.ui.notify(connectionError(error), "error");
      }
    },
  });
  pi.registerCommand("ecomic-scientist", {
    description: "Run the formally gated Pi Agent Core scientist on the current ECOMIC session.",
    handler: async (_args, ctx) => {
      const sessionId = getActiveSession();
      const config = loadNonSecretConfig();
      if (!sessionId) { ctx.ui.notify("Create a research session or restore one with /ecomic-history first.", "warning"); return; }
      if (!config.provider || !config.model || !config.tool_calling_verified) { ctx.ui.notify("Run /ecomic-settings and the verified /ecomic-test-connection first.", "warning"); return; }
      const key = hydrateCredentialToProcess(config.provider);
      const provider = PROVIDERS[config.provider];
      configurePiProvider(pi, config);
      const model = ctx.modelRegistry.find(provider.piProvider, config.model);
      if (!key || !model) { ctx.ui.notify("The current model or credential is unavailable. Recheck API settings.", "error"); return; }
      const question = await ctx.ui.input("Research question for Scientist Agent", "Example: compare LRBE-Uncertainty with CountOnly-MinCost under a low budget.");
      if (!question?.trim()) return;
      const agent = createScientistAgent(model, key, runtimeCall, `ecomic-${sessionId}`);
      agent.subscribe((event) => {
        if (event.type === "tool_execution_start") ctx.ui.setStatus("ecomic-agent", `Scientist Agent is calling ${event.toolName}`);
        if (event.type === "agent_end") ctx.ui.setStatus("ecomic-agent", "Scientist Agent finished; results are persisted in SQLite.");
      });
      try {
        await agent.prompt(`Current ECOMIC session_id is ${sessionId}. ${question.trim()} You must use only ECOMIC typed tools, begin with observe_state, and stop with an honest conclusion when evidence is insufficient.`);
        if (agent.state.errorMessage) throw new Error(agent.state.errorMessage);
        ctx.ui.notify("Scientist Agent completed this typed-tool cycle. Use /ecomic-report for the SQLite-backed research report.", "info");
      } catch (error) { ctx.ui.notify(connectionError(error), "error"); }
    },
  });
}
