"""Run the required non-credit benchmark matrix in explicit REPLAY MODE.

Source: UCI Wisconsin Diagnostic Breast Cancer dataset, bundled by scikit-learn.
It is a real public structured non-credit dataset; the decision mechanism below
is simulated solely to validate the selective-label protocol, not to claim a
historical clinical selection process.
"""
from __future__ import annotations
import csv, json
from pathlib import Path
from sklearn.datasets import load_breast_cancer
from agent_backend.environment.dynamic import DynamicSelectiveLabelEnvironment

ROOT=Path(__file__).parents[1]; OUT=ROOT/"benchmarks"/"results"; OUT.mkdir(parents=True,exist_ok=True)
def main():
 data=load_breast_cancer(); rows=[]
 for i,(features,label) in enumerate(zip(data.data,data.target)):
  rows.append({"feature_0":float(features[0]),"feature_1":float(features[1]),"decision":"observed" if features[0]>=float(data.data[:,0].mean()) else "hidden","label":int(label),"cost":1+float(features[1]>data.data[:,1].mean()),"decision_time":f"2020-01-{i%28+1:02d}","outcome_time":f"2020-02-{i%28+1:02d}"})
 spec={"domain_name":"medical-diagnostic-replay","features":["feature_0","feature_1"],"historical_decision":{"column":"decision","observed_action_values":["observed"],"non_observed_action_values":["hidden"],"unknown_action_values":[],"confidence":1.0,"confirmed":True},"outcome":{"column":"label"},"observation_cost":{"column":"cost","proxy":True},"observation_action":{"confirmed":True,"reversible":True,"simulatable":True},"selection_mechanism":{"type":"simulated-replay","simulated":True,"mode":"REPLAY MODE"},"time":{"decision_time":"decision_time","outcome_time":"outcome_time"}}
 records=[]
 for seed in range(5):
  for budget in (30.,60.,90.):
   for policy in ("Random","CountOnly-MinCost","LRBE-Uncertainty"):
    env=DynamicSelectiveLabelEnvironment(rows,spec,seed=seed); env.reset(total_budget=budget)
    for round_index in range(5):
     result=env.advance_round(batch_size=30,policy=policy,seed=seed+round_index)
     if result["status"]=="EXHAUSTED": break
    final=env.finalize(); metrics=final.get("metrics",{})
    records.append({"dataset":"UCI_WDBC","mode":"REPLAY_MODE_SIMULATION","seed":seed,"budget":budget,"policy":policy,"feedback_count":env.observe_state()["visible_label_count"],"remaining_budget":env.observe_state()["remaining_budget"],"roc_auc":metrics.get("roc_auc"),"average_precision":metrics.get("average_precision")})
 with (OUT/"uci_wdbc_replay_matrix.csv").open("w",newline="",encoding="utf8") as f: csv.DictWriter(f,fieldnames=records[0]).writeheader(); csv.DictWriter(f,fieldnames=records[0]).writerows(records)
 (OUT/"uci_wdbc_replay_metadata.json").write_text(json.dumps({"source":"UCI Wisconsin Diagnostic Breast Cancer via sklearn.datasets.load_breast_cancer","license":"UCI dataset terms; verify before competition redistribution","domain":"medical diagnosis (non-credit)","decision_semantics":"synthetic replay threshold; not historical clinical workflow","visibility_semantics":"private evaluator retains labels; protocol hides candidate labels","simulation":True,"matrix":"5 seeds × 3 budgets × 3 policies"},ensure_ascii=False,indent=2),encoding="utf8")
if __name__=="__main__": main()
