from __future__ import annotations
import json,sys
from pathlib import Path
from .runtime import ResearchRuntime
def dispatch(action:str,p:dict)->dict:
 if action=="finalize_evaluation" and "metrics" in p:raise ValueError("schema validation failed: finalize_evaluation accepts only session_id and run_id; metrics are evaluator-owned")
 r=ResearchRuntime(p.get("state_dir") or Path.home()/".ecomic")
 try:
  s=str(p.get("session_id",""))
  if action=="load_dataset":return r.create_session(str(p["path"]),str(p.get("description","")))
  if action=="confirm_decision_mapping":return r.confirm_decision_mapping(s,str(p["decision_column"]),list(p["observed_values"]),list(p["non_observed_values"]),target_column=p.get("target_column"),cost_column=p.get("cost_column"),decision_time=p.get("decision_time"),outcome_time=p.get("outcome_time"),observation_reversible=p.get("observation_reversible"),observation_simulatable=p.get("observation_simulatable"))
  if action=="create_hypothesis":return r.create_hypothesis(s,str(p["content"]))
  if action=="plan_experiment":return r.plan_experiment(s,str(p["hypothesis_id"]),str(p["policy"]),float(p["budget"]),int(p["rounds"]))
  if action=="run_experiment":return r.run_experiment(s,str(p["plan_id"]),str(p["policy"]),float(p["budget"]),int(p.get("seed",0)),int(p["rounds"]))
  if action=="lock_research_plan":return r.lock_research_plan(s,str(p["plan_id"]))
  if action=="lock_run_plan":return r.lock_run_plan(s,str(p["run_id"]))
  if action=="finalize_evaluation":return r.finalize_evaluation(s,str(p["run_id"]))
  if action=="claim_guard":return r.claim_guard(s,str(p["claim"]),str(p.get("domain_scope","run-local")),str(p.get("dataset_scope","current-dataset")),str(p.get("policy_scope","current-policy")),str(p.get("budget_scope","current-budget")),str(p.get("metric_scope","feedback_count")),list(p.get("evidence_run_ids",[])),str(p.get("strength","cautious")))
  if action=="observe_state":return r.observe_state(s)
  if action=="resume_environment":return r.resume_environment(s)
  if action=="resume_next_round":return r.resume_next_round(s,str(p["run_id"]))
  raise ValueError(f"unknown typed tool: {action}")
 finally:r.close()
def main():
 for line in sys.stdin:
  try:q=json.loads(line);out=dispatch(str(q.get("action","")),dict(q.get("payload",{})))
  except Exception as e:out={"status":"ERROR","message":str(e)}
  print(json.dumps(out,ensure_ascii=False),flush=True)
 return 0
if __name__=="__main__":raise SystemExit(main())
