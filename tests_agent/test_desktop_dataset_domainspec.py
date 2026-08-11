import csv
import tempfile
import unittest
from pathlib import Path

from agent_backend.rpc import dispatch
from agent_backend.persistence.database import DatabaseManager


class DesktopDatasetDomainSpecTests(unittest.TestCase):
    def make_csv(self, root: Path) -> Path:
        path = root / "desktop_selection.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["feature", "decision", "outcome", "cost", "decision_time", "outcome_time"])
            writer.writeheader()
            for index in range(80):
                writer.writerow({"feature": index, "decision": "reviewed" if index % 3 == 0 else "hidden", "outcome": index % 2, "cost": 1, "decision_time": "2026-01-01", "outcome_time": "2026-01-02"})
        return path

    def test_desktop_preview_is_bounded_and_confirmation_creates_three_spec_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            root, state = Path(directory), Path(directory) / "state"
            path = self.make_csv(root)
            preview = dispatch("inspect_dataset", {"path": str(path)})
            self.assertEqual(preview["schema"]["row_count"], 80)
            self.assertEqual(preview["schema"]["column_count"], 6)
            self.assertLessEqual(len(preview["sample"]), 50)
            self.assertIn("sha256", preview)
            session = dispatch("load_dataset", {"path": str(path), "state_dir": str(state)})["session_id"]
            hypothesis = dispatch("create_hypothesis", {"session_id": session, "state_dir": str(state), "content": "must remain gated"})
            plan = dispatch("plan_experiment", {"session_id": session, "state_dir": str(state), "hypothesis_id": hypothesis["hypothesis_id"], "policy": "Random", "budget": 5, "rounds": 1})
            with self.assertRaisesRegex(RuntimeError, "NEEDS_USER_INPUT"):
                dispatch("run_experiment", {"session_id": session, "state_dir": str(state), "plan_id": plan["plan_id"], "policy": "Random", "budget": 5, "rounds": 1, "seed": 1})
            dispatch("confirm_decision_mapping", {"session_id": session, "state_dir": str(state), "decision_column": "decision", "observed_values": ["reviewed"], "non_observed_values": ["hidden"], "target_column": "outcome", "cost_column": "cost", "decision_time": "decision_time", "outcome_time": "outcome_time"})
            with self.assertRaisesRegex(RuntimeError, "NEEDS_USER_INPUT"):
                dispatch("run_experiment", {"session_id": session, "state_dir": str(state), "plan_id": plan["plan_id"], "policy": "Random", "budget": 5, "rounds": 1, "seed": 1})
            dispatch("confirm_observation_action", {"session_id": session, "state_dir": str(state), "reversible": True, "simulatable": True, "description": "offline replay"})
            db = DatabaseManager(state / "ecomic.db")
            try:
                versions = db.connection.execute("SELECT version, confirmed FROM domain_specs WHERE session_id=? ORDER BY version", (session,)).fetchall()
                self.assertEqual([(row[0], row[1]) for row in versions], [(1, 0), (2, 0), (3, 1)])
            finally:
                db.close()
            run = dispatch("run_experiment", {"session_id": session, "state_dir": str(state), "plan_id": plan["plan_id"], "policy": "Random", "budget": 5, "rounds": 1, "seed": 1})
            self.assertTrue(run["run_id"])


if __name__ == "__main__":
    unittest.main()
