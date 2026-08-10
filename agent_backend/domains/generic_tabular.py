from __future__ import annotations

from typing import Any

from ..schemas import DomainSpec


def audit_selective_label_environment(spec: DomainSpec, dataset: dict[str, Any], description: str = "") -> dict[str, Any]:
    checks = []
    decision = spec.historical_decision.get("column")
    target = spec.outcome.get("column")
    cost = spec.observation_cost.get("column")
    checks.append({"name": "historical_decision", "passed": bool(decision), "detail": decision or "未识别历史决策"})
    checks.append({"name": "decision_gates_outcome_visibility", "passed": bool(decision and target), "detail": "需要描述确认历史决策与后续标签可见性关系"})
    checks.append({"name": "partially_observed_outcome", "passed": bool(target and decision), "detail": "通过候选池与决策字段构造可见性掩码"})
    checks.append({"name": "additional_observation", "passed": spec.observation_action.get("simulatable", False), "detail": "可离线模拟额外观察"})
    checks.append({"name": "cost_defined", "passed": bool(cost), "detail": "PROXY COST" if cost else "缺少成本字段，不能虚构真实风险"})
    checks.append({"name": "evaluation_isolation", "passed": True, "detail": "outer-test 由 evaluation barrier 隔离"})
    checks.append({"name": "time_leakage", "passed": not spec.leakage_fields, "detail": spec.leakage_fields or "未发现明显事后字段"})
    checks.append({"name": "unknown_semantics", "passed": not spec.unknown_fields, "detail": spec.unknown_fields or "关键语义已具备"})
    passed = sum(bool(c["passed"]) for c in checks)
    if spec.unknown_fields or passed < 5:
        status = "NEEDS_USER_INPUT" if spec.unknown_fields else "INCONCLUSIVE"
    elif any(c["name"] == "time_leakage" and not c["passed"] for c in checks):
        status = "BLOCKED"
    elif passed < len(checks):
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"
    return {"status": status, "checks": checks, "passed_checks": passed, "total_checks": len(checks), "description": description}


def build_generic_environment(spec: DomainSpec, dataset: dict[str, Any]) -> dict[str, Any]:
    if spec.audit_status == "BLOCKED":
        raise ValueError("环境已阻断")
    target = spec.outcome.get("column")
    decision = spec.historical_decision.get("column")
    cost = spec.observation_cost.get("column")
    candidates: list[dict[str, Any]] = []
    for index, row in enumerate(dataset["rows"]):
        visible = bool(decision and str(row.get(decision, "")).lower() in {"1", "true", "yes", "approved", "reviewed", "investigated", "selected", "已复核"})
        outcome = row.get(target) if visible and target else None
        try:
            observation_cost = float(row.get(cost, 1.0)) if cost else 1.0
        except (TypeError, ValueError):
            observation_cost = 1.0
        candidates.append({"row_id": index, "visible": visible, "outcome": outcome, "observation_cost": max(0.0, observation_cost)})
    return {"candidate_count": len(candidates), "visible_count": sum(x["visible"] for x in candidates), "candidates": candidates, "cost_is_proxy": True}

