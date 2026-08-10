from __future__ import annotations

import random
from typing import Any


CAPABILITIES = {
    "Random": {"requires_probability_model": False, "requires_cost": True, "requires_feature_matrix": False, "requires_credit_semantics": False},
    "CountOnly-MinCost": {"requires_probability_model": False, "requires_cost": True, "requires_feature_matrix": False, "requires_credit_semantics": False},
    "LRBE-Uncertainty": {"requires_probability_model": True, "requires_cost": True, "requires_feature_matrix": True, "requires_credit_semantics": False},
    "FAVE-v2.1": {"requires_probability_model": True, "requires_cost": True, "requires_feature_matrix": True, "requires_credit_semantics": True},
}


def list_applicable_policies(spec: dict[str, Any]) -> list[dict[str, Any]]:
    has_cost = bool(spec.get("observation_cost", {}).get("column"))
    has_features = bool(spec.get("features"))
    result = []
    for name, cap in CAPABILITIES.items():
        applicable = has_cost and (not cap["requires_feature_matrix"] or has_features) and not (cap["requires_credit_semantics"] and spec.get("domain_name") != "credit")
        result.append({"policy": name, "capability": cap, "status": "APPLICABLE" if applicable else "POLICY_NOT_APPLICABLE"})
    return result


def _value(row: dict[str, Any], index: int, policy: str, seed: int) -> float:
    if policy == "CountOnly-MinCost":
        return -float(row["observation_cost"])
    if policy == "LRBE-Uncertainty":
        # Deterministic uncertainty proxy: mid-range costs receive priority.
        cost = float(row["observation_cost"])
        return 1.0 / (1.0 + abs(cost - 1.0))
    random.seed(seed * 100003 + index)
    return random.random()


def run_policy(environment: dict[str, Any], policy: str, budget: float, seed: int = 0) -> dict[str, Any]:
    if policy not in CAPABILITIES:
        raise ValueError(f"未知策略: {policy}")
    if policy == "FAVE-v2.1":
        return {"policy": policy, "status": "POLICY_NOT_APPLICABLE", "reason": "FAVE 的信用领域前提未被 GenericTabularAdapter 声明"}
    ordered = sorted(range(len(environment["candidates"])), key=lambda i: _value(environment["candidates"][i], i, policy, seed), reverse=True)
    selected, spent = [], 0.0
    for i in ordered:
        cost = float(environment["candidates"][i]["observation_cost"])
        if spent + cost <= budget + 1e-9:
            selected.append(i)
            spent += cost
    return {"policy": policy, "status": "COMPLETED", "seed": seed, "budget": budget, "selected": selected, "feedback_count": len(selected), "predicted_cost": spent, "cost_is_proxy": True}

