import csv
import tempfile
import unittest
from pathlib import Path

from agent_backend.rpc import dispatch
from agent_backend.runtime import ResearchRuntime

class DesktopStreamProgressTests(unittest.TestCase):
    def test_five_real_rounds_emit_five_ordered_progress_events(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / "five_rounds.csv"; state = root / "state"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["x", "decision", "label", "cost", "decision_time", "outcome_time"]); writer.writeheader()
                for index in range(500): writer.writerow({"x": index, "decision": 1 if index % 20 == 0 else 0, "label": int(index % 5 == 0), "cost": 1, "decision_time": "2026-01-01", "outcome_time": "2026-02-01"})
            session = dispatch("load_dataset", {"path": str(source), "state_dir": str(state)})["session_id"]
            dispatch("confirm_decision_mapping", {"state_dir": str(state), "session_id": session, "decision_column": "decision", "observed_values": ["1"], "non_observed_values": ["0"], "target_column": "label", "cost_column": "cost", "decision_time": "decision_time", "outcome_time": "outcome_time"})
            dispatch("confirm_observation_action", {"state_dir": str(state), "session_id": session, "reversible": True, "simulatable": True, "description": "offline replay"})
            hypothesis = dispatch("create_hypothesis", {"state_dir": str(state), "session_id": session, "content": "five-round progress verification"})
            plan = dispatch("plan_experiment", {"state_dir": str(state), "session_id": session, "hypothesis_id": hypothesis["hypothesis_id"], "policy": "Random", "budget": 1000, "rounds": 5})
            events = []; runtime = ResearchRuntime(state)
            try:
                result = runtime.run_experiment(session, plan["plan_id"], "Random", 1000, 9, 5, progress=events.append)
            finally:
                runtime.close()
            self.assertTrue(result["run_id"])
            self.assertEqual([event["round"] for event in events], [1, 2, 3, 4, 5], events)
            self.assertTrue(all(event["total_rounds"] == 5 and event["session_id"] == session for event in events))

if __name__ == "__main__": unittest.main()