import fs from "node:fs";
import os from "node:os";
import path from "node:path";

/** Provider ids and credential names match Pi's built-in provider registry. */
export const PROVIDERS = Object.freeze({
  openai: { label: "OpenAI", piProvider: "openai", keyEnv: "OPENAI_API_KEY", toolCalling: "catalog" },
  anthropic: { label: "Anthropic", piProvider: "anthropic", keyEnv: "ANTHROPIC_API_KEY", toolCalling: "catalog" },
  deepseek: { label: "DeepSeek", piProvider: "deepseek", keyEnv: "DEEPSEEK_API_KEY", toolCalling: "catalog" },
  google: { label: "Google Gemini", piProvider: "google", keyEnv: "GEMINI_API_KEY", toolCalling: "catalog" },
  openrouter: { label: "OpenRouter", piProvider: "openrouter", keyEnv: "OPENROUTER_API_KEY", toolCalling: "catalog" },
  moonshot: { label: "Moonshot", piProvider: "moonshotai-cn", keyEnv: "MOONSHOT_API_KEY", toolCalling: "catalog" },
  qwen: { label: "Qwen", piProvider: "qwen-token-plan-cn", keyEnv: "QWEN_TOKEN_PLAN_CN_API_KEY", toolCalling: "catalog" },
  minimax: { label: "MiniMax", piProvider: "minimax-cn", keyEnv: "MINIMAX_API_KEY", toolCalling: "catalog" },
  custom_openai_compatible: { label: "Custom OpenAI-Compatible", piProvider: "ecomic-custom", keyEnv: "ECOMIC_CUSTOM_API_KEY", toolCalling: "connection-test-required" },
});

export const ecomicHome = (home = os.homedir()) => path.join(home, ".ecomic");
export const configPath = (home) => path.join(ecomicHome(home), "config.json");
export const credentialsPath = (home) => path.join(ecomicHome(home), "credentials.env");

function ensurePrivateDirectory(home) { fs.mkdirSync(ecomicHome(home), { recursive: true, mode: 0o700 }); }
function readCredentials(home) {
  try {
    return Object.fromEntries(fs.readFileSync(credentialsPath(home), "utf8").split(/\r?\n/).flatMap((line) => {
      const separator = line.indexOf("=");
      if (separator <= 0) return [];
      const name = line.slice(0, separator).trim();
      const value = line.slice(separator + 1).trim();
      return /^[A-Z][A-Z0-9_]*$/.test(name) && value ? [[name, value]] : [];
    }));
  } catch { return {}; }
}

export function redactSecret(value) {
  const text = String(value ?? "");
  return !text ? "not configured" : text.length <= 6 ? "******" : `${text.slice(0, 3)}****${text.slice(-4)}`;
}
export function redactText(value) {
  return String(value ?? "")
    .replace(/(authorization\s*:\s*bearer\s+)[^\s,;]+/gi, "$1[REDACTED]")
    .replace(/(\bbearer\s+)[^\s,;]+/gi, "$1[REDACTED]")
    .replace(/((?:api[_-]?key|token|secret)\s*[:=]\s*)[^\s,;]+/gi, "$1[REDACTED]");
}
export function loadNonSecretConfig(home) {
  try {
    const value = JSON.parse(fs.readFileSync(configPath(home), "utf8"));
    return { provider: value.provider || null, model: value.model || null, base_url: value.base_url || null, language: value.language || "zh-CN", thinking_level: value.thinking_level || "normal", tool_calling_verified: value.tool_calling_verified === true, last_connection_test: value.last_connection_test || null };
  } catch { return { provider: null, model: null, base_url: null, language: "zh-CN", thinking_level: "normal", tool_calling_verified: false, last_connection_test: null }; }
}
export function saveNonSecretConfig(config, home) {
  ensurePrivateDirectory(home);
  const safe = { provider: config.provider || null, model: config.model || null, base_url: config.base_url || null, language: config.language || "zh-CN", thinking_level: config.thinking_level || "normal", tool_calling_verified: config.tool_calling_verified === true, last_connection_test: config.last_connection_test || null };
  fs.writeFileSync(configPath(home), `${JSON.stringify(safe, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  try { fs.chmodSync(configPath(home), 0o600); } catch { /* Windows ACLs differ. */ }
  return safe;
}
export function loadCredential(provider, home) { const definition = PROVIDERS[provider]; return definition ? readCredentials(home)[definition.keyEnv] : undefined; }
export function hydrateCredentialToProcess(provider, home) {
  const definition = PROVIDERS[provider];
  const key = loadCredential(provider, home);
  if (definition && key && !process.env[definition.keyEnv]) process.env[definition.keyEnv] = key;
  return key;
}
export function saveCredential(provider, apiKey, home) {
  const definition = PROVIDERS[provider];
  if (!definition) throw new Error("Unsupported provider");
  if (!apiKey || /\r|\n/.test(apiKey)) throw new Error("API Key must be non-empty and single-line");
  ensurePrivateDirectory(home);
  const credentials = readCredentials(home);
  credentials[definition.keyEnv] = apiKey;
  fs.writeFileSync(credentialsPath(home), `${Object.entries(credentials).sort(([a], [b]) => a.localeCompare(b)).map(([name, value]) => `${name}=${value}`).join("\n")}\n`, { encoding: "utf8", mode: 0o600 });
  try { fs.chmodSync(credentialsPath(home), 0o600); } catch { /* Windows ACLs differ. */ }
  return { provider, masked_key: redactSecret(apiKey), stored: "local-private-file" };
}
export function clearCredential(provider, home) {
  const definition = PROVIDERS[provider];
  if (!definition) return false;
  const credentials = readCredentials(home);
  if (!credentials[definition.keyEnv]) return false;
  delete credentials[definition.keyEnv];
  if (Object.keys(credentials).length) fs.writeFileSync(credentialsPath(home), `${Object.entries(credentials).sort(([a], [b]) => a.localeCompare(b)).map(([name, value]) => `${name}=${value}`).join("\n")}\n`, { encoding: "utf8", mode: 0o600 });
  else fs.rmSync(credentialsPath(home), { force: true });
  return true;
}
export function checkConfiguration(config, apiKey) {
  const provider = PROVIDERS[config.provider];
  if (!provider) return { ok: false, message: "Provider is not in ECOMIC's declared Pi support list." };
  if (config.base_url && !/^https?:\/\//i.test(config.base_url)) return { ok: false, message: "API Base URL must start with http:// or https://." };
  if (config.provider === "custom_openai_compatible" && !config.base_url) return { ok: false, message: "Custom OpenAI-compatible provider requires an API Base URL." };
  if (!apiKey) return { ok: false, message: "API Key is required." };
  if (!config.model) return { ok: false, message: "Model ID is required." };
  return { ok: true, message: "Configuration format is valid. Run the explicit connection test before starting Scientist Agent.", toolCalling: provider.toolCalling };
}
