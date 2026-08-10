import csv
import tempfile
import unittest
from pathlib import Path

from agent_backend.rpc import dispatch


class AgentFollowupRuntimeTests(unittest.TestCase):
    def _dataset(self, root: Path) -> Path:
        path = root / "followup.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["feature", "decision", "label", "cost", "decision_time", "outcome_time"])
            writer.writeheader()
            for index in range(75):
                writer.writerow({"feature": index, "decision": "reviewed" if index % 3 == 0 else "not_reviewed", "label": index % 2, "cost": 1 + index % 2, "decision_time": "2026-01-01", "outcome_time": "2026-01-02"})
        return path

    def test_followup_tools_share_runtime_and_keep_oracle_hidden(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = str(root / "state")
            session = dispatch("load_dataset", {"path": str(self._dataset(root)), "state_dir": state})["session_id"]
            dispatch("confirm_decision_mapping", {"state_dir": state, "session_id": session, "decision_column": "decision", "observed_values": ["reviewed"], "non_observed_values": ["not_reviewed"], "target_column": "label", "cost_column": "cost", "decision_time": "decision_time", "outcome_time": "outcome_time"})
            dispatch("confirm_observation_action", {"state_dir": state, "session_id": session, "reversible": True, "simulatable": True, "description": "offline replay"})
            audit = dispatch("audit_environment", {"state_dir": state, "session_id": session})
            self.assertNotIn("oracle", str(audit).lower())
            parent = dispatch("create_hypothesis", {"state_dir": state, "session_id": session, "content": "Initial uncertainty hypothesis"})
            revised = dispatch("revise_hypothesis", {"state_dir": state, "session_id": session, "parent_hypothesis_id": parent["hypothesis_id"], "content": "Follow-up: repeat across fresh seeds"})
            plan_a = dispatch("plan_experiment", {"state_dir": state, "session_id": session, "hypothesis_id": parent["hypothesis_id"], "policy": "Random", "budget": 10, "rounds": 2})
            plan_b = dispatch("plan_experiment", {"state_dir": state, "session_id": session, "hypothesis_id": revised["hypothesis_id"], "policy": "LRBE-Uncertainty", "budget": 10, "rounds": 2})
            run_a = dispatch("run_experiment", {"state_dir": state, "session_id": session, "plan_id": plan_a["plan_id"], "policy": "Random", "budget": 10, "seed": 2, "rounds": 2})
            run_b = dispatch("run_experiment", {"state_dir": state, "session_id": session, "plan_id": plan_b["plan_id"], "policy": "LRBE-Uncertainty", "budget": 10, "seed": 3, "rounds": 2})
            comparison = dispatch("compare_visible_evidence", {"state_dir": state, "session_id": session, "run_ids": [run_a["run_id"], run_b["run_id"]]})
            self.assertEqual(comparison["comparison_scope"], "RESEARCH_VISIBLE_ONLY")
            self.assertEqual(len(comparison["runs"]), 2)
            self.assertNotIn("roc_auc", str(comparison))
            with self.assertRaises(KeyError):
                dispatch("revise_hypothesis", {"state_dir": state, "session_id": session, "parent_hypothesis_id": "hyp_missing", "content": "invalid"})


if __name__ == "__main__":
    unittest.main()
