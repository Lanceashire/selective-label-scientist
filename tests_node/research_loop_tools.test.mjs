import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

test("Pi and Agent expose typed follow-up research tools through the unified runtime", () => {
  const rpc = fs.readFileSync("agent_backend/rpc.py", "utf8");
  const extension = fs.readFileSync("agent/src/ecomic-research-loop-tools.ts", "utf8");
  const agent = fs.readFileSync("agent/src/scientist-agent.ts", "utf8");
  for (const name of ["audit_environment", "revise_hypothesis", "compare_visible_evidence"]) {
    assert.match(rpc, new RegExp(`action == "${name}"`));
    assert.match(extension, new RegExp(`"${name}"`));
    assert.match(agent, new RegExp(`"${name}"`));
  }
  assert.match(agent, /Begin with observe_state/);
  assert.match(agent, /compare_visible_evidence/);
  assert.doesNotMatch(extension, /metrics:\s*Type/);
});
