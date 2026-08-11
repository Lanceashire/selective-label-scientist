import assert from "node:assert/strict";
import test from "node:test";
import { Agent } from "../vendor/pi/packages/agent/dist/index.js";
import { EventStream, Type, getModel } from "../vendor/pi/packages/ai/dist/compat.js";

function usage() { return { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } }; }
function toolMessage(name, id) { return { role: "assistant", content: [{ type: "toolCall", id, name, arguments: { session_id: "mock-session" } }], api: "openai-responses", provider: "openai", model: "mock", usage: usage(), stopReason: "toolUse", timestamp: Date.now() }; }
function doneMessage() { return { role: "assistant", content: [{ type: "text", text: "research complete" }], api: "openai-responses", provider: "openai", model: "mock", usage: usage(), stopReason: "stop", timestamp: Date.now() }; }
function mockStreamFor(message) { const stream = new EventStream((event) => event.type === "done" || event.type === "error", (event) => event.type === "done" ? event.message : event.error); queueMicrotask(() => stream.push({ type: "done", reason: message.stopReason, message })); return stream; }

function auditedTool(name, calls, execute) {
  return { name, label: name, description: "mock typed research tool", parameters: Type.Object({ session_id: Type.String() }), executionMode: "sequential", execute: async (_id, args) => { calls.push(name); const details = await execute(args); return { content: [{ type: "text", text: JSON.stringify(details) }], details }; } };
}

test("Pi Agent Core mock provider revises its next tool call from researcher-visible run evidence", async () => {
  const calls = [];
  let revealedFeedback = 0;
  let turn = 0;
  const tools = [
    auditedTool("ecomic_create_hypothesis", calls, async () => ({ hypothesis_id: "h1" })),
    auditedTool("ecomic_run_experiment", calls, async () => { revealedFeedback = 6; return { run_id: "r1", revealed_label_count: revealedFeedback, comparison_scope: "RESEARCH_VISIBLE_ONLY" }; }),
    auditedTool("ecomic_revise_hypothesis", calls, async () => ({ hypothesis_id: "h2", parent_hypothesis_id: "h1" })),
    auditedTool("ecomic_generate_report", calls, async () => ({ final_report: "mock-report.md" })),
  ];
  const agent = new Agent({
    initialState: { model: getModel("openai", "gpt-4o-mini"), tools, systemPrompt: "Use only audited typed research tools." },
    getApiKey: () => "mock-key",
    toolExecution: "sequential",
    streamFn: () => {
      const next = turn++ === 0 ? "ecomic_create_hypothesis" : turn === 2 ? "ecomic_run_experiment" : turn === 3 ? (revealedFeedback > 0 ? "ecomic_revise_hypothesis" : "ecomic_generate_report") : turn === 4 ? "ecomic_generate_report" : null;
      return mockStreamFor(next ? toolMessage(next, `tool-${turn}`) : doneMessage());
    },
  });
  await agent.prompt("Compare low-budget policies using researcher-visible feedback only.");
  assert.deepEqual(calls, ["ecomic_create_hypothesis", "ecomic_run_experiment", "ecomic_revise_hypothesis", "ecomic_generate_report"]);
  assert.equal(revealedFeedback, 6);
  assert.equal(agent.state.errorMessage, undefined);
});