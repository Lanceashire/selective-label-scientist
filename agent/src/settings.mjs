import fs from "node:fs";
import os from "node:os";
import path from "node:path";

// These ids and environment variables are taken from the bundled Pi provider registry.
// Tool support is model-dependent where Pi's catalog cannot guarantee it for every model.
export const PROVIDERS = Object.freeze({
  openai: { label: "OpenAI", piProvider: "openai", keyEnv: "OPENAI_API_KEY", toolCalling: "model-dependent" },
  anthropic: { label: "Anthropic", piProvider: "anthropic", keyEnv: "ANTHROPIC_API_KEY", toolCalling: "model-dependent" },
  deepseek: { label: "DeepSeek", piProvider: "deepseek", keyEnv: "DEEPSEEK_API_KEY", toolCalling: "model-dependent" },
  google: { label: "Google Gemini", piProvider: "google", keyEnv: "GOOGLE_API_KEY", toolCalling: "model-dependent" },
  openrouter: { label: "OpenRouter", piProvider: "openrouter", keyEnv: "OPENROUTER_API_KEY", toolCalling: "model-dependent" },
  moonshot: { label: "Moonshot（Pi moonshotai-cn）", piProvider: "moonshotai-cn", keyEnv: "MOONSHOT_API_KEY", toolCalling: "model-dependent" },
  qwen: { label: "Qwen（Pi qwen-token-plan-cn）", piProvider: "qwen-token-plan-cn", keyEnv: "QWEN_TOKEN_PLAN_CN_API_KEY", toolCalling: "model-dependent" },
  minimax: { label: "MiniMax（Pi minimax-cn）", piProvider: "minimax-cn", keyEnv: "MINIMAX_CN_API_KEY", toolCalling: "model-dependent" },
  custom_openai_compatible: { label: "自定义 OpenAI-Compatible", piProvider: "ecomic-custom", keyEnv: "ECOMIC_CUSTOM_API_KEY", toolCalling: "unverified" },
});

export const ecomicHome = (home = os.homedir()) => path.join(home, ".ecomic");
export const configPath = (home) => path.join(ecomicHome(home), "config.json");
export const credentialsPath = (home) => path.join(ecomicHome(home), "credentials.env");

function ensurePrivateDirectory(home) { fs.mkdirSync(ecomicHome(home), { recursive: true, mode: 0o700 }); }

export function redactSecret(value) {
  const text = String(value ?? "");
  if (!text) return "未配置";
  return text.length <= 6 ? "******" : `${text.slice(0, 3)}****${text.slice(-4)}`;
}

export function redactText(value) {
  return String(value ?? "")
    .replace(/(authorization\s*:\s*bearer\s+)[^\s,;]+/gi, "$1[REDACTED]")
    .replace(/(\bbearer\s+)[^\s,;]+/gi, "$1[REDACTED]")
    .replace(/((?:api[_-]?key|token|secret)\s*[:=]\s*)[^\s,;]+/gi, "$1[REDACTED]");
}

export function loadNonSecretConfig(home) {
  try { return JSON.parse(fs.readFileSync(configPath(home), "utf8")); }
  catch { return { provider: null, model: null, base_url: null, language: "zh-CN", thinking_level: "normal" }; }
}

export function saveNonSecretConfig(config, home) {
  ensurePrivateDirectory(home);
  const safe = { provider: config.provider || null, model: config.model || null, base_url: config.base_url || null, language: config.language || "zh-CN", thinking_level: config.thinking_level || "normal" };
  fs.writeFileSync(configPath(home), `${JSON.stringify(safe, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  return safe;
}

export function saveCredential(provider, apiKey, home) {
  const definition = PROVIDERS[provider];
  if (!definition) throw new Error("不支持的 Provider");
  if (!apiKey || /\r|\n/.test(apiKey)) throw new Error("API Key 不能为空且不能包含换行");
  ensurePrivateDirectory(home);
  fs.writeFileSync(credentialsPath(home), `${definition.keyEnv}=${apiKey}\n`, { encoding: "utf8", mode: 0o600 });
  try { fs.chmodSync(credentialsPath(home), 0o600); } catch { /* Windows has different ACL semantics. */ }
  return { provider, masked_key: redactSecret(apiKey), stored: "local-private-file" };
}

export function clearCredential(home) {
  try { fs.rmSync(credentialsPath(home)); return true; }
  catch { return false; }
}

export function checkConfiguration(config, apiKey) {
  const provider = PROVIDERS[config.provider];
  if (!provider) return { ok: false, message: "当前 Provider 不在 ECOMIC 已声明的 Pi 支持范围内" };
  if (config.base_url && !/^https?:\/\//i.test(config.base_url)) return { ok: false, message: "API Base URL 必须以 http:// 或 https:// 开头" };
  if (config.provider === "custom_openai_compatible" && !config.base_url) return { ok: false, message: "自定义 OpenAI-Compatible Provider 必须提供 API Base URL" };
  if (!apiKey) return { ok: false, message: "尚未输入 API Key" };
  if (!config.model) return { ok: false, message: "尚未填写 Model ID" };
  if (provider.toolCalling === "unverified") return { ok: false, message: "该自定义 Provider 尚未通过 Pi provider extension 验证，因此不能启动正式 Scientist Agent" };
  return { ok: true, message: "配置格式有效；真实连接测试会通过 Pi ModelRegistry 发起最小请求，可能消耗少量 Token。", toolCalling: "model-dependent" };
}
