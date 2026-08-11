/**
 * One-shot real Provider probe. It runs through Pi's Models/Provider APIs and
 * accepts a credential only from its inherited process environment. stdout is
 * restricted to the redacted JSON contract consumed by the Rust bridge.
 */
import { Type } from "../../vendor/pi/packages/ai/dist/index.js";
import { envApiKeyAuth } from "../../vendor/pi/packages/ai/dist/auth/helpers.js";
import { createProvider } from "../../vendor/pi/packages/ai/dist/models.js";
import { openAICompletionsApi } from "../../vendor/pi/packages/ai/dist/api/openai-completions.lazy.js";
import { builtinModels } from "../../vendor/pi/packages/ai/dist/providers/all.js";
import { failedConnectionResult, successfulConnectionResult } from "./connection-test-contract.mjs";

const PROVIDERS = Object.freeze({
  openai: { piProvider: "openai", keyEnv: "OPENAI_API_KEY" },
  anthropic: { piProvider: "anthropic", keyEnv: "ANTHROPIC_API_KEY" },
  deepseek: { piProvider: "deepseek", keyEnv: "DEEPSEEK_API_KEY" },
  google: { piProvider: "google", keyEnv: "GEMINI_API_KEY" },
  openrouter: { piProvider: "openrouter", keyEnv: "OPENROUTER_API_KEY" },
  moonshot: { piProvider: "moonshotai-cn", keyEnv: "MOONSHOT_API_KEY" },
  qwen: { piProvider: "qwen-token-plan-cn", keyEnv: "QWEN_TOKEN_PLAN_CN_API_KEY" },
  minimax: { piProvider: "minimax-cn", keyEnv: "MINIMAX_API_KEY" },
  custom_openai_compatible: { piProvider: "ecomic-custom", keyEnv: "ECOMIC_CUSTOM_API_KEY" },
});

function customProvider(modelId, baseUrl) {
  return createProvider({
    id: "ecomic-custom",
    name: "ECOMIC Custom OpenAI-Compatible",
    baseUrl,
    auth: { apiKey: envApiKeyAuth("ECOMIC Custom API key", ["ECOMIC_CUSTOM_API_KEY"]) },
    models: [{ id: modelId, name: modelId, api: "openai-completions", provider: "ecomic-custom", baseUrl, reasoning: false, input: ["text"], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 128000, maxTokens: 64 }],
    api: openAICompletionsApi(),
  });
}

async function probe() {
  const providerId = process.env.ECOMIC_PROVIDER ?? "";
  const modelId = process.env.ECOMIC_MODEL ?? "";
  const baseUrl = process.env.ECOMIC_BASE_URL?.trim() || undefined;
  const definition = PROVIDERS[providerId];
  if (!definition || !modelId || !process.env[definition.keyEnv]) return failedConnectionResult(new Error("invalid response"));

  const models = builtinModels();
  if (providerId === "custom_openai_compatible") {
    if (!baseUrl) return failedConnectionResult(new Error("not found"));
    models.setProvider(customProvider(modelId, baseUrl));
  }
  const found = models.getModel(definition.piProvider, modelId);
  if (!found) return failedConnectionResult(new Error("unknown model"));
  const model = baseUrl && providerId !== "custom_openai_compatible" ? { ...found, baseUrl } : found;
  const response = await models.complete(model, {
    messages: [{ role: "user", content: [{ type: "text", text: "Call ecomic_connection_probe exactly once with ok=true. Do not add prose." }], timestamp: Date.now() }],
    tools: [{ name: "ecomic_connection_probe", description: "Harmless ECOMIC connection probe.", parameters: Type.Object({ ok: Type.Boolean() }) }],
  }, { maxTokens: 32 });
  const verified = response.stopReason === "toolUse" && response.content.some((part) => part.type === "toolCall" && part.name === "ecomic_connection_probe");
  return successfulConnectionResult(verified);
}

probe().then((result) => process.stdout.write(`${JSON.stringify(result)}\n`)).catch((error) => process.stdout.write(`${JSON.stringify(failedConnectionResult(error))}\n`));
