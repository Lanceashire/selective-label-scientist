import csv
import json
import tempfile
import unittest
from pathlib import Path

from agent_backend.rpc import dispatch


class SessionReportAndConfirmationTests(unittest.TestCase):
    def _dataset(self, root: Path) -> Path:
        path = root / "selection.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["feature", "decision", "label", "cost", "decision_time", "outcome_time"])
            writer.writeheader()
            for index in range(72):
                writer.writerow({"feature": index, "decision": "observed" if index % 3 == 0 else "hidden", "label": index % 2, "cost": 1, "decision_time": "2026-01-01", "outcome_time": "2026-01-02"})
        return path

    def test_confirmations_version_domain_spec_and_export_sqlite_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = str(root / "state")
            session = dispatch("load_dataset", {"path": str(self._dataset(root)), "state_dir": state})["session_id"]
            initial = dispatch("observe_state", {"session_id": session, "state_dir": state})
            self.assertEqual(initial["runs"], 0)
            decision = dispatch("confirm_decision_mapping", {"session_id": session, "state_dir": state, "decision_column": "decision", "observed_values": ["observed"], "non_observed_values": ["hidden"], "target_column": "label", "cost_column": "cost", "decision_time": "decision_time", "outcome_time": "outcome_time"})
            self.assertFalse(decision["domain_spec"]["observation_action"]["confirmed"])
            action = dispatch("confirm_observation_action", {"session_id": session, "state_dir": state, "reversible": True, "simulatable": True, "description": "offline replay only"})
            self.assertTrue(action["domain_spec"]["observation_action"]["confirmed"])
            listing = dispatch("list_sessions", {"state_dir": state})["sessions"]
            self.assertEqual(listing[0]["session_id"], session)
            dispatch("set_research_question", {"session_id": session, "state_dir": state, "question": "比较低预算下的策略反馈效率"})
            hypothesis = dispatch("create_hypothesis", {"session_id": session, "state_dir": state, "content": "test uncertainty policy"})
            plan = dispatch("plan_experiment", {"session_id": session, "state_dir": state, "hypothesis_id": hypothesis["hypothesis_id"], "policy": "LRBE-Uncertainty", "budget": 8, "rounds": 2})
            run = dispatch("run_experiment", {"session_id": session, "state_dir": state, "plan_id": plan["plan_id"], "policy": "LRBE-Uncertainty", "budget": 8, "rounds": 2, "seed": 11})
            restored = dispatch("resume_next_round", {"session_id": session, "state_dir": state, "run_id": run["run_id"]})
            self.assertEqual(restored["mode"], "DETERMINISTIC_REPLAY_RESTORE")
            dispatch("lock_run_plan", {"session_id": session, "state_dir": state, "run_id": run["run_id"]})
            dispatch("finalize_evaluation", {"session_id": session, "state_dir": state, "run_id": run["run_id"]})
            report = dispatch("generate_report", {"session_id": session, "state_dir": state})
            self.assertTrue(Path(report["final_report"]).is_file())
            self.assertTrue(Path(report["manifest"]).is_file())
            self.assertTrue(Path(report["actions"]).is_file())
            manifest = json.loads(Path(report["manifest"]).read_text(encoding="utf-8"))
            self.assertTrue(manifest["final_evaluation_revealed"])
            viewed = dispatch("read_report", {"session_id": session, "state_dir": state})
            self.assertIn("比较低预算下的策略反馈效率", viewed["content"])
            for heading in ("研究问题", "DomainSpec", "假设与修订", "实验与可见证据", "Oracle Final Evaluation", "Claim Guard", "限制", "Reproduction Info"): self.assertIn(heading, viewed["content"])
            exported = root / "exported-report.md"
            self.assertEqual(dispatch("export_report", {"session_id": session, "state_dir": state, "destination": str(exported)})["status"], "EXPORTED")
            self.assertEqual(exported.read_text(encoding="utf-8"), viewed["content"])


if __name__ == "__main__":
    unittest.main()
