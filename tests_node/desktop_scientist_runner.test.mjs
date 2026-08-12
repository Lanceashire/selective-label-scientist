import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

test("desktop Pi Scientist launcher uses vendored Agent Core and emits safe typed-tool events", () => {
  const source = fs.readFileSync("agent/src/desktop-scientist-runner-v2.mjs", "utf8");
  assert.match(source, /vendor\/pi\/packages\/agent\/dist\/index\.js/);
  assert.match(source, /new Agent/);
  assert.match(source, /streamFn:streamSimple/);
  assert.match(source, /tool_start/);
  assert.match(source, /tool_end/);
  assert.match(source, /beforeToolCall/);
  assert.match(source, /ecomic_compare_visible_evidence|compare_visible_evidence/);
  assert.match(source, /ecomic_revise_hypothesis|revise_hypothesis/);
assert.match(source, /custom_openai_compatible/);
  assert.match(source, /createProvider/);
  assert.match(source, /openAICompletionsApi/);
  assert.doesNotMatch(source, /console\.log\(.*API|process\.argv.*API/i);
});

test("desktop Scientist runner reuses one persistent Python worker and enforces tool deadlines", () => {
  const source = fs.readFileSync("agent/src/desktop-scientist-runner-v2.mjs", "utf8");
  assert.match(source, /function ensureWorker\(\)/);
  assert.match(source, /const pending = new Map\(\)/);
  assert.match(source, /TOOL_TIMEOUT_MS/);
  assert.match(source, /Tool timeout:/);
  assert.match(source, /taskkill/, "Windows tool timeout must terminate the owned worker tree");
  assert.doesNotMatch(source, /spawn\(backend, \["--stream"\]/, "tools must not cold-start a backend executable per call");
});