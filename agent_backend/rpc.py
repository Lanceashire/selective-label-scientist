"""Typed RPC facade; every action delegates to ResearchRuntime."""
from __future__ import annotations
import json, sys
from pathlib import Path
from .runtime import ResearchRuntime
def dispatch(action: str, payload: dict) -> dict:
 if action=="finalize_evaluation" and "metrics" in payload: raise ValueError("schema validation failed: finalize_evaluation accepts only session_id and run_id; metrics are evaluator-owned")
 runtime=ResearchRuntime(payload.get("state_dir") or Path.home()/".ecomic")
 try:
  if action=="load_dataset": return runtime.create_session(str(payload["path"]),str(payload.get("description","")))
  if action=="confirm_decision_mapping": return runtime.confirm_decision_mapping(str(payload["session_id"]),str(payload["decision_column"]),list(payload["observed_values"]),list(payload["non_observed_values"]),target_column=payload.get("target_column"),cost_column=payload.get("cost_column"),decision_time=payload.get("decision_time"),outcome_time=payload.get("outcome_time"),observation_reversible=payload.get("observation_reversible"),observation_simulatable=payload.get("observation_simulatable"))
  if action=="create_hypothesis": return runtime.create_hypothesis(str(payload["session_id"]),str(payload["content"]))
  if action=="plan_experiment": return runtime.plan_experiment(str(payload["session_id"]),str(payload["hypothesis_id"]),str(payload["policy"]),float(payload["budget"]),int(payload["rounds"]))
  if action=="run_experiment": return runtime.run_experiment(str(payload["session_id"]),str(payload["plan_id"]),str(payload["policy"]),float(payload["budget"]),int(payload.get("seed",0)),int(payload["rounds"]))
  if action=="lock_research_plan": return runtime.lock_research_plan(str(payload["session_id"]),str(payload["plan_id"]))
  if action=="finalize_evaluation": return runtime.finalize_evaluation(str(payload["session_id"]),str(payload["run_id"]))
  if action=="claim_guard": return runtime.claim_guard(str(payload["session_id"]),str(payload["claim"]),str(payload.get("domain_scope","run-local")),str(payload.get("dataset_scope","current-dataset")),str(payload.get("policy_scope","current-policy")),str(payload.get("budget_scope","current-budget")),str(payload.get("metric_scope","feedback_count")),list(payload.get("evidence_run_ids",[])),str(payload.get("strength","cautious")))
  if action=="observe_state": return runtime.observe_state(str(payload["session_id"]))
  if action=="resume_environment": return runtime.resume_environment(str(payload["session_id"]))
  raise ValueError(f"unknown typed tool: {action}")
 finally: runtime.close()
def main()->int:
 for line in sys.stdin:
  try: r=json.loads(line); output=dispatch(str(r.get("action","")),dict(r.get("payload",{})))
  except Exception as exc: output={"status":"ERROR","message":str(exc)}
  print(json.dumps(output,ensure_ascii=False),flush=True)
 return 0
if __name__=="__main__": raise SystemExit(main())
