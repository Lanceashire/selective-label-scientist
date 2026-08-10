from __future__ import annotations

from typing import Any


class ResearchVisibility:
    """A small explicit allow-list; hidden outcomes are never returned in research mode."""

    def __init__(self, environment: dict[str, Any]):
        self.environment = environment

    def research_snapshot(self, budget: float, selected: list[int], predicted_cost: float) -> dict[str, Any]:
        candidates = self.environment["candidates"]
        return {
            "mode": "RESEARCH",
            "feedback_count": len(selected),
            "predicted_cost": predicted_cost,
            "budget_utilization": predicted_cost / budget if budget else None,
            "candidate_pool_size": len(candidates),
            "visible_feedback_coverage": sum(candidates[i]["visible"] for i in selected) / max(1, len(selected)),
            "outer_test_revealed": False,
        }

    def final_snapshot(self, metrics: dict[str, Any]) -> dict[str, Any]:
        return {"mode": "FINAL_EVALUATION", "outer_test_revealed": True, "metrics": metrics}

