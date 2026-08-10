import tempfile
import unittest
from pathlib import Path

from agent_backend.agent.scientist import ScientistAgent
from agent_backend.environment.dynamic import DynamicSelectiveLabelEnvironment
from agent_backend.environment.protocol import ProtocolViolation, build_partition
from agent_backend.policies.registry import brute_force_lrbe, stage1_k_star, stage2_select


def rows(n=90):
    result = []
    for index in range(n):
        # confirmed, simulated selection so labels are physically available for the oracle but hidden from research
        result.append({"x1": index / n, "x2": (index * 7) % 11, "decision": "observed" if index % 3 == 0 else "hidden", "label": int((index * 13) % 17 < 7), "cost": 1 + index % 3, "decision_time": index, "outcome_time": index + 1})
    return result


def spec():
    return {"domain_name": "synthetic", "features": ["x1", "x2"], "historical_decision": {"column": "decision", "observed_action_values": ["observed"], "non_observed_action_values": ["hidden"], "unknown_action_values": [], "confidence": 1.0, "confirmed": True}, "outcome": {"column": "label"}, "observation_cost": {"column": "cost"}, "observation_action": {"confirmed": True, "reversible": True, "simulatable": True}, "selection_mechanism": {"simulated": True}, "time": {"decision_time": "decision_time", "outcome_time": "outcome_time"}}


class BetaProtocolTests(unittest.TestCase):
    def test_partition_invariants_100_seeds(self):
        for seed in range(100):
            universe = build_partition(rows(), spec(), seed=seed)
            self.assertFalse(universe.visible_ids & universe.candidate_ids)
            self.assertFalse(universe.visible_ids & universe.forbidden_ids)
            self.assertFalse(universe.candidate_ids & universe.oracle_ids)
            batch = universe.activate_batch(5)
            universe.consume_batch(set(sorted(batch)[:2]))
            self.assertFalse(universe.current_batch_ids)
            self.assertFalse(universe.departed_candidate_ids & universe.candidate_ids)

    def test_dynamic_rounds_and_oracle_once(self):
        env = DynamicSelectiveLabelEnvironment(rows(), spec(), seed=3)
        env.reset(total_budget=30)
        for round_index in range(3):
            observation = env.advance_round(batch_size=12, policy="LRBE-Uncertainty", seed=round_index)
            self.assertLessEqual(observation["predicted_cost"], 30)
            self.assertNotIn("labels", observation)
        final = env.finalize()
        self.assertEqual(final["status"], "FINAL_EVALUATION_REVEALED")
        with self.assertRaises(ProtocolViolation):
            env.advance_round(batch_size=2, policy="Random")

    def test_lrbe_matches_bruteforce_small_cases(self):
        for seed in range(50):
            costs = [1 + ((seed + index) % 4) for index in range(8)]
            utilities = [((seed * 3 + index * 7) % 19) / 19 for index in range(8)]
            budget = 9
            k = stage1_k_star(costs, budget)
            chosen = stage2_select(list(range(8)), costs, utilities, budget, k)
            expected_k, expected_utility = brute_force_lrbe(costs, utilities, budget)
            self.assertEqual(k, expected_k)
            self.assertAlmostEqual(sum(utilities[i] for i in chosen), expected_utility, places=7)

    def test_mock_agent_persists_and_finalizes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = ScientistAgent(rows(), spec(), Path(directory)).run_mock(budget=40, rounds=2)
            self.assertEqual(output["status"], "COMPLETED")
            self.assertTrue(output["state"]["final_evaluation_revealed"])
            self.assertGreaterEqual(len(output["state"]["hypotheses"]), 2)


if __name__ == "__main__":
    unittest.main()
