import csv
import tempfile
import unittest
from pathlib import Path
from agent_backend.rpc import dispatch

class RuntimeRpcTests(unittest.TestCase):
 def _csv(self,root):
  path=root/"data.csv"
  with path.open("w",newline="",encoding="utf-8") as h:
   w=csv.DictWriter(h,fieldnames=["x","decision","label","cost","decision_time","outcome_time"]); w.writeheader()
   for i in range(45): w.writerow({"x":i,"decision":"yes" if i%3==0 else "no","label":int(i%5==0),"cost":1+i%2,"decision_time":f"2026-01-{i%20+1:02d}","outcome_time":f"2026-02-{i%20+1:02d}"})
  return path
 def test_rpc_uses_runtime_and_final_metrics_cannot_be_injected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); state=str(root/"state"); x=dispatch("load_dataset",{"path":str(self._csv(root)),"state_dir":state}); s=x["session_id"]
   y=dispatch("confirm_decision_mapping",{"state_dir":state,"session_id":s,"decision_column":"decision","observed_values":["yes"],"non_observed_values":["no"],"target_column":"label","cost_column":"cost","decision_time":"decision_time","outcome_time":"outcome_time","observation_reversible":True,"observation_simulatable":True}); self.assertIn(y["audit"]["status"],{"PASS","PASS_WITH_WARNINGS"})
   h=dispatch("create_hypothesis",{"state_dir":state,"session_id":s,"content":"LRBE is worth testing"}); p=dispatch("plan_experiment",{"state_dir":state,"session_id":s,"hypothesis_id":h["hypothesis_id"],"policy":"LRBE-Uncertainty","budget":12,"rounds":2}); r=dispatch("run_experiment",{"state_dir":state,"session_id":s,"plan_id":p["plan_id"],"policy":"LRBE-Uncertainty","budget":12,"seed":4,"rounds":2}); self.assertTrue(r["run_id"])
   dispatch("lock_research_plan",{"state_dir":state,"session_id":s,"plan_id":p["plan_id"]})
   with self.assertRaisesRegex(ValueError,"metrics are evaluator-owned"): dispatch("finalize_evaluation",{"state_dir":state,"session_id":s,"run_id":r["run_id"],"metrics":{"roc_auc":1}})
   final=dispatch("finalize_evaluation",{"state_dir":state,"session_id":s,"run_id":r["run_id"]}); self.assertIn(final["status"],{"FINAL_EVALUATION_REVEALED","INCONCLUSIVE"})
   with self.assertRaisesRegex(RuntimeError,"FINALIZED"): dispatch("run_experiment",{"state_dir":state,"session_id":s,"plan_id":p["plan_id"],"policy":"Random","budget":2,"seed":5,"rounds":1})

if __name__=="__main__": unittest.main()
