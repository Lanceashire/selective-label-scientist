// Compatibility fixture retained for consumers that import the old settings test helper.
// Active security assertions live in settings_secure.test.mjs.
export { checkConfiguration, configPath, credentialsPath, redactSecret, redactText, saveCredential, saveNonSecretConfig } from "../agent/src/settings.mjs";
