import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"../..");
function rpc(action:string,payload:Record<string,unknown>){const r=spawnSync(process.env.ECOMIC_PYTHON||"python",["-m","agent_backend.rpc"],{cwd:root,input:`${JSON.stringify({action,payload})}\n`,encoding:"utf8",windowsHide:true});return JSON.parse(r.stdout.trim().split(/\r?\n/).pop()||"{}");}
export default function(pi:ExtensionAPI){
 pi.registerCommand("ecomic-final-auto",{description:"按 Session 自动锁定 Run 所属 Plan 并执行内部最终评价",handler:async(_args,ctx)=>{const sessionId=await ctx.ui.input("Session ID","从 /ecomic-home 或历史研究中获取");if(!sessionId)return;try{const snapshot:any=rpc("resume_environment",{session_id:sessionId.trim()});const runId=snapshot.run_id;if(!runId)throw new Error("当前 Session 没有可恢复的实验 Run");rpc("lock_run_plan",{session_id:sessionId.trim(),run_id:runId});const result:any=rpc("finalize_evaluation",{session_id:sessionId.trim(),run_id:runId});ctx.ui.notify(`最终评价完成：${result.status}。所有指标由私有 Oracle 内部计算。`,`info`);}catch(error:any){ctx.ui.notify(`最终评价失败：${String(error.message||error).replace(/Bearer\s+[^\s]+/gi,"Bearer [REDACTED]")}`,"error");}}});
 pi.registerCommand("ecomic-history",{description:"查看并恢复 ECOMIC 历史研究",handler:async(_args,ctx)=>{const sessionId=await ctx.ui.input("输入要恢复的 Session ID","SQLite 历史 Session ID");if(!sessionId)return;try{const snapshot:any=rpc("resume_next_round",{session_id:sessionId.trim(),run_id:await ctx.ui.input("Run ID","从环境快照中获取")||""});ctx.ui.setWidget("ecomic-history",[`历史研究已恢复：${sessionId}`,`Run: ${snapshot.run_id}`,`下一轮：${snapshot.next_round}`,`模式：${snapshot.mode}`,"Oracle: LOCKED 🔒"],{placement:"aboveEditor"});ctx.ui.notify("恢复状态已加载；下一实验将沿确定性 replay 轨迹继续。","info");}catch(error:any){ctx.ui.notify(`恢复失败：${String(error.message||error)}`,"error");}}});
}
