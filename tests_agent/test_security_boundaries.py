from __future__ import annotations

import unittest

from agent_backend.environment.visibility import ResearchVisibility


class SecurityBoundaryTests(unittest.TestCase):
    def test_research_snapshot_has_no_hidden_outcome_or_outer_metrics(self):
        env = {"candidates": [{"row_id": 0, "visible": False, "outcome": "SECRET", "observation_cost": 1.0}]}
        snapshot = ResearchVisibility(env).research_snapshot(2.0, [0], 1.0)
        self.assertNotIn("outcome", snapshot)
        self.assertNotIn("outer_test_recall", snapshot)
        self.assertFalse(snapshot["outer_test_revealed"])

