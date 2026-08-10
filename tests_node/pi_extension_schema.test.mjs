import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

test("Pi extension has typed evaluator and separate semantic confirmations without metrics", () => {
  const source = fs.readFileSync("agent/src/pi-extension.ts", "utf8");
  const start = source.indexOf('register("finalize_evaluation"');
  const end = source.indexOf('register("observe_state"', start);
  const schema = source.slice(start, end);
  assert.match(source, /const\s+session\s*=\s*Type\.Object\(\{\s*session_id/);
  assert.match(schema, /\.\.\.session\.properties/);
  assert.match(schema, /run_id/);
  assert.doesNotMatch(schema, /metrics/);
  assert.match(source, /register\("confirm_observation_action"/);
  assert.match(source, /register\("lock_run_plan"/);
  assert.match(source, /secretInput/);
  assert.match(source, /credentials\.env/);
});
