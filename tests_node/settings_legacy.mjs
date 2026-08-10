import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { checkConfiguration, configPath, credentialsPath, redactSecret, redactText, saveCredential, saveNonSecretConfig } from "../agent/src/settings.mjs";

test("credentials stay outside repository and are masked", () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "ecomic-settings-"));
  saveNonSecretConfig({ provider: "deepseek", model: "deepseek-chat", base_url: null }, home);
  saveCredential("deepseek", "sk-abcdefghijklmnopqrstuvwxyz23af", home);
  assert.equal(JSON.parse(fs.readFileSync(configPath(home), "utf8")).provider, "deepseek");
  assert.match(fs.readFileSync(credentialsPath(home), "utf8"), /DEEPSEEK_API_KEY=/);
  assert.equal(redactSecret("sk-abcdefghijklmnopqrstuvwxyz23af"), "sk-****23af");
  assert.equal(redactText("Authorization: Bearer super-secret"), "Authorization: [REDACTED] super-secret");
  assert.equal(checkConfiguration({ provider: "deepseek", model: "deepseek-chat" }, "key").ok, true);
  fs.rmSync(home, { recursive: true, force: true });
});
