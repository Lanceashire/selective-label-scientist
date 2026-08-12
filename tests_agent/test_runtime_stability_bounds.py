from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_backend.ingestion.handle import DatasetHandle
from agent_backend.rpc import dispatch
from agent_backend.runtime import ResearchRuntime


class RuntimeStabilityBoundsTests(unittest.TestCase):
    def dataset(self, root: Path) -> Path:
        path = root / "stability.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["feature", "decision", "label", "cost", "decision_time", "outcome_time"],
            )
            writer.writeheader()
            for index in range(240):
                writer.writerow(
                    {
                        "feature": index,
                        "decision": "reviewed" if index % 4 == 0 else "hidden",
                        "label": int(index % 5 == 0),
                        "cost": 1,
                        "decision_time": "2026-01-01",
                        "outcome_time": "2026-02-01",
                    }
                )
        return path

    @staticmethod
    def confirm(runtime: ResearchRuntime, session_id: str) -> str:
        runtime.confirm_decision_mapping(
            session_id,
            "decision",
            ["reviewed"],
            ["hidden"],
            target_column="label",
            cost_column="cost",
            decision_time="decision_time",
            outcome_time="outcome_time",
        )
        runtime.confirm_observation_action(
            session_id,
            reversible=True,
            simulatable=True,
            description="offline replay",
        )
        return runtime.create_hypothesis(session_id, "bounded-result hypothesis")["hypothesis_id"]

    def test_session_runtime_reuses_its_loaded_dataset_handle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = ResearchRuntime(root / "state")
            try:
                session = runtime.create_session(self.dataset(root))["session_id"]
                with patch("agent_backend.runtime.service.DatasetHandle.open", wraps=DatasetHandle.open) as reopen:
                    self.confirm(runtime, session)
                self.assertEqual(reopen.call_count, 0, "confirmed session work must reuse the session-scoped DuckDB handle")
            finally:
                runtime.close()

    def test_experiment_response_is_compact_and_chart_points_are_capped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = str(root / "state")
            source = self.dataset(root)
            session = dispatch("load_dataset", {"path": str(source), "state_dir": state})["session_id"]
            runtime = ResearchRuntime(state)
            try:
                hypothesis_id = self.confirm(runtime, session)
                plan_id = runtime.plan_experiment(session, hypothesis_id, "Random", 80, 4)["plan_id"]
                run = runtime.run_experiment(session, plan_id, "Random", 80, 7, 4)
            finally:
                runtime.close()

            self.assertEqual(run["status"], "COMPLETED")
            self.assertEqual(set(run), {"run_id", "status", "rounds", "visible_summary", "artifact_ref"})
            self.assertNotIn("observations", run)
            self.assertNotIn("selected_ids", json.dumps(run, ensure_ascii=False))

            artifact_path = Path(run["artifact_ref"])
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertIn("raw_observations", artifact)
            self.assertIn("observations", artifact)
            artifact["observations"] = [
                {
                    "status": "COMPLETED",
                    "revealed_label_count": 1,
                    "predicted_cost": 1,
                    "remaining_budget": 9999 - index,
                    "round_index": index + 1,
                    "candidate_remaining": 9999 - index,
                }
                for index in range(2_505)
            ]
            artifact_path.write_text(json.dumps(artifact, ensure_ascii=False), encoding="utf-8")

            chart = dispatch("chart_data", {"state_dir": state, "session_id": session})
            self.assertEqual(chart["feedback_trajectory_total_points"], 2_505)
            self.assertTrue(chart["feedback_trajectory_downsampled"])
            self.assertEqual(chart["chart_point_limit"], 2_000)
            self.assertLessEqual(len(chart["feedback_trajectory"]), 2_000)
            self.assertEqual(chart["feedback_trajectory"][0]["round"], 1)
            self.assertEqual(chart["feedback_trajectory"][-1]["round"], 2_505)
            self.assertNotIn("selected_ids", json.dumps(chart, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()