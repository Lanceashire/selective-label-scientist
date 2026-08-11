/** Safe JSONL desktop launcher for the real vendored Pi Agent Core. */
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Agent } from "../../vendor/pi/packages/agent/dist/index.js";
import { Type, streamSimple } from "../../vendor/pi/packages/ai/dist/compat.js";
import { envApiKeyAuth } from "../../vendor/pi/packages/ai/dist/auth/helpers.js";
import { createProvider } from "../../vendor/pi/packages/ai/dist/models.js";
import { openAICompletionsApi } from "../../vendor/pi/packages/ai/dist/api/openai-completions.lazy.js";
import { builtinModels } from "../../vendor/pi/packages/ai/dist/providers/all.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const providers = { openai:["openai","OPENAI_API_KEY"], anthropic:["anthropic","ANTHROPIC_API_KEY"], deepseek:["deepseek","DEEPSEEK_API_KEY"], google:["google","GEMINI_API_KEY"], openrouter:["openrouter","OPENROUTER_API_KEY"], moonshot:["moonshotai-cn","MOONSHOT_API_KEY"], qwen:["qwen-token-plan-cn","QWEN_TOKEN_PLAN_CN_API_KEY"], minimax:["minimax-cn","MINIMAX_API_KEY"], custom_openai_compatible:["ecomic-custom","ECOMIC_CUSTOM_API_KEY"] };
function customProvider(modelId, baseUrl) {
  return createProvider({ id:"ecomic-custom", name:"ECOMIC Custom OpenAI-Compatible", baseUrl,
    auth:{ apiKey:envApiKeyAuth("ECOMIC Custom API key", ["ECOMIC_CUSTOM_API_KEY"]) },
    models:[{ id:modelId, name:modelId, api:"openai-completions", provider:"ecomic-custom", baseUrl, reasoning:false, input:["text"], cost:{input:0,output:0,cacheRead:0,cacheWrite:0}, contextWindow:128000, maxTokens:8192 }],
    api:openAICompletionsApi() });
}
const emit = (event) => process.stdout.write(`${JSON.stringify(event)}\n`);
function call(action, payload) {
  return new Promise((resolve, reject) => {
    const backend = process.env.ECOMIC_BACKEND?.trim();
    const module = action === "run_experiment" ? "agent_backend.stream_rpc" : "agent_backend.rpc";
    const child = backend ? spawn(backend, ["--stream"], { cwd: root, stdio: ["pipe", "pipe", "ignore"], windowsHide: true }) : spawn(process.env.ECOMIC_PYTHON || "python", ["-m", module], { cwd: root, stdio: ["pipe", "pipe", "ignore"], windowsHide: true });
    let buffer = ""; let result;
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => { buffer += chunk; const lines = buffer.split(/\r?\n/); buffer = lines.pop() || ""; for (const line of lines) { if (!line.trim()) continue; try { const event = JSON.parse(line); if (event.type === "experiment_progress") emit(event); else result = event; } catch { /* ignore non-JSON output */ } } });
    child.on("error", reject);
    child.on("close", (code) => { if (buffer.trim()) { try { const event = JSON.parse(buffer); if (event.type === "experiment_progress") emit(event); else result = event; } catch {} } if (code !== 0 || !result || result.status === "ERROR") reject(new Error(result?.message || "Research runtime failed")); else resolve(result); });
    child.stdin.end(`${JSON.stringify({ action, payload: { ...payload, state_dir: process.env.ECOMIC_STATE_DIR } })}\n`);
  });
}
const session = Type.Object({ session_id: Type.String(), state_dir: Type.Optional(Type.String()) });
function typedTool(name, parameters) {
  return { name: `ecomic_${name}`, label: `ECOMIC: ${name}`, description: `Audited typed research tool ${name}; never expose Oracle labels or evaluator metrics.`, parameters, executionMode:"sequential", execute: async (_id,args) => { emit({type:"tool_start",tool:name}); const result=await call(name,args); emit({type:"tool_end",tool:name,status:"COMPLETED"}); return {content:[{type:"text",text:JSON.stringify(result)}],details:{action:name}}; } };
}
function agent(model, key, sid) {
  const tools=[typedTool("observe_state",session),typedTool("audit_environment",session),typedTool("create_hypothesis",Type.Object({...session.properties,content:Type.String()})),typedTool("revise_hypothesis",Type.Object({...session.properties,parent_hypothesis_id:Type.String(),content:Type.String()})),typedTool("plan_experiment",Type.Object({...session.properties,hypothesis_id:Type.String(),policy:Type.String(),budget:Type.Number(),rounds:Type.Integer({minimum:1})})),typedTool("run_experiment",Type.Object({...session.properties,plan_id:Type.String(),policy:Type.String(),budget:Type.Number(),seed:Type.Integer(),rounds:Type.Integer({minimum:1})})),typedTool("compare_visible_evidence",Type.Object({...session.properties,run_ids:Type.Array(Type.String(),{minItems:2})})),typedTool("lock_run_plan",Type.Object({...session.properties,run_id:Type.String()})),typedTool("finalize_evaluation",Type.Object({...session.properties,run_id:Type.String()})),typedTool("claim_guard",Type.Object({...session.properties,claim:Type.String(),evidence_run_ids:Type.Array(Type.String()),strength:Type.Optional(Type.String())})),typedTool("generate_report",session)];
  return new Agent({initialState:{systemPrompt:"You are ECOMIC, a cautious AI scientist. Use only typed ECOMIC tools. Begin with observe_state and audit_environment, create and revise hypotheses only from researcher-visible evidence, and never access Oracle labels or submit evaluator metrics.",model,tools,thinkingLevel:"medium"},streamFn:streamSimple,getApiKey:()=>key,sessionId:`desktop-${sid}`,toolExecution:"sequential",beforeToolCall:async({toolCall,args})=>(/oracle|hidden[._-]?label|shell|bash/i.test(toolCall.name)||(toolCall.name==="ecomic_finalize_evaluation"&&"metrics" in args))?{block:true,reason:"Forbidden research boundary",terminate:true}:undefined});
}
async function main(){const provider=process.env.ECOMIC_PROVIDER||"";const info=providers[provider];const sid=process.env.ECOMIC_SESSION_ID||"";const question=process.env.ECOMIC_RESEARCH_QUESTION||"";if(!info||!sid||!question.trim()||!process.env[info[1]])throw new Error("缺少经验证的模型、凭据、Session 或研究问题");const baseUrl=process.env.ECOMIC_BASE_URL?.trim()||undefined;const models=builtinModels();if(provider==="custom_openai_compatible"){if(!baseUrl)throw new Error("Custom Provider requires base URL");models.setProvider(customProvider(process.env.ECOMIC_MODEL||"",baseUrl));}const found=models.getModel(info[0],process.env.ECOMIC_MODEL||"");if(!found)throw new Error("Pi does not support this Model ID");const model=baseUrl&&provider!=="custom_openai_compatible"?{...found,baseUrl}:found;const run=agent(model,process.env[info[1]],sid);run.subscribe(event=>{if(event.type==="tool_execution_start")emit({type:"agent_tool_execution",tool:event.toolName});});emit({type:"agent_started",session_id:sid});await run.prompt(`Current ECOMIC session_id is ${sid}. Research question: ${question}.`);if(run.state.errorMessage)throw new Error(run.state.errorMessage);emit({type:"agent_completed",session_id:sid});}
main().catch(()=>{emit({type:"agent_error",message:"Scientist Agent 运行失败，请检查模型连接或研究配置。"});process.exitCode=1;});
