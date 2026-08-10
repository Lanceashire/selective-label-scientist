import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

test("formal Scientist command is gated by a verified tool probe and runs Agent Core", () => {
  const runtime = fs.readFileSync("agent/src/ecomic-api-runtime.ts", "utf8");
  const agent = fs.readFileSync("agent/src/scientist-agent.ts", "utf8");
  assert.match(runtime, /ecomic-scientist/);
  assert.match(runtime, /tool_calling_verified/);
  assert.match(runtime, /createScientistAgent/);
  assert.match(runtime, /begin with observe_state/);
  assert.match(agent, /streamFn:\s*streamSimple/);
  assert.match(agent, /getApiKey:\s*\(\) => apiKey/);
  assert.doesNotMatch(agent, /metrics:\s*Type/);
});
