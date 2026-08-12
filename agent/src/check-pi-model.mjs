/**
 * Checks whether the pinned Pi Runtime supports a given provider+model.
 * Used by scientist_preflight() to verify MODEL_SUPPORTED_BY_CURRENT_PI.
 *
 * Usage: node check-pi-model.mjs <provider> <model_id> [base_url]
 * Output: JSONL on stdout: {"supported":true|false,"provider":"...","model_id":"..."}
 *
 * This script imports the REAL Pi runtime — it does NOT mock Pi Agent Core.
 */
import path from "node:path";
import { fileURLToPath } from "node:url";
import { builtinModels } from "../../vendor/pi/packages/ai/dist/providers/all.js";
import { createProvider } from "../../vendor/pi/packages/ai/dist/models.js";
import { envApiKeyAuth } from "../../vendor/pi/packages/ai/dist/auth/helpers.js";
import { openAICompletionsApi } from "../../vendor/pi/packages/ai/dist/api/openai-completions.lazy.js";

const providers = {
  openai: ["openai", "OPENAI_API_KEY"],
  anthropic: ["anthropic", "ANTHROPIC_API_KEY"],
  deepseek: ["deepseek", "DEEPSEEK_API_KEY"],
  google: ["google", "GEMINI_API_KEY"],
  openrouter: ["openrouter", "OPENROUTER_API_KEY"],
  moonshot: ["moonshotai-cn", "MOONSHOT_API_KEY"],
  qwen: ["qwen-token-plan-cn", "QWEN_TOKEN_PLAN_CN_API_KEY"],
  minimax: ["minimax-cn", "MINIMAX_API_KEY"],
  custom_openai_compatible: ["ecomic-custom", "ECOMIC_CUSTOM_API_KEY"],
};

function customProvider(modelId, baseUrl) {
  return createProvider({
    id: "ecomic-custom",
    name: "ECOMIC Custom OpenAI-Compatible",
    baseUrl,
    auth: { apiKey: envApiKeyAuth("ECOMIC Custom API key", ["ECOMIC_CUSTOM_API_KEY"]) },
    models: [{
      id: modelId, name: modelId, api: "openai-completions", provider: "ecomic-custom",
      baseUrl, reasoning: false, input: ["text"],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow: 128000, maxTokens: 8192,
    }],
    api: openAICompletionsApi(),
  });
}

const [provider, modelId, baseUrlArg] = process.argv.slice(2);

if (!provider || !modelId) {
  process.stdout.write(JSON.stringify({ supported: false, error: "provider and model_id required" }) + "\n");
  process.exit(1);
}

try {
  const info = providers[provider];
  if (!info) {
    process.stdout.write(JSON.stringify({ supported: false, provider, model_id: modelId, error: "unknown provider" }) + "\n");
    process.exit(0);
  }

  const models = builtinModels();
  const baseUrl = baseUrlArg?.trim() || undefined;

  if (provider === "custom_openai_compatible") {
    if (!baseUrl) {
      process.stdout.write(JSON.stringify({ supported: false, provider, model_id: modelId, error: "base_url required for custom provider" }) + "\n");
      process.exit(0);
    }
    models.setProvider(customProvider(modelId, baseUrl));
  }

  const found = models.getModel(info[0], modelId);
  process.stdout.write(JSON.stringify({ supported: !!found, provider, model_id: modelId }) + "\n");
} catch (error) {
  process.stdout.write(JSON.stringify({ supported: false, provider, model_id: modelId, error: error.message || "Pi model check failed" }) + "\n");
  process.exit(0);
}
