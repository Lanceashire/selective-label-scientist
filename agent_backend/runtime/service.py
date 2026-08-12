"""Single official runtime for all research entry points."""
from __future__ import annotations
import json
from collections import OrderedDict
from pathlib import Path
from typing import Any
from ..domains.semantic_auditor import audit_semantics
from ..environment.dynamic import DynamicSelectiveLabelEnvironment
from ..ingestion.handle import DatasetHandle
from ..ingestion.semantic_features import infer_semantics
from ..persistence.database import DatabaseManager

MAX_RUNTIME_DATASET_HANDLES = 2
MAX_CHART_POINTS = 2_000

def _downsample_chart_points(points: list[dict[str, Any]], limit: int = MAX_CHART_POINTS) -> tuple[list[dict[str, Any]], bool]:
 if len(points) <= limit: return points, False
 if limit < 2: return points[:1], True
 indexes = {round(index * (len(points) - 1) / (limit - 1)) for index in range(limit)}
 return [point for index, point in enumerate(points) if index in indexes], True

class ResearchRuntime:
 def __init__(self,state_dir: str|Path|None=None):
  self.state_dir=Path(state_dir or Path.home()/".ecomic"); self.state_dir.mkdir(parents=True,exist_ok=True); self.db=DatabaseManager(self.state_dir/"ecomic.db"); self._dataset_handles: OrderedDict[str, DatasetHandle] = OrderedDict()
 def close(self):
  for handle in self._dataset_handles.values(): handle.connection.close()
  self._dataset_handles.clear(); self.db.close()
 def _session(self,s): return self.db.resume_session(s)
 def _spec(self,s): return json.loads(self._session(s)["domain_specs"][-1]["content_json"])
 def retain_dataset_handle(self,s,handle):
  old=self._dataset_handles.pop(s,None)
  if old is not None and old is not handle: old.connection.close()
  self._dataset_handles[s]=handle
  while len(self._dataset_handles)>MAX_RUNTIME_DATASET_HANDLES:
   _,stale=self._dataset_handles.popitem(last=False); stale.connection.close()
 def _handle(self,s):
  cached=self._dataset_handles.pop(s,None)
  if cached is not None:
   self._dataset_handles[s]=cached; return cached
  row=self.db.connection.execute("SELECT d.original_path FROM datasets d JOIN sessions s ON s.dataset_id=d.dataset_id WHERE s.session_id=?",(s,)).fetchone()
  if row is None: raise KeyError("dataset for session is missing")
  handle=DatasetHandle.open(str(row[0])); self.retain_dataset_handle(s,handle); return handle
 def _rows(self,s):
  h=self._handle(s); return h.materialize_for_experiment(h.columns)
 def _open(self,s):
  if self._session(s)["final_evaluation_revealed"]: raise RuntimeError("FINALIZED: final evaluation has been revealed; research mutations are blocked")
 def create_session(self,path,description=""):
  handle=DatasetHandle.open(path)
  try:
   result=self.create_session_from_handle(handle,description); self.retain_dataset_handle(result["session_id"],handle); return result
  except Exception:
   handle.connection.close(); raise
 def create_session_from_handle(self,handle,description=""):
  rows=handle.materialize_for_experiment(handle.columns); inf=infer_semantics({"path":str(handle.path),"hash":handle.sha256,"columns":handle.columns,"rows":rows},description); c=inf["candidates"]; pick=lambda k:(c.get(k)or[{}])[0]; d,t,cost,e=pick("decision"),pick("target"),pick("cost"),pick("id")
  spec={"domain_name":"unknown","task_type":"binary_classification","entity_id":e.get("column"),"features":[x for x in handle.columns if x not in {d.get("column"),t.get("column"),cost.get("column"),e.get("column")}],"historical_decision":{"column":d.get("column"),"observed_action_values":[],"non_observed_action_values":[],"unknown_action_values":[],"confidence":d.get("confidence",0),"confirmed":False},"outcome":{"column":t.get("column"),"confidence":t.get("confidence",0)},"observation_cost":{"column":cost.get("column"),"proxy":True},"observation_action":{"description":"requires confirmation","reversible":None,"simulatable":None,"confirmed":False},"selection_mechanism":{"type":"unknown","simulated":False},"time":{"decision_time":None,"outcome_time":None},"audit_status":"NEEDS_USER_INPUT"}
  did=self.db.register_dataset(handle.sha256,str(handle.path),handle.format,handle.row_count,len(handle.columns),handle.size_bytes); sid=self.db.create_session(did); schema=handle.profile(); self.db.save_session_metadata(sid,schema,c); self.db.save_domain_spec(sid,spec,False,"NEEDS_USER_INPUT"); self.db.append_event(sid,"load_dataset",{"path":str(handle.path)},"DuckDB DatasetHandle","COMPLETED")
  return {"session_id":sid,"schema":schema,"candidates":c,"domain_spec":spec,"status":"NEEDS_USER_INPUT"}
 def confirm_decision_mapping(self,s,decision_column,observed_values,non_observed_values,**kw):
  self._open(s)
  if not observed_values or not non_observed_values or set(observed_values)&set(non_observed_values): raise ValueError("observed/non-observed values must both be nonempty and disjoint")
  spec=self._spec(s); spec["historical_decision"]={"column":decision_column,"observed_action_values":observed_values,"non_observed_action_values":non_observed_values,"unknown_action_values":[],"confidence":1.,"confirmed":True}
  if kw.get("target_column"): spec["outcome"]["column"]=kw["target_column"]
  if kw.get("cost_column"): spec["observation_cost"]["column"]=kw["cost_column"]
  spec["observation_action"].update({"reversible":kw.get("observation_reversible"),"simulatable":kw.get("observation_simulatable"),"confirmed":kw.get("observation_reversible") is not None and kw.get("observation_simulatable") is not None}); spec["time"]={"decision_time":kw.get("decision_time"),"outcome_time":kw.get("outcome_time")}
  audit=audit_semantics(spec,self._rows(s)); spec["audit_status"]=audit["status"]; self.db.save_confirmation(s,"decision_mapping",{"column":decision_column},decision_column); self.db.save_domain_spec(s,spec,audit["status"] in {"PASS","PASS_WITH_WARNINGS"},audit["status"]); self.db.append_event(s,"confirm_decision_mapping",{"column":decision_column},"human confirmation","COMPLETED")
  return {"session_id":s,"domain_spec":spec,"audit":audit}
 def create_hypothesis(self,s,content): self._open(s); return {"hypothesis_id":self.db.save_hypothesis(s,content)}
 def plan_experiment(self,s,hypothesis_id,policy,budget,rounds): self._open(s); return {"plan_id":self.db.save_plan(s,hypothesis_id,{"policy":policy,"budget":budget,"rounds":rounds})}
 def run_experiment(self,s,plan_id,policy,budget,seed,rounds,progress=None):
  self._open(s); spec=self._spec(s)
  if not(spec["historical_decision"].get("confirmed") and spec["observation_action"].get("confirmed")): raise RuntimeError("NEEDS_USER_INPUT: confirm decision mapping and observation action in TUI first")
  env=DynamicSelectiveLabelEnvironment(self._rows(s),spec,seed=seed); env.reset(total_budget=budget); rid=self.db.save_run(s,plan_id,policy,budget,seed,0); observations=[]
  for i in range(rounds):
   item=env.advance_round(batch_size=max(1,len(env.universe.candidate_ids)//max(1,rounds)),policy=policy,seed=seed+i); observations.append(item)
   if progress: progress({"type":"experiment_progress","session_id":s,"run_id":rid,"round":i+1,"total_rounds":rounds,"status":item.get("status","COMPLETED")})
   if item["status"]=="EXHAUSTED" and item.get("candidate_remaining", 0) == 0: break
  visible_observations=[{"status":item.get("status"),"revealed_label_count":item.get("revealed_label_count",0),"predicted_cost":item.get("predicted_cost",0),"remaining_budget":item.get("remaining_budget"),"round_index":item.get("round_index"),"candidate_remaining":item.get("candidate_remaining")} for item in observations]
  artifact_dir=self.state_dir/"agent_runs"/s; artifact_dir.mkdir(parents=True,exist_ok=True); artifact=artifact_dir/f"{rid}.json"
  artifact.write_text(json.dumps({"policy":policy,"budget":budget,"seed":seed,"rounds":len(observations),"observations":visible_observations,"raw_observations":observations},ensure_ascii=False),encoding="utf8")
  self.db.finish_run(rid,status="COMPLETED",round_end=len(observations),artifact_path=str(artifact)); self.db.append_event(s,"run_experiment",{"run_id":rid,"rounds":len(observations)},"DynamicSelectiveLabelEnvironment","COMPLETED")
  final_state=env.observe_state(); feedback_count=sum(int(item.get("revealed_label_count",0) or 0) for item in visible_observations)
  return {"run_id":rid,"status":"COMPLETED","rounds":len(observations),"visible_summary":{"feedback_count":feedback_count,"remaining_budget":final_state.get("remaining_budget"),"visible_label_count":final_state.get("visible_label_count"),"candidate_remaining":final_state.get("candidate_remaining")},"artifact_ref":str(artifact)}
 def lock_research_plan(self,s,plan_id): self.db.lock_plan(s,plan_id); return {"status":"LOCKED"}
 def finalize_evaluation(self,s,run_id):
  row=self.db.connection.execute("SELECT artifact_path FROM experiment_runs WHERE run_id=? AND session_id=?",(run_id,s)).fetchone()
  if not row: raise KeyError("run not found in session")
  recipe=json.loads(Path(row[0]).read_text(encoding="utf8")); env=DynamicSelectiveLabelEnvironment(self._rows(s),self._spec(s),seed=int(recipe["seed"])); env.reset(total_budget=float(recipe["budget"]))
  for i in range(int(recipe["rounds"])):
   try: env.advance_round(batch_size=max(1,len(env.universe.candidate_ids)//max(1,int(recipe["rounds"]))),policy=recipe["policy"],seed=int(recipe["seed"])+i)
   except Exception: break
  env._finished=False; result=env.finalize(); self.db.save_final_evaluation(s,run_id,result["metrics"]); self.db.append_event(s,"finalize_evaluation",{"run_id":run_id},"internal oracle evaluator","COMPLETED"); return result
 def chart_data(self,s):
  state=self._session(s); all_runs=[]; all_trajectory=[]
  for row in state["runs"]:
   observations=[]
   try: observations=json.loads(Path(row["artifact_path"]).read_text(encoding="utf8")).get("observations",[]) if row.get("artifact_path") else []
   except (OSError,json.JSONDecodeError): observations=[]
   cumulative=0
   for index,observation in enumerate(observations,1):
    cumulative+=int(observation.get("revealed_label_count",observation.get("feedback_count",0)) or 0)
    all_trajectory.append({"run_id":row["run_id"],"policy":row["policy"],"round":index,"feedback_count":cumulative,"budget":row["budget"]})
   spent=sum(float(observation.get("predicted_cost",0) or 0) for observation in observations); budget=float(row["budget"] or 0)
   all_runs.append({"run_id":row["run_id"],"policy":row["policy"],"budget":budget,"rounds":row["round_end"] or 0,"feedback_count":cumulative,"budget_utilization":min(1.0,spent/budget) if budget else 0.0,"status":row["status"]})
  feedback_trajectory,trajectory_downsampled=_downsample_chart_points(all_trajectory)
  all_hypotheses=[{"hypothesis_id":row["hypothesis_id"],"order":index,"content":row["content"]} for index,row in enumerate(state["hypotheses"],1)]
  hypotheses,hypothesis_downsampled=_downsample_chart_points(all_hypotheses,500)
  runs,runs_downsampled=_downsample_chart_points(all_runs,500)
  result={"session_id":s,"research_mode":not bool(state["final_evaluation_revealed"]),"runs":runs,"feedback_trajectory":feedback_trajectory,"feedback_trajectory_total_points":len(all_trajectory),"feedback_trajectory_downsampled":trajectory_downsampled,"chart_point_limit":MAX_CHART_POINTS,"hypothesis_timeline":hypotheses,"hypothesis_timeline_total_items":len(all_hypotheses),"hypothesis_timeline_downsampled":hypothesis_downsampled,"runs_total":len(all_runs),"runs_downsampled":runs_downsampled,"policy_comparison":[{"policy":row["policy"],"budget":row["budget"],"rounds":row["rounds"],"feedback_count":row["feedback_count"],"budget_utilization":row["budget_utilization"]} for row in runs],"final_metrics":None}
  if state["final_evaluation_revealed"]:
   row=self.db.connection.execute("SELECT metrics_json FROM final_evaluations WHERE session_id=?",(s,)).fetchone()
   result["final_metrics"]=json.loads(row[0]) if row else {}
  return result
 def get_session(self,s):
  return self._session(s)
 def observe_state(self,s):
  x=self._session(s); return {"session_id":s,"status":x["status"],"final_evaluation_revealed":bool(x["final_evaluation_revealed"]),"runs":len(x["runs"]),"hypotheses":len(x["hypotheses"]),"plans":len(x["plans"])}
