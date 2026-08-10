from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from agent_backend.domains.generic_tabular import audit_selective_label_environment
from agent_backend.environment.evaluation_barrier import EvaluationBarrier
from agent_backend.ingestion.loader import load_dataset
from agent_backend.ingestion.profiler import inspect_schema, profile_columns
from agent_backend.ingestion.semantic_features import infer_semantics
from agent_backend.policies.registry import list_applicable_policies, run_policy
from agent_backend.schemas import build_domain_spec
from agent_backend.evidence.claim_guard import claim_guard


class AgentCoreTests(unittest.TestCase):
    def make_csv(self, rows):
        handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8")
        with handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return Path(handle.name)

    def test_ingestion_schema_and_domain_spec(self):
        path = self.make_csv([
            {"id": "a", "score": "0.2", "reviewed": "yes", "label": "1", "cost": "2"},
            {"id": "b", "score": "0.8", "reviewed": "no", "label": "0", "cost": "3"},
        ])
        dataset = load_dataset(path)
        schema = inspect_schema(dataset)
        self.assertEqual(schema["row_count"], 2)
        inference = infer_semantics(dataset)
        spec = build_domain_spec(inference)
        self.assertIn("label", spec.outcome["column"])
        self.assertTrue(spec.features)

    def test_missing_semantics_requires_confirmation(self):
        path = self.make_csv([{"a": "1", "b": "x"}, {"a": "2", "b": "y"}])
        spec = build_domain_spec(infer_semantics(load_dataset(path)))
        self.assertTrue(spec.unknown_fields)
        self.assertEqual(audit_selective_label_environment(spec, load_dataset(path))["status"], "NEEDS_USER_INPUT")

    def test_not_selective_stops_before_experiment(self):
        path = self.make_csv([
            {"record_id": "a", "feature": "1", "final_label": "0"},
            {"record_id": "b", "feature": "2", "final_label": "1"},
        ])
        dataset = load_dataset(path)
        spec = build_domain_spec(infer_semantics(dataset))
        audit = audit_selective_label_environment(spec, dataset)
        self.assertIn(audit["status"], {"NEEDS_USER_INPUT", "INCONCLUSIVE"})

    def test_policy_capability_and_budget(self):
        env = {"candidates": [{"observation_cost": 1.0, "visible": True}, {"observation_cost": 2.0, "visible": False}]}
        result = run_policy(env, "CountOnly-MinCost", 1.5, seed=7)
        self.assertEqual(result["feedback_count"], 1)
        self.assertLessEqual(result["predicted_cost"], 1.5)
        spec = {"domain_name": "unknown", "features": ["x"], "observation_cost": {"column": "cost"}}
        statuses = {x["policy"]: x["status"] for x in list_applicable_policies(spec)}
        self.assertEqual(statuses["FAVE-v2.1"], "POLICY_NOT_APPLICABLE")

    def test_evaluation_barrier(self):
        barrier = EvaluationBarrier()
        with self.assertRaises(RuntimeError):
            barrier.reveal({"recall": 0.5})
        barrier.lock_research_plan()
        barrier.reveal({"recall": 0.5})
        with self.assertRaises(RuntimeError):
            barrier.assert_research()
        with self.assertRaises(RuntimeError):
            barrier.reveal({"recall": 0.6})

    def test_claim_guard_blocks_overclaim(self):
        result = claim_guard("该策略适用于所有领域。", {"domain": "fraud"}, "fraud")
        self.assertEqual(result["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()

