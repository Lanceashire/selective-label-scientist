"""Generic policies with a real lexicographic risk-budget exploration solver."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import random
from typing import Any, Iterable

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from ..environment.protocol import ResearchDataView

CAPABILITIES = {
    "Random": {"requires_probability_model": False, "requires_cost": True, "requires_feature_matrix": False, "requires_credit_semantics": False},
    "CountOnly-MinCost": {"requires_probability_model": False, "requires_cost": True, "requires_feature_matrix": False, "requires_credit_semantics": False},
    "Uncertainty-QualityFirst": {"requires_probability_model": True, "requires_cost": True, "requires_feature_matrix": True, "requires_credit_semantics": False},
    "LRBE-Uncertainty": {"requires_probability_model": True, "requires_cost": True, "requires_feature_matrix": True, "requires_credit_semantics": False},
    "FAVE-v2.1": {"requires_probability_model": True, "requires_cost": True, "requires_feature_matrix": True, "requires_credit_semantics": True},
}

@dataclass(frozen=True)
class PolicyResult:
    policy: str; selected_ids: tuple[int, ...]; k_star: int | None; predicted_cost: float; total_utility: float; status: str = "COMPLETED"
    def to_dict(self) -> dict[str, Any]:
        return {"policy": self.policy, "selected_ids": list(self.selected_ids), "selected": list(self.selected_ids), "feedback_count": len(self.selected_ids), "k_star": self.k_star, "predicted_cost": self.predicted_cost, "total_utility": self.total_utility, "status": self.status, "cost_is_proxy": True}

def list_applicable_policies(spec: dict[str, Any]) -> list[dict[str, Any]]:
    has_cost = bool(spec.get("observation_cost", {}).get("column")); has_features = bool(spec.get("features")); output = []
    for name, capability in CAPABILITIES.items():
        applicable = has_cost and (not capability["requires_feature_matrix"] or has_features) and not (capability["requires_credit_semantics"] and spec.get("domain_name") != "credit")
        output.append({"policy": name, "capability": capability, "status": "APPLICABLE" if applicable else "POLICY_NOT_APPLICABLE"})
    return output

def uncertainty_value(probability: float) -> float: return float(probability * (1.0 - probability))

def stage1_k_star(costs: Iterable[float], budget: float) -> int:
    running = 0.0; count = 0
    for cost in sorted(max(0.0, float(c)) for c in costs):
        if running + cost <= budget + 1e-9: running += cost; count += 1
        else: break
    return count

def stage2_select(ids: list[int], costs: list[float], utilities: list[float], budget: float, k_star: int) -> list[int]:
    if k_star == 0: return []
    n = len(ids)
    if n == 0 or k_star > n: raise ValueError("无效的 Stage 2 尺寸")
    constraints = [LinearConstraint(np.ones((1, n)), lb=np.array([k_star]), ub=np.array([k_star])), LinearConstraint(np.asarray(costs, dtype=float).reshape(1, -1), lb=np.array([-np.inf]), ub=np.array([budget + 1e-9]))]
    result = milp(c=-np.asarray(utilities, dtype=float), integrality=np.ones(n), bounds=Bounds(np.zeros(n), np.ones(n)), constraints=constraints, options={"disp": False})
    if not result.success or result.x is None: raise RuntimeError(f"LRBE Stage 2 MILP failed: {result.message}")
    return [ids[index] for index, value in enumerate(result.x) if value >= 0.5]

def brute_force_lrbe(costs: list[float], utilities: list[float], budget: float) -> tuple[int, float]:
    best_k = -1; best_utility = float("-inf")
    for size in range(len(costs) + 1):
        for subset in combinations(range(len(costs)), size):
            total_cost = sum(costs[index] for index in subset)
            if total_cost <= budget + 1e-9:
                value = sum(utilities[index] for index in subset)
                if size > best_k or (size == best_k and value > best_utility): best_k, best_utility = size, value
    return best_k, best_utility

def _greedy(ids: list[int], costs: dict[int, float], scores: dict[int, float], budget: float) -> list[int]:
    selected: list[int] = []; spent = 0.0
    for row_id in sorted(ids, key=lambda item: scores[item], reverse=True):
        if spent + costs[row_id] <= budget + 1e-9: selected.append(row_id); spent += costs[row_id]
    return selected

def execute_policy(view: ResearchDataView, policy: str, *, seed: int = 0) -> PolicyResult:
    ids = sorted(view.candidate_ids); costs = {row_id: float(view.costs[row_id]) for row_id in ids}
    if policy == "FAVE-v2.1": return PolicyResult(policy, (), None, 0.0, 0.0, "POLICY_NOT_APPLICABLE")
    if policy == "Random":
        rng = random.Random(seed); shuffled = list(ids); rng.shuffle(shuffled); scores = {row_id: -index for index, row_id in enumerate(shuffled)}; selected = _greedy(ids, costs, scores, view.remaining_budget)
        return PolicyResult(policy, tuple(selected), None, sum(costs[x] for x in selected), 0.0)
    if policy == "CountOnly-MinCost":
        k_star = stage1_k_star([costs[row_id] for row_id in ids], view.remaining_budget); selected = sorted(ids, key=lambda row_id: costs[row_id])[:k_star]
        return PolicyResult(policy, tuple(selected), k_star, sum(costs[x] for x in selected), 0.0)
    utilities = {row_id: uncertainty_value(view.probabilities[row_id]) for row_id in ids}
    if policy == "Uncertainty-QualityFirst":
        selected = _greedy(ids, costs, utilities, view.remaining_budget); return PolicyResult(policy, tuple(selected), None, sum(costs[x] for x in selected), sum(utilities[x] for x in selected))
    if policy == "LRBE-Uncertainty":
        k_star = stage1_k_star([costs[row_id] for row_id in ids], view.remaining_budget); selected = stage2_select(ids, [costs[x] for x in ids], [utilities[x] for x in ids], view.remaining_budget, k_star)
        return PolicyResult(policy, tuple(sorted(selected)), k_star, sum(costs[x] for x in selected), sum(utilities[x] for x in selected))
    raise ValueError(f"未知策略: {policy}")

def run_policy(environment: dict[str, Any], policy: str, budget: float, seed: int = 0) -> dict[str, Any]:
    ids = list(range(len(environment.get("candidates", []))))
    view = ResearchDataView(frozenset(ids), {}, {idx: float(row["observation_cost"]) for idx, row in enumerate(environment.get("candidates", []))}, {idx: 0.5 for idx in ids}, budget, 0)
    return execute_policy(view, policy, seed=seed).to_dict()
