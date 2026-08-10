/** Real Pi Agent Core integration. MockLLM remains CI-only in Python. */
import { Agent, type AgentTool } from "@earendil-works/pi-agent-core";
import { Type, streamSimple, type Api, type Model } from "@earendil-works/pi-ai/compat";
import { ECOMIC_SYSTEM_PROMPT } from "./system-prompt.js";

export type RuntimeCall = (action: string, payload: Record<string, unknown>) => Promise<unknown>;
const session = Type.Object({ session_id: Type.String(), state_dir: Type.Optional(Type.String()) });
function tool(name: string, parameters: any, call: RuntimeCall): AgentTool<any> {
  return { name: `ecomic_${name}`, label: `ECOMIC: ${name}`, description: `Audited ECOMIC scientific tool: ${name}. Never request hidden labels or supply final metrics.`, parameters, executionMode: "sequential", execute: async (_id, args) => ({ content: [{ type: "text", text: JSON.stringify(await call(name, args as Record<string, unknown>), null, 2) }], details: { action: name } }) };
}
export function createScientistAgent(model: Model<Api>, apiKey: string, callRuntime: RuntimeCall, sessionId = `ecomic-${Date.now()}`) {
  const tools = [
    tool("observe_state", session, callRuntime),
    tool("audit_environment", session, callRuntime),
    tool("resume_environment", session, callRuntime),
    tool("generate_report", session, callRuntime),
    tool("load_dataset", Type.Object({ path: Type.String(), description: Type.Optional(Type.String()), state_dir: Type.Optional(Type.String()) }), callRuntime),
    tool("confirm_decision_mapping", Type.Object({ ...session.properties, decision_column: Type.String(), observed_values: Type.Array(Type.String()), non_observed_values: Type.Array(Type.String()), target_column: Type.Optional(Type.String()), cost_column: Type.Optional(Type.String()), decision_time: Type.Optional(Type.String()), outcome_time: Type.Optional(Type.String()) }), callRuntime),
    tool("confirm_observation_action", Type.Object({ ...session.properties, reversible: Type.Boolean(), simulatable: Type.Boolean(), description: Type.String() }), callRuntime),
    tool("create_hypothesis", Type.Object({ ...session.properties, content: Type.String() }), callRuntime),
    tool("revise_hypothesis", Type.Object({ ...session.properties, parent_hypothesis_id: Type.String(), content: Type.String() }), callRuntime),
    tool("plan_experiment", Type.Object({ ...session.properties, hypothesis_id: Type.String(), policy: Type.String(), budget: Type.Number(), rounds: Type.Integer({ minimum: 1 }) }), callRuntime),
    tool("run_experiment", Type.Object({ ...session.properties, plan_id: Type.String(), policy: Type.String(), budget: Type.Number(), seed: Type.Integer(), rounds: Type.Integer({ minimum: 1 }) }), callRuntime),
    tool("compare_visible_evidence", Type.Object({ ...session.properties, run_ids: Type.Array(Type.String(), { minItems: 2 }) }), callRuntime),
    tool("lock_run_plan", Type.Object({ ...session.properties, run_id: Type.String() }), callRuntime),
    // There intentionally is no `metrics` field. EvaluationService owns private Oracle data.
    tool("finalize_evaluation", Type.Object({ ...session.properties, run_id: Type.String() }), callRuntime),
    tool("claim_guard", Type.Object({ ...session.properties, claim: Type.String(), evidence_run_ids: Type.Array(Type.String()), strength: Type.Optional(Type.String()) }), callRuntime),
  ];
  return new Agent({
    initialState: { systemPrompt: `${ECOMIC_SYSTEM_PROMPT}\n\nBegin with observe_state and then audit_environment. Before experiments, establish and separately confirm the DomainSpec decision mapping and observation action. After a run, use compare_visible_evidence; when evidence is insufficient, choose fresh seeds/budgets or persist a follow-up with revise_hypothesis. Never access Oracle data, never supply final metrics, allow INCONCLUSIVE outcomes, never chase an ungrounded policy win, and persist every hypothesis or revision through a typed tool. Only lock a run plan and finalize after the model has honestly decided the research loop is ready.`, model, tools, thinkingLevel: "medium" },
    streamFn: streamSimple,
    getApiKey: () => apiKey,
    sessionId,
    toolExecution: "sequential",
    beforeToolCall: async ({ toolCall, args }: any) => {
      if (/oracle|hidden[._-]?label|shell|bash/i.test(toolCall.name)) return { block: true, reason: "Oracle and arbitrary shell are forbidden", terminate: true };
      if (toolCall.name === "ecomic_finalize_evaluation" && "metrics" in args) return { block: true, reason: "Final metrics are evaluator-owned", terminate: true };
      return undefined;
    },
  });
}
