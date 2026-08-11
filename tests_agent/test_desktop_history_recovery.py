import csv
import tempfile
import unittest
from pathlib import Path

from agent_backend.rpc import dispatch


class DesktopHistoryRecoveryTests(unittest.TestCase):
    def _data(self, root: Path) -> Path:
        path = root / "history.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["feature", "decision", "label", "cost"])
            writer.writeheader()
            for index in range(80):
                writer.writerow({"feature": index, "decision": "1" if index % 2 else "0", "label": index % 3 == 0, "cost": 1})
        return path

    def test_list_resume_and_explicit_delete_keep_the_same_session_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._data(root)
            state = str(root / "state")
            session = dispatch("load_dataset", {"state_dir": state, "path": str(source)})["session_id"]
            dispatch("confirm_decision_mapping", {"state_dir": state, "session_id": session, "decision_column": "decision", "observed_values": ["1"], "non_observed_values": ["0"], "target_column": "label", "cost_column": "cost"})
            dispatch("confirm_observation_action", {"state_dir": state, "session_id": session, "reversible": True, "simulatable": True, "description": "offline replay"})
            hypothesis = dispatch("create_hypothesis", {"state_dir": state, "session_id": session, "content": "history H1"})
            plan = dispatch("plan_experiment", {"state_dir": state, "session_id": session, "hypothesis_id": hypothesis["hypothesis_id"], "policy": "Random", "budget": 12, "rounds": 3})
            run = dispatch("run_experiment", {"state_dir": state, "session_id": session, "plan_id": plan["plan_id"], "policy": "Random", "budget": 12, "seed": 17, "rounds": 3})

            history = dispatch("list_sessions", {"state_dir": state})["sessions"]
            card = next(item for item in history if item["session_id"] == session)
            self.assertEqual(card["dataset"], "history.csv")
            self.assertEqual(card["hypothesis_count"], 1)
            self.assertEqual(card["run_count"], 1)
            self.assertIn("updated_at", card)

            restored = dispatch("resume_session", {"state_dir": state, "session_id": session})
            self.assertEqual(restored["session_id"], session)
            self.assertEqual(restored["domain_spec"]["historical_decision"]["column"], "decision")
            self.assertEqual(restored["snapshot"]["round_index"], 3)
            replay = dispatch("resume_next_round", {"state_dir": state, "session_id": session, "run_id": run["run_id"]})
            self.assertEqual(replay["next_round"], restored["snapshot"]["round_index"])
            self.assertEqual(replay["remaining_budget"], restored["snapshot"]["state"]["remaining_budget"])

            self.assertEqual(dispatch("delete_session", {"state_dir": state, "session_id": session})["status"], "DELETED")
            self.assertTrue(source.exists(), "deleting a Session must not delete the user's source dataset")
            self.assertNotIn(session, [item["session_id"] for item in dispatch("list_sessions", {"state_dir": state})["sessions"]])


if __name__ == "__main__":
    unittest.main()