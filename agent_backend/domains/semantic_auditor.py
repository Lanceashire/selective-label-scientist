"""Semantic selective-label audit: data evidence is not semantic confirmation."""
from __future__ import annotations

from collections import Counter
from typing import Any

from ..schemas import DomainSpec


def label_availability_mask(rows: list[dict[str, Any]], target_column: str) -> dict[str, Any]:
    missing = [index for index, row in enumerate(rows) if row.get(target_column) in (None, "", "NA", "N/A", "nan")]
    return {"target_column": target_column, "observed_count": len(rows) - len(missing), "missing_count": len(missing), "missing_rate": len(missing) / max(1, len(rows)), "availability_by_row": "materialized internally; not exposed to policies"}


def audit_semantics(spec: DomainSpec | dict[str, Any], rows: list[dict[str, Any]], description: str = "") -> dict[str, Any]:
    content = spec.to_dict() if isinstance(spec, DomainSpec) else spec
    decision = content.get("historical_decision", {})
    target = content.get("outcome", {}).get("column")
    action = content.get("observation_action", {})
    checks: list[dict[str, Any]] = []
    mapping_confirmed = bool(decision.get("confirmed"))
    observed = set(map(str, decision.get("observed_action_values", [])))
    non_observed = set(map(str, decision.get("non_observed_action_values", [])))
    checks.append({"name": "decision_mapping_confirmed", "status": "PASS" if mapping_confirmed and observed and non_observed and not observed & non_observed else "NEEDS_USER_INPUT", "detail": "requires human-confirmed observed/non-observed decision values"})
    if not target:
        checks.append({"name": "label_availability", "status": "NEEDS_USER_INPUT", "detail": "outcome column is not confirmed"})
    else:
        mask = label_availability_mask(rows, str(target))
        simulated = bool(content.get("selection_mechanism", {}).get("simulated"))
        if mask["missing_count"] == 0 and not simulated:
            state = "NOT_SELECTIVE_LABEL"
            detail = "fully observed labels alone do not establish selective-label causality"
        elif mask["missing_count"] > 0 or simulated:
            state = "PASS_WITH_WARNINGS" if simulated else "PASS"
            detail = "simulation" if simulated else "empirical label availability variation detected"
        else:
            state, detail = "INCONCLUSIVE", "cannot establish label availability"
        checks.append({"name": "label_availability", "status": state, "detail": detail, "mask": mask})
    checks.append({"name": "observation_action", "status": "PASS" if action.get("confirmed") and action.get("reversible") is True and action.get("simulatable") is True else "NEEDS_USER_INPUT", "detail": "observation action must be confirmed; defaults are never accepted"})
    time_ok = bool(content.get("time", {}).get("decision_time") and content.get("time", {}).get("outcome_time"))
    checks.append({"name": "time_order", "status": "PASS" if time_ok else "NEEDS_USER_INPUT", "detail": "decision time and outcome time must be supplied or explicitly marked simulation"})
    status_values = {entry["status"] for entry in checks}
    if "NOT_SELECTIVE_LABEL" in status_values:
        status = "NOT_SELECTIVE_LABEL"
    elif "NEEDS_USER_INPUT" in status_values:
        status = "NEEDS_USER_INPUT"
    elif "INCONCLUSIVE" in status_values:
        status = "INCONCLUSIVE"
    elif "PASS_WITH_WARNINGS" in status_values:
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"
    return {"status": status, "checks": checks, "description": description, "semantic_confirmation_required": status != "PASS"}
