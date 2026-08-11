import csv
import tempfile
import unittest
from pathlib import Path

from agent_backend.rpc import dispatch


class RuntimeRpcTests(unittest.TestCase):
    def _csv(self, root):
        path = root / "data.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["x", "decision", "label", "cost", "decision_time", "outcome_time"])
            writer.writeheader()
            for index in range(45):
                writer.writerow({"x": index, "decision": "yes" if index % 3 == 0 else "no", "label": int(index % 5 == 0), "cost": 1 + index % 2, "decision_time": f"2026-01-{index % 20 + 1:02d}", "outcome_time": f"2026-02-{index % 20 + 1:02d}"})
        return path

    def test_rpc_uses_runtime_and_final_metrics_cannot_be_injected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = str(root / "state")
            created = dispatch("load_dataset", {"path": str(self._csv(root)), "state_dir": state})
            session = created["session_id"]
            decision = dispatch("confirm_decision_mapping", {"state_dir": state, "session_id": session, "decision_column": "decision", "observed_values": ["yes"], "non_observed_values": ["no"], "target_column": "label", "cost_column": "cost", "decision_time": "decision_time", "outcome_time": "outcome_time"})
            self.assertEqual(decision["next_step"], "confirm_observation_action")
            action = dispatch("confirm_observation_action", {"state_dir": state, "session_id": session, "reversible": True, "simulatable": True, "description": "approved offline replay"})
            self.assertIn(action["audit"]["status"], {"PASS", "PASS_WITH_WARNINGS"})
            hypothesis = dispatch("create_hypothesis", {"state_dir": state, "session_id": session, "content": "LRBE is worth testing"})
            plan = dispatch("plan_experiment", {"state_dir": state, "session_id": session, "hypothesis_id": hypothesis["hypothesis_id"], "policy": "LRBE-Uncertainty", "budget": 12, "rounds": 2})
            run = dispatch("run_experiment", {"state_dir": state, "session_id": session, "plan_id": plan["plan_id"], "policy": "LRBE-Uncertainty", "budget": 12, "seed": 4, "rounds": 2})
            self.assertTrue(run["run_id"])
            chart_before = dispatch("chart_data", {"state_dir": state, "session_id": session})
            self.assertTrue(chart_before["research_mode"])
            self.assertIsNone(chart_before["final_metrics"])
            self.assertNotIn("roc_auc", str(chart_before).lower())
            self.assertNotIn("average_precision", str(chart_before).lower())
            self.assertNotIn("selected_ids", str(chart_before).lower())
            self.assertIn("feedback_trajectory", chart_before)
            self.assertIn("hypothesis_timeline", chart_before)
            self.assertEqual(chart_before["hypothesis_timeline"][0]["content"], "LRBE is worth testing")
            self.assertIn("feedback_count", chart_before["policy_comparison"][0])
            self.assertIn("budget_utilization", chart_before["policy_comparison"][0])
            snapshot = dispatch("get_session", {"state_dir": state, "session_id": session})
            self.assertEqual(snapshot["session_id"], session)
            self.assertEqual(len(snapshot["hypotheses"]), 1)
            self.assertEqual(len(snapshot["plans"]), 1)
            self.assertEqual(len(snapshot["runs"]), 1)
            dispatch("lock_research_plan", {"state_dir": state, "session_id": session, "plan_id": plan["plan_id"]})
            with self.assertRaisesRegex(ValueError, "metrics are evaluator-owned"):
                dispatch("finalize_evaluation", {"state_dir": state, "session_id": session, "run_id": run["run_id"], "metrics": {"roc_auc": 1}})
            final = dispatch("finalize_evaluation", {"state_dir": state, "session_id": session, "run_id": run["run_id"]})
            self.assertIn(final["status"], {"FINAL_EVALUATION_REVEALED", "INCONCLUSIVE"})
            chart_after = dispatch("chart_data", {"state_dir": state, "session_id": session})
            self.assertFalse(chart_after["research_mode"])
            self.assertIsNotNone(chart_after["final_metrics"])
            with self.assertRaisesRegex(RuntimeError, "FINALIZED"):
                dispatch("run_experiment", {"state_dir": state, "session_id": session, "plan_id": plan["plan_id"], "policy": "Random", "budget": 2, "seed": 5, "rounds": 1})


if __name__ == "__main__":
    unittest.main()
