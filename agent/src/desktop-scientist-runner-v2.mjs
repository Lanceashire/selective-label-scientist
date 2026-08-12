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
let worker;
let workerBuffer = "";
let workerSequence = 0;
const pending = new Map();
const TOOL_TIMEOUT_MS = 120000;

function rejectPending(message) {
  for (const { reject, timer } of pending.values()) { clearTimeout(timer); reject(new Error(message)); }
  pending.clear();
}

function stopWorker(reason = "Research worker stopped.") {
  const child = worker;
  worker = undefined;
  if (!child || child.exitCode !== null || child.killed) return;
  if (process.platform === "win32" && child.pid) spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], { stdio: "ignore", windowsHide: true });
  else child.kill("SIGKILL");
  rejectPending(reason);
}

function receiveWorkerLine(line) {
  if (!line.trim()) return;
  let response;
  try { response = JSON.parse(line); } catch { stopWorker("Research worker emitted malformed JSON."); return; }
  if (response.type === "experiment_progress") { emit(response); return; }
  const requestId = response.request_id;
  const request = pending.get(requestId);
  if (!request) return;
  pending.delete(requestId); clearTimeout(request.timer);
  if (response.ok === true) request.resolve(response.data);
  else request.reject(new Error(response.error?.message || "Research worker request failed."));
}

function ensureWorker() {
  if (worker && worker.exitCode === null && !worker.killed) return worker;
  const backend = process.env.ECOMIC_BACKEND?.trim();
  const module = process.env.ECOMIC_PYTHON || "python";
  worker = backend
    ? spawn(backend, [], { cwd: root, stdio: ["pipe", "pipe", "pipe"], windowsHide: true })
    : spawn(module, ["-m", "agent_backend.desktop_sidecar"], { cwd: root, stdio: ["pipe", "pipe", "pipe"], windowsHide: true });
  worker.stdout.setEncoding("utf8");
  worker.stdout.on("data", (chunk) => { workerBuffer += chunk; const lines = workerBuffer.split(/\r?\n/); workerBuffer = lines.pop() || ""; for (const line of lines) receiveWorkerLine(line); });
  worker.stderr.setEncoding("utf8");
  worker.stderr.on("data", (chunk) => process.stderr.write(chunk));
  worker.on("error", (error) => { worker = undefined; rejectPending(`Research worker failed to start: ${error.message}`); });
  worker.on("close", (code) => { if (workerBuffer.trim()) receiveWorkerLine(workerBuffer); workerBuffer = ""; worker = undefined; rejectPending(`Research worker exited (${code ?? "unknown"}).`); });
  return worker;
}

function call(action, payload) {
  return new Promise((resolve, reject) => {
    const child = ensureWorker();
    const request_id = `tool_${++workerSequence}`;
    const timer = setTimeout(() => { pending.delete(request_id); stopWorker(`Tool timeout: ${action}`); reject(new Error(`Tool timeout: ${action}`)); }, TOOL_TIMEOUT_MS);
    pending.set(request_id, { resolve, reject, timer });
    const request = JSON.stringify({ request_id, action, payload: { ...payload, state_dir: process.env.ECOMIC_STATE_DIR } });
    child.stdin.write(`${request}\n`, (error) => { if (!error) return; const active = pending.get(request_id); if (!active) return; pending.delete(request_id); clearTimeout(timer); stopWorker(`Research worker write failed: ${error.message}`); reject(error); });
  });
}
const session = Type.Object({ session_id: Type.String(), state_dir: Type.Optional(Type.String()) });
function typedTool(name, parameters) {
  return { name: `ecomic_${name}`, label: `ECOMIC: ${name}`, description: `Audited typed research tool ${name}; never expose Oracle labels or evaluator metrics.`, parameters, executionMode:"sequential", execute: async (_id,args) => { const sid=args.session_id||process.env.ECOMIC_SESSION_ID||""; emit({type:"tool_start",tool:name,session_id:sid}); const result=await call(name,args); emit({type:"tool_end",tool:name,status:"COMPLETED",session_id:sid}); return {content:[{type:"text",text:JSON.stringify(result)}],details:{action:name}}; } };
}
function agent(model, key, sid) {
  const tools=[typedTool("observe_state",session),typedTool("audit_environment",session),typedTool("create_hypothesis",Type.Object({...session.properties,content:Type.String()})),typedTool("revise_hypothesis",Type.Object({...session.properties,parent_hypothesis_id:Type.String(),content:Type.String()})),typedTool("plan_experiment",Type.Object({...session.properties,hypothesis_id:Type.String(),policy:Type.String(),budget:Type.Number(),rounds:Type.Integer({minimum:1})})),typedTool("run_experiment",Type.Object({...session.properties,plan_id:Type.String(),policy:Type.String(),budget:Type.Number(),seed:Type.Integer(),rounds:Type.Integer({minimum:1})})),typedTool("compare_visible_evidence",Type.Object({...session.properties,run_ids:Type.Array(Type.String(),{minItems:2})})),typedTool("lock_run_plan",Type.Object({...session.properties,run_id:Type.String()})),typedTool("finalize_evaluation",Type.Object({...session.properties,run_id:Type.String()})),typedTool("claim_guard",Type.Object({...session.properties,claim:Type.String(),evidence_run_ids:Type.Array(Type.String()),strength:Type.Optional(Type.String())})),typedTool("generate_report",session)];
  return new Agent({initialState:{systemPrompt:"You are ECOMIC, a cautious AI scientist. Use only typed ECOMIC tools. Begin with observe_state and audit_environment, create and revise hypotheses only from researcher-visible evidence, and never access Oracle labels or submit evaluator metrics.",model,tools,thinkingLevel:"medium"},streamFn:streamSimple,getApiKey:()=>key,sessionId:`desktop-${sid}`,toolExecution:"sequential",beforeToolCall:async({toolCall,args})=>(/oracle|hidden[._-]?label|shell|bash/i.test(toolCall.name)||(toolCall.name==="ecomic_finalize_evaluation"&&"metrics" in args))?{block:true,reason:"Forbidden research boundary",terminate:true}:undefined});
}
async function main() {
  const provider = process.env.ECOMIC_PROVIDER || "";
  const info = providers[provider];
  const sid = process.env.ECOMIC_SESSION_ID || "";
  const question = process.env.ECOMIC_RESEARCH_QUESTION || "";

  // Validate prerequisites
  if (!info || !sid || !question.trim() || !process.env[info[1]]) {
    throw classifyError("缺少经验证的模型、凭据、Session 或研究问题", "PROVIDER_CREDENTIAL_MISSING");
  }

  const baseUrl = process.env.ECOMIC_BASE_URL?.trim() || undefined;
  const modelId = process.env.ECOMIC_MODEL || "";

  // Resolve model through Pi
  let model;
  try {
    const models = builtinModels();
    if (provider === "custom_openai_compatible") {
      if (!baseUrl) throw classifyError("Custom Provider requires base URL", "PROVIDER_MALFORMED_RESPONSE");
      models.setProvider(customProvider(modelId, baseUrl));
    }
    const found = models.getModel(info[0], modelId);
    if (!found) throw classifyError(`Pi does not support this Model ID: ${modelId}`, "PI_MODEL_NOT_FOUND");
    model = baseUrl && provider !== "custom_openai_compatible" ? { ...found, baseUrl } : found;
  } catch (error) {
    if (error.code) throw error;
    throw classifyError(error.message, "PI_AGENT_CORE_MISSING");
  }

  // Initialize Pi Agent
  let run;
  try {
    run = agent(model, process.env[info[1]], sid);
  } catch (error) {
    throw classifyError(`Pi Agent 初始化失败: ${error.message}`, "AGENT_INITIALIZATION_FAILED");
  }

  run.subscribe(event => {
    if (event.type === "tool_execution_start") {
      emit({ type: "agent_tool_execution", tool: event.toolName, session_id: sid });
    }
  });

  // Emit agent_ready only after Pi Agent is successfully initialized
  emit({ type: "agent_ready", session_id: sid, message: "Pi Agent 已初始化，开始执行研究任务。" });

  // Execute the research prompt
  try {
    await run.prompt(`Current ECOMIC session_id is ${sid}. Research question: ${question}.`);
  } catch (error) {
    throw classifyError(error.message || "Pi Agent 执行失败", "AGENT_PROTOCOL_ERROR");
  }

  if (run.state.errorMessage) {
    throw classifyError(run.state.errorMessage, "AGENT_PROTOCOL_ERROR");
  }

  emit({ type: "agent_completed", session_id: sid });
}

function classifyError(message, defaultCode) {
  const msg = String(message || "").toLowerCase();
  let code = defaultCode || "UNKNOWN";
  if (msg.includes("unauthorized") || msg.includes("401") || msg.includes("invalid api key")) code = "PROVIDER_UNAUTHORIZED";
  else if (msg.includes("rate_limit") || msg.includes("429") || msg.includes("rate limit")) code = "PROVIDER_RATE_LIMITED";
  else if (msg.includes("timeout") || msg.includes("timed out")) code = "PROVIDER_TIMEOUT";
  else if (msg.includes("network") || msg.includes("econnrefused") || msg.includes("enotfound") || msg.includes("fetch failed")) code = "PROVIDER_NETWORK_ERROR";
  else if (msg.includes("not found") || msg.includes("model")) code = defaultCode;
  const err = new Error(message);
  err.code = code;
  err.type = "agent_error";
  return err;
}

main().catch((error) => {
  const code = error.code || "UNKNOWN";
  const message = error.message || "Scientist Agent 运行失败。";
  process.stderr.write(`[agent_error] code=${code} message=${message}\n`);
  if (error.stack) process.stderr.write(`${error.stack}\n`);
  emit({ type: "agent_error", code, message, session_id: process.env.ECOMIC_SESSION_ID || "" });
  process.exitCode = 1;
}).finally(() => stopWorker("Scientist task finished."));
