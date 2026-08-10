import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
test("real Pi Scientist Agent uses Agent Core and forbids injected metrics",()=>{const source=fs.readFileSync("agent/src/scientist-agent.ts","utf8");assert.match(source,/new Agent/);assert.match(source,/streamSimple/);assert.match(source,/beforeToolCall/);assert.match(source,/Final metrics are evaluator-owned/);assert.match(source,/create_hypothesis/);assert.match(source,/run_experiment/);assert.match(source,/finalize_evaluation/);assert.doesNotMatch(source,/import .*MockLLM|new MockLLM/);});
