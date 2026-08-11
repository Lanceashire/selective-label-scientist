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
