/** Optional pi-ai model boundary. The deterministic backend never needs an API key. */
export type EcomicModelConfig = { provider: string; model?: string; configured: boolean };

export function readModelConfig(env: NodeJS.ProcessEnv = process.env): EcomicModelConfig {
  const provider = env.ECOMIC_LLM_PROVIDER || "mock";
  const model = env.ECOMIC_LLM_MODEL || undefined;
  const keyByProvider: Record<string, string> = {
    openai: "OPENAI_API_KEY",
    anthropic: "ANTHROPIC_API_KEY",
    deepseek: "DEEPSEEK_API_KEY",
    google: "GOOGLE_API_KEY",
  };
  return { provider, model, configured: provider === "mock" || Boolean(env[keyByProvider[provider]]) };
}

/**
 * The real Pi extension loads @earendil-works/pi-ai through Pi's provider
 * registry when installed. Keeping this function lazy means schema audit and
 * mock runs remain usable without network credentials.
 */
export async function loadPiAi(): Promise<unknown> {
  return import("@earendil-works/pi-ai/providers/all");
}

