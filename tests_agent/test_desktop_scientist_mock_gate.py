import tempfile
import unittest
from pathlib import Path

from agent_backend.agent.scientist import ScientistAgent


def rows(count=120):
    return [
        {
            "feature": index / count,
            "decision": "reviewed" if index % 3 == 0 else "hidden",
            "label": int((index * 11) % 19 < 8),
            "cost": 1 + index % 3,
            "decision_time": index,
            "outcome_time": index + 1,
        }
        for index in range(count)
    ]


def confirmed_spec():
    return {
        "domain_name": "mock-gate",
        "features": ["feature"],
        "historical_decision": {"column": "decision", "observed_action_values": ["reviewed"], "non_observed_action_values": ["hidden"], "unknown_action_values": [], "confidence": 1.0, "confirmed": True},
        "outcome": {"column": "label"},
        "observation_cost": {"column": "cost"},
        "observation_action": {"description": "offline replay", "confirmed": True, "reversible": True, "simulatable": True},
        "selection_mechanism": {"simulated": True},
        "time": {"decision_time": "decision_time", "outcome_time": "outcome_time"},
    }


class DesktopScientistMockGateTests(unittest.TestCase):
    def test_mock_provider_executes_adaptive_typed_scientist_research(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ScientistAgent(rows(), confirmed_spec(), Path(directory)).run_mock(budget=36, rounds=2)
            self.assertEqual(result["status"], "COMPLETED")
            self.assertGreaterEqual(len(result["state"]["hypotheses"]), 2)
            self.assertGreaterEqual(len(result["state"]["plans"]), 2)
            self.assertGreaterEqual(len(result["state"]["runs"]), 2)
            self.assertEqual(result["state"]["status"], "FINALIZED")
            self.assertEqual(result["agent_decisions"][:3], ["run_experiment", "inspect_evidence", "revise_hypothesis"])
            self.assertGreater(result["comparison"]["observed_feedback"][0], 0)
            self.assertEqual(result["comparison"]["comparison_scope"], "RESEARCH_VISIBLE_ONLY")
            self.assertTrue(Path(result["report"]["final_report"]).is_file())
            self.assertNotIn("roc_auc", str(result["comparison"]).lower())


if __name__ == "__main__":
    unittest.main()
