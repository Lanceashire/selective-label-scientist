"""Single official runtime for all research entry points."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from ..domains.semantic_auditor import audit_semantics
from ..environment.dynamic import DynamicSelectiveLabelEnvironment
from ..ingestion.handle import DatasetHandle
from ..ingestion.semantic_features import infer_semantics
from ..persistence.database import DatabaseManager

class ResearchRuntime:
 def __init__(self,state_dir: str|Path|None=None):
  self.state_dir=Path(state_dir or Path.home()/".ecomic"); self.state_dir.mkdir(parents=True,exist_ok=True); self.db=DatabaseManager(self.state_dir/"ecomic.db")
 def close(self): self.db.close()
 def _session(self,s): return self.db.resume_session(s)
 def _spec(self,s): return json.loads(self._session(s)["domain_specs"][-1]["content_json"])
 def _rows(self,s):
  row=self.db.connection.execute("SELECT d.original_path FROM datasets d JOIN sessions s ON s.dataset_id=d.dataset_id WHERE s.session_id=?",(s,)).fetchone()
  h=DatasetHandle.open(str(row[0])); return h.materialize_for_experiment(h.columns)
 def _open(self,s):
  if self._session(s)["final_evaluation_revealed"]: raise RuntimeError("FINALIZED: final evaluation has been revealed; research mutations are blocked")
 def create_session(self,path,description=""):
  h=DatasetHandle.open(path); rows=h.materialize_for_experiment(h.columns); inf=infer_semantics({"path":str(h.path),"hash":h.sha256,"columns":h.columns,"rows":rows},description); c=inf["candidates"]; pick=lambda k:(c.get(k)or[{}])[0]; d,t,cost,e=pick("decision"),pick("target"),pick("cost"),pick("id")
  spec={"domain_name":"unknown","task_type":"binary_classification","entity_id":e.get("column"),"features":[x for x in h.columns if x not in {d.get("column"),t.get("column"),cost.get("column"),e.get("column")}],"historical_decision":{"column":d.get("column"),"observed_action_values":[],"non_observed_action_values":[],"unknown_action_values":[],"confidence":d.get("confidence",0),"confirmed":False},"outcome":{"column":t.get("column"),"confidence":t.get("confidence",0)},"observation_cost":{"column":cost.get("column"),"proxy":True},"observation_action":{"description":"requires confirmation","reversible":None,"simulatable":None,"confirmed":False},"selection_mechanism":{"type":"unknown","simulated":False},"time":{"decision_time":None,"outcome_time":None},"audit_status":"NEEDS_USER_INPUT"}
  did=self.db.register_dataset(h.sha256,str(h.path),h.format,h.row_count,len(h.columns),h.size_bytes); sid=self.db.create_session(did); self.db.save_domain_spec(sid,spec,False,"NEEDS_USER_INPUT"); self.db.append_event(sid,"load_dataset",{"path":str(h.path)},"DuckDB DatasetHandle","COMPLETED")
  return {"session_id":sid,"schema":h.profile(),"candidates":c,"domain_spec":spec,"status":"NEEDS_USER_INPUT"}
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
 def run_experiment(self,s,plan_id,policy,budget,seed,rounds):
  self._open(s); spec=self._spec(s)
  if not(spec["historical_decision"].get("confirmed") and spec["observation_action"].get("confirmed")): raise RuntimeError("NEEDS_USER_INPUT: confirm decision mapping and observation action in TUI first")
  env=DynamicSelectiveLabelEnvironment(self._rows(s),spec,seed=seed); env.reset(total_budget=budget); rid=self.db.save_run(s,plan_id,policy,budget,seed,0); obs=[]
  for i in range(rounds):
   x=env.advance_round(batch_size=max(1,len(env.universe.candidate_ids)//max(1,rounds)),policy=policy,seed=seed+i); obs.append(x)
   if x["status"]=="EXHAUSTED": break
  p=self.state_dir/"agent_runs"/s; p.mkdir(parents=True,exist_ok=True); artifact=p/f"{rid}.json"; artifact.write_text(json.dumps({"policy":policy,"budget":budget,"seed":seed,"rounds":len(obs)}),encoding="utf8"); self.db.finish_run(rid,status="COMPLETED",round_end=len(obs),artifact_path=str(artifact)); self.db.append_event(s,"run_experiment",{"run_id":rid},"DynamicSelectiveLabelEnvironment","COMPLETED")
  return {"run_id":rid,"observations":obs,"state":env.observe_state()}
 def lock_research_plan(self,s,plan_id): self.db.lock_plan(s,plan_id); return {"status":"LOCKED"}
 def finalize_evaluation(self,s,run_id):
  row=self.db.connection.execute("SELECT artifact_path FROM experiment_runs WHERE run_id=? AND session_id=?",(run_id,s)).fetchone()
  if not row: raise KeyError("run not found in session")
  recipe=json.loads(Path(row[0]).read_text(encoding="utf8")); env=DynamicSelectiveLabelEnvironment(self._rows(s),self._spec(s),seed=int(recipe["seed"])); env.reset(total_budget=float(recipe["budget"]))
  for i in range(int(recipe["rounds"])):
   try: env.advance_round(batch_size=max(1,len(env.universe.candidate_ids)//max(1,int(recipe["rounds"]))),policy=recipe["policy"],seed=int(recipe["seed"])+i)
   except Exception: break
  env._finished=False; result=env.finalize(); self.db.save_final_evaluation(s,run_id,result["metrics"]); self.db.append_event(s,"finalize_evaluation",{"run_id":run_id},"internal oracle evaluator","COMPLETED"); return result
 def observe_state(self,s):
  x=self._session(s); return {"session_id":s,"status":x["status"],"final_evaluation_revealed":bool(x["final_evaluation_revealed"]),"runs":len(x["runs"]),"hypotheses":len(x["hypotheses"]),"plans":len(x["plans"])}
