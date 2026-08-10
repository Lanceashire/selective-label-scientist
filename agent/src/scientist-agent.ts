/** Real Pi Agent Core integration. MockLLM remains CI-only in Python. */
import { Agent, type AgentTool } from "@earendil-works/pi-agent-core";
import { Type } from "@earendil-works/pi-ai";
import { ECOMIC_SYSTEM_PROMPT } from "./system-prompt.js";

export type RuntimeCall = (action: string, payload: Record<string, unknown>) => Promise<unknown>;
const session = Type.Object({ session_id: Type.String(), state_dir: Type.Optional(Type.String()) });
function tool(name: string, parameters: any, call: RuntimeCall): AgentTool<any> {
 return { name: `ecomic_${name}`, label: `ECOMIC: ${name}`, description: `Audited ECOMIC scientific tool: ${name}. Do not request hidden labels or final metrics.`, parameters, executionMode: "sequential", execute: async (_id, args) => ({ content: [{ type: "text", text: JSON.stringify(await call(name,args as Record<string,unknown>),null,2) }], details: { action:name } }) };
}
export function createScientistAgent(models: any, provider: string, modelId: string, callRuntime: RuntimeCall, sessionId = `ecomic-${Date.now()}`) {
 const model=models.getModel(provider,modelId); if(!model) throw new Error(`模型不可用：${provider}/${modelId}`);
 const tools=[
  tool("observe_state",session,callRuntime),
  tool("load_dataset",Type.Object({path:Type.String(),description:Type.Optional(Type.String()),state_dir:Type.Optional(Type.String())}),callRuntime),
  tool("confirm_decision_mapping",Type.Object({...session.properties,decision_column:Type.String(),observed_values:Type.Array(Type.String()),non_observed_values:Type.Array(Type.String()),target_column:Type.Optional(Type.String()),cost_column:Type.Optional(Type.String()),decision_time:Type.Optional(Type.String()),outcome_time:Type.Optional(Type.String()),observation_reversible:Type.Boolean(),observation_simulatable:Type.Boolean()}),callRuntime),
  tool("create_hypothesis",Type.Object({...session.properties,content:Type.String()}),callRuntime),
  tool("plan_experiment",Type.Object({...session.properties,hypothesis_id:Type.String(),policy:Type.String(),budget:Type.Number(),rounds:Type.Integer({minimum:1})}),callRuntime),
  tool("run_experiment",Type.Object({...session.properties,plan_id:Type.String(),policy:Type.String(),budget:Type.Number(),seed:Type.Integer(),rounds:Type.Integer({minimum:1})}),callRuntime),
  tool("lock_research_plan",Type.Object({...session.properties,plan_id:Type.String()}),callRuntime),
  tool("finalize_evaluation",Type.Object({...session.properties,run_id:Type.String()}),callRuntime),
  tool("claim_guard",Type.Object({...session.properties,claim:Type.String(),evidence_run_ids:Type.Array(Type.String()),strength:Type.Optional(Type.String())}),callRuntime),
 ];
 return new Agent({initialState:{systemPrompt:`${ECOMIC_SYSTEM_PROMPT}\n\nBefore experiments, establish and confirm DomainSpec. Never access Oracle data, never supply final metrics, and allow INCONCLUSIVE outcomes. Every hypothesis/revision must be persisted with tools.`,model,tools,thinkingLevel:"medium"},streamFn:models.streamSimple.bind(models),sessionId,toolExecution:"sequential",beforeToolCall:async({toolCall,args}:any)=>{if(/oracle|hidden.label|shell|bash/i.test(toolCall.name))return {block:true,reason:"Oracle and arbitrary shell are forbidden",terminate:true};if(toolCall.name==="ecomic_finalize_evaluation"&&"metrics" in args)return {block:true,reason:"Final metrics are evaluator-owned",terminate:true};}});
}
