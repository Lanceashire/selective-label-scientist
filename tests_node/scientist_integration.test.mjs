/**
 * Real Scientist Integration Test (Phase 7)
 *
 * Tests the full chain:
 *   Node Scientist Runner → Pi Agent Core → local deterministic provider
 *   → Pi produces Tool Call → typed tool → real Python worker
 *   → observe_state → returns result → Agent completed
 *
 * ALLOWED:  Mock Provider network (local HTTP server returns deterministic responses)
 * FORBIDDEN: Mock Pi Agent Core (must use real `new Agent(...)`, `prompt(...)`, tool calls)
 *
 * This test SKIPS gracefully if Pi Runtime or Python backend is unavailable.
 * In CI, it runs after Gate 2 (Pi Bootstrap) and Gate 6 (Python Backend Build).
 */
import assert from "node:assert/strict";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const piAgentCore = path.join(root, "vendor/pi/packages/agent/dist/index.js");
const piAi = path.join(root, "vendor/pi/packages/ai/dist/index.js");
const runner = path.join(root, "agent/src/desktop-scientist-runner-v2.mjs");

const runtimeAvailable = fs.existsSync(piAgentCore) && fs.existsSync(piAi) && fs.existsSync(runner);

test.skip(!runtimeAvailable, "Pi Runtime or Scientist Runner not available — skipping integration test");

/**
 * Creates a deterministic local OpenAI-compatible HTTP server.
 * First response: tool_call to ecomic_observe_state
 * Second response: simple text completion (agent finishes)
 */
function createMockProvider(port) {
  let callCount = 0;
  const server = http.createServer((req, res) => {
    let body = "";
    req.on("data", (chunk) => { body += chunk; });
    req.on("end", () => {
      callCount++;
      res.writeHead(200, { "Content-Type": "application/json" });

      if (callCount === 1) {
        // First response: instruct Pi to call ecomic_observe_state
        res.end(JSON.stringify({
          id: `chatcmpl-mock-${callCount}`,
          object: "chat.completion",
          choices: [{
            index: 0,
            message: {
              role: "assistant",
              content: null,
              tool_calls: [{
                id: `call_${callCount}`,
                type: "function",
                function: {
                  name: "ecomic_observe_state",
                  arguments: JSON.stringify({ session_id: process.env.ECOMIC_TEST_SESSION_ID || "" }),
                },
              }],
            },
            finish_reason: "tool_calls",
          }],
          usage: { prompt_tokens: 10, completion_tokens: 20, total_tokens: 30 },
        }));
      } else {
        // Subsequent responses: agent completes
        res.end(JSON.stringify({
          id: `chatcmpl-mock-${callCount}`,
          object: "chat.completion",
          choices: [{
            index: 0,
            message: {
              role: "assistant",
              content: "I have observed the experimental state and completed my research task. The session is ready for evaluation.",
            },
            finish_reason: "stop",
          }],
          usage: { prompt_tokens: 50, completion_tokens: 30, total_tokens: 80 },
        }));
      }
    });
  });
  return new Promise((resolve) => {
    server.listen(port, "127.0.0.1", () => resolve({ server, port }));
  });
}

/**
 * Starts the real Python backend as a subprocess and returns helpers
 * to send JSONL RPC requests.
 */
function startPythonBackend(stateDir) {
  const backend = process.env.ECOMIC_BACKEND_EXE || "";
  const python = process.env.ECOMIC_PYTHON || "python";
  const child = backend
    ? spawn(backend, [], { cwd: root, stdio: ["pipe", "pipe", "pipe"], windowsHide: true })
    : spawn(python, ["-m", "agent_backend.desktop_sidecar"], { cwd: root, stdio: ["pipe", "pipe", "pipe"], windowsHide: true });

  let buffer = "";
  const pending = new Map();
  let seq = 0;

  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (chunk) => {
    buffer += chunk;
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const response = JSON.parse(line);
        if (response.event) continue; // skip events
        const req = pending.get(response.request_id);
        if (req) {
          pending.delete(response.request_id);
          if (response.ok) req.resolve(response.data);
          else req.reject(new Error(response.error?.message || "backend error"));
        }
      } catch { /* ignore malformed */ }
    }
  });
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", () => {}); // suppress

  function call(action, payload = {}) {
    return new Promise((resolve, reject) => {
      const requestId = `test_${++seq}`;
      pending.set(requestId, { resolve, reject });
      const request = JSON.stringify({ request_id: requestId, action, payload: { ...payload, state_dir: stateDir } });
      child.stdin.write(`${request}\n`);
    });
  }

  return { child, call };
}

/**
 * Creates a minimal test CSV dataset and imports it via the Python backend.
 */
async function setupTestSession(backend) {
  const csvPath = path.join(root, "release", "backend-exe-acceptance", "scientist_integration.csv");
  fs.mkdirSync(path.dirname(csvPath), { recursive: true });
  const rows = "feature,decision,label,cost\n" + Array.from({ length: 80 }, (_, i) => `${i},${i % 2},${i % 3},1`).join("\n");
  fs.writeFileSync(csvPath, rows, "utf8");

  const preview = await backend.call("inspect_dataset", { path: csvPath });
  const loaded = await backend.call("load_dataset", { path: csvPath, dataset_handle_id: preview.dataset_handle_id });
  const sessionId = loaded.session_id;

  // Set up domain spec so preflight passes
  await backend.call("confirm_decision_mapping", {
    session_id: sessionId,
    decision_column: "decision",
    observed_values: ["1"],
    non_observed_values: ["0"],
    target_column: "label",
    cost_column: "cost",
  });
  await backend.call("confirm_observation_action", {
    session_id: sessionId,
    reversible: true,
    simulatable: true,
    description: "integration test observation",
  });

  return { sessionId, csvPath };
}

test("Scientist Integration: real Pi Agent Core + real Python worker + mock provider", async () => {
  if (!runtimeAvailable) return;

  const stateDir = path.join(root, "release", "scientist-integration-state");
  fs.mkdirSync(stateDir, { recursive: true });

  // 1. Start Python backend and create a real session
  const backend = startPythonBackend(stateDir);
  try {
    // Wait for backend to be ready
    await new Promise((resolve) => setTimeout(resolve, 2000));
    await backend.call("health_check");

    const { sessionId } = await setupTestSession(backend);

    // 2. Start mock provider on a random port
    const mockProvider = await createMockProvider(0);
    const mockPort = mockProvider.server.address().port;
    const mockBaseUrl = `http://127.0.0.1:${mockPort}`;

    try {
      // 3. Run the scientist runner with mock provider
      const events = [];
      const env = {
        ...process.env,
        ECOMIC_PROVIDER: "custom_openai_compatible",
        ECOMIC_MODEL: "test-deterministic-model",
        ECOMIC_BASE_URL: mockBaseUrl,
        ECOMIC_CUSTOM_API_KEY: "test-key-not-real",
        ECOMIC_SESSION_ID: sessionId,
        ECOMIC_RESEARCH_QUESTION: "Observe the current experimental state.",
        ECOMIC_STATE_DIR: stateDir,
        ECOMIC_BACKEND: process.env.ECOMIC_BACKEND_EXE || "",
        ECOMIC_PYTHON: process.env.ECOMIC_PYTHON || "python",
      };

      const result = await new Promise((resolve, reject) => {
        const child = spawn(process.execPath, [runner], {
          cwd: root,
          env,
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
          // Parse JSONL events from stdout
          for (const line of stdout.split(/\r?\n/)) {
            if (!line.trim()) continue;
            try { events.push(JSON.parse(line)); } catch { /* not JSON */ }
          }
          resolve({ code, events, stderr });
        });
        child.on("error", reject);
        // Timeout after 60 seconds
        setTimeout(() => {
          child.kill("SIGKILL");
          reject(new Error("Scientist runner timed out after 60s"));
        }, 60000);
      });

      // 4. Verify the full chain
      const eventTypes = events.map((e) => e.type);

      // Pi Agent Core must have initialized (agent_ready emitted by Node)
      assert.ok(eventTypes.includes("agent_ready"),
        `Expected agent_ready in events. Got: ${eventTypes.join(", ")}. stderr: ${result.stderr}`);

      // Pi must have produced at least one tool call
      assert.ok(eventTypes.includes("tool_start"),
        `Expected tool_start in events. Got: ${eventTypes.join(", ")}`);

      // The tool call must have been to observe_state
      const toolStartEvents = events.filter((e) => e.type === "tool_start");
      assert.ok(toolStartEvents.some((e) => e.tool === "observe_state"),
        `Expected observe_state tool call. Got tools: ${toolStartEvents.map((e) => e.tool).join(", ")}`);

      // The tool call must have reached the Python worker and completed
      assert.ok(eventTypes.includes("tool_end"),
        `Expected tool_end in events. Got: ${eventTypes.join(", ")}`);

      // Agent must have completed
      assert.ok(eventTypes.includes("agent_completed"),
        `Expected agent_completed in events. Got: ${eventTypes.join(", ")}`);

      // No agent_error should have occurred
      assert.ok(!eventTypes.includes("agent_error"),
        `Unexpected agent_error. Events: ${JSON.stringify(events.filter((e) => e.type === "agent_error"))}`);

    } finally {
      mockProvider.server.close();
    }
  } finally {
    try { backend.child.stdin.write(JSON.stringify({ request_id: "shutdown", action: "shutdown", payload: {} }) + "\n"); } catch {}
    try { backend.child.kill("SIGKILL"); } catch {}
  }
});
