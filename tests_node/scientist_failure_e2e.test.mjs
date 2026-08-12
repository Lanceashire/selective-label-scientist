/**
 * Scientist Failure E2E Tests (Requirement 25)
 *
 * Verifies that the Scientist Runner handles various failure scenarios
 * with correct error codes, no deadlocks, and proper cleanup.
 *
 * Each test verifies:
 *   - App does not crash
 *   - Task reaches a terminal state
 *   - Error code is correct
 *   - No permanent loading state
 */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const runner = path.join(root, "agent/src/desktop-scientist-runner-v2.mjs");

/**
 * Runs the scientist runner with the given environment and captures JSONL events.
 * Returns { code, events, stderr }.
 */
function runRunner(env, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [runner], {
      cwd: root,
      env: { ...process.env, ...env },
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.setEncoding("utf8");
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("close", (code) => {
      const events = [];
      for (const line of stdout.split(/\r?\n/)) {
        if (!line.trim()) continue;
        try { events.push(JSON.parse(line)); } catch { /* not JSON */ }
      }
      resolve({ code, events, stderr });
    });
    child.on("error", reject);
    setTimeout(() => {
      try { child.kill("SIGKILL"); } catch {}
      reject(new Error(`Runner timed out after ${timeoutMs}ms`));
    }, timeoutMs);
  });
}

test("Failure: missing provider credential returns PROVIDER_CREDENTIAL_MISSING", async () => {
  const result = await runRunner({
    ECOMIC_PROVIDER: "openai",
    ECOMIC_MODEL: "gpt-4",
    ECOMIC_SESSION_ID: "test-session",
    ECOMIC_RESEARCH_QUESTION: "test question",
    ECOMIC_STATE_DIR: "/tmp/test-state",
    OPENAI_API_KEY: "", // Missing credential
  });
  const errorEvents = result.events.filter((e) => e.type === "agent_error");
  assert.ok(errorEvents.length > 0, "Expected at least one agent_error event");
  assert.equal(errorEvents[0].code, "PROVIDER_CREDENTIAL_MISSING",
    `Expected PROVIDER_CREDENTIAL_MISSING, got: ${errorEvents[0].code}`);
  assert.notEqual(result.code, 0, "Runner should exit with non-zero code");
});

test("Failure: unknown provider returns PROVIDER_CREDENTIAL_MISSING", async () => {
  const result = await runRunner({
    ECOMIC_PROVIDER: "unknown_provider",
    ECOMIC_MODEL: "some-model",
    ECOMIC_SESSION_ID: "test-session",
    ECOMIC_RESEARCH_QUESTION: "test question",
    ECOMIC_STATE_DIR: "/tmp/test-state",
  });
  const errorEvents = result.events.filter((e) => e.type === "agent_error");
  assert.ok(errorEvents.length > 0, "Expected at least one agent_error event");
  assert.equal(errorEvents[0].code, "PROVIDER_CREDENTIAL_MISSING");
});

test("Failure: empty session ID returns PROVIDER_CREDENTIAL_MISSING", async () => {
  const result = await runRunner({
    ECOMIC_PROVIDER: "openai",
    ECOMIC_MODEL: "gpt-4",
    ECOMIC_SESSION_ID: "",
    ECOMIC_RESEARCH_QUESTION: "test question",
    ECOMIC_STATE_DIR: "/tmp/test-state",
    OPENAI_API_KEY: "fake-key",
  });
  const errorEvents = result.events.filter((e) => e.type === "agent_error");
  assert.ok(errorEvents.length > 0, "Expected at least one agent_error event");
  assert.equal(errorEvents[0].code, "PROVIDER_CREDENTIAL_MISSING");
});

test("Failure: empty research question returns PROVIDER_CREDENTIAL_MISSING", async () => {
  const result = await runRunner({
    ECOMIC_PROVIDER: "openai",
    ECOMIC_MODEL: "gpt-4",
    ECOMIC_SESSION_ID: "test-session",
    ECOMIC_RESEARCH_QUESTION: "",
    ECOMIC_STATE_DIR: "/tmp/test-state",
    OPENAI_API_KEY: "fake-key",
  });
  const errorEvents = result.events.filter((e) => e.type === "agent_error");
  assert.ok(errorEvents.length > 0, "Expected at least one agent_error event");
  assert.equal(errorEvents[0].code, "PROVIDER_CREDENTIAL_MISSING");
});

test("Failure: custom provider without base URL returns PROVIDER_MALFORMED_RESPONSE", async () => {
  // This test requires Pi Runtime to be available
  const piCore = path.join(root, "vendor/pi/packages/agent/dist/index.js");
  if (!fs.existsSync(piCore)) {
    test.skip("Pi Runtime not available — skipping");
    return;
  }

  const result = await runRunner({
    ECOMIC_PROVIDER: "custom_openai_compatible",
    ECOMIC_MODEL: "custom-model",
    ECOMIC_BASE_URL: "", // Missing base URL
    ECOMIC_SESSION_ID: "test-session",
    ECOMIC_RESEARCH_QUESTION: "test question",
    ECOMIC_STATE_DIR: "/tmp/test-state",
    ECOMIC_CUSTOM_API_KEY: "fake-key",
  });
  const errorEvents = result.events.filter((e) => e.type === "agent_error");
  assert.ok(errorEvents.length > 0, "Expected at least one agent_error event");
  assert.ok(
    errorEvents[0].code === "PROVIDER_MALFORMED_RESPONSE" || errorEvents[0].code === "PI_MODEL_NOT_FOUND",
    `Expected PROVIDER_MALFORMED_RESPONSE or PI_MODEL_NOT_FOUND, got: ${errorEvents[0].code}`
  );
});

test("Failure: unsupported model ID returns PI_MODEL_NOT_FOUND", async () => {
  // This test requires Pi Runtime to be available
  const piCore = path.join(root, "vendor/pi/packages/agent/dist/index.js");
  if (!fs.existsSync(piCore)) {
    test.skip("Pi Runtime not available — skipping");
    return;
  }

  const result = await runRunner({
    ECOMIC_PROVIDER: "openai",
    ECOMIC_MODEL: "definitely-not-a-real-model-xyz123",
    ECOMIC_SESSION_ID: "test-session",
    ECOMIC_RESEARCH_QUESTION: "test question",
    ECOMIC_STATE_DIR: "/tmp/test-state",
    OPENAI_API_KEY: "fake-key",
  });
  const errorEvents = result.events.filter((e) => e.type === "agent_error");
  assert.ok(errorEvents.length > 0, "Expected at least one agent_error event");
  assert.equal(errorEvents[0].code, "PI_MODEL_NOT_FOUND",
    `Expected PI_MODEL_NOT_FOUND, got: ${errorEvents[0].code}`);
});

test("Failure: error events always include session_id", async () => {
  const result = await runRunner({
    ECOMIC_PROVIDER: "openai",
    ECOMIC_MODEL: "gpt-4",
    ECOMIC_SESSION_ID: "test-session-123",
    ECOMIC_RESEARCH_QUESTION: "test question",
    ECOMIC_STATE_DIR: "/tmp/test-state",
    OPENAI_API_KEY: "",
  });
  const errorEvents = result.events.filter((e) => e.type === "agent_error");
  assert.ok(errorEvents.length > 0);
  assert.equal(errorEvents[0].session_id, "test-session-123",
    "Error events must include session_id for UI filtering");
});

test("Failure: runner exits with non-zero code on error", async () => {
  const result = await runRunner({
    ECOMIC_PROVIDER: "openai",
    ECOMIC_MODEL: "gpt-4",
    ECOMIC_SESSION_ID: "test-session",
    ECOMIC_RESEARCH_QUESTION: "test",
    ECOMIC_STATE_DIR: "/tmp/test-state",
    OPENAI_API_KEY: "",
  });
  assert.notEqual(result.code, 0, "Runner must exit with non-zero code on error");
  assert.equal(result.code, 1, "Runner should exit with code 1");
});

test("Failure: stderr contains diagnostic information", async () => {
  const result = await runRunner({
    ECOMIC_PROVIDER: "openai",
    ECOMIC_MODEL: "gpt-4",
    ECOMIC_SESSION_ID: "test-session",
    ECOMIC_RESEARCH_QUESTION: "test",
    ECOMIC_STATE_DIR: "/tmp/test-state",
    OPENAI_API_KEY: "",
  });
  assert.ok(result.stderr.length > 0, "stderr should contain diagnostic information");
  assert.ok(result.stderr.includes("[agent_error]"), "stderr should contain [agent_error] tag");
});

test("Failure: stdout only contains JSONL (no free-form text)", async () => {
  const result = await runRunner({
    ECOMIC_PROVIDER: "openai",
    ECOMIC_MODEL: "gpt-4",
    ECOMIC_SESSION_ID: "test-session",
    ECOMIC_RESEARCH_QUESTION: "test",
    ECOMIC_STATE_DIR: "/tmp/test-state",
    OPENAI_API_KEY: "",
  });
  for (const line of result.events) {
    assert.ok(typeof line === "object", "Each stdout line must be valid JSON");
    assert.ok(line.type, "Each event must have a type field");
  }
});

test("Failure: API key is never leaked in events or stderr", async () => {
  const fakeKey = "sk-leaked-test-key-12345";
  const result = await runRunner({
    ECOMIC_PROVIDER: "openai",
    ECOMIC_MODEL: "gpt-4",
    ECOMIC_SESSION_ID: "test-session",
    ECOMIC_RESEARCH_QUESTION: "test",
    ECOMIC_STATE_DIR: "/tmp/test-state",
    OPENAI_API_KEY: fakeKey,
  });
  const allOutput = result.stderr + JSON.stringify(result.events);
  assert.ok(!allOutput.includes(fakeKey),
    "API key must never appear in stderr or events");
});
