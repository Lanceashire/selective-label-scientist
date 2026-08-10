"""Semantic audit. Statistics support review but never replace confirmation."""
from __future__ import annotations
from typing import Any
from ..schemas import DomainSpec

def label_availability_mask(rows: list[dict[str, Any]], target_column: str) -> dict[str, Any]:
    missing = [index for index, row in enumerate(rows) if row.get(target_column) in (None, "", "NA", "N/A", "nan")]
    return {"target_column": target_column, "observed_count": len(rows)-len(missing), "missing_count": len(missing), "missing_rate": len(missing)/max(1, len(rows)), "availability_by_row": "private"}

def audit_semantics(spec: DomainSpec | dict[str, Any], rows: list[dict[str, Any]], description: str = "") -> dict[str, Any]:
    content = spec.to_dict() if isinstance(spec, DomainSpec) else spec; decision = content.get("historical_decision", {}); target = content.get("outcome", {}).get("column"); action = content.get("observation_action", {})
    observed = set(map(str, decision.get("observed_action_values", []))); hidden = set(map(str, decision.get("non_observed_action_values", []))); confirmed = bool(decision.get("confirmed"))
    checks = [{"name":"decision_mapping_confirmed", "status":"PASS" if confirmed and observed and hidden and not observed & hidden else "NEEDS_USER_INPUT", "detail":"human-confirmed observed/non-observed mapping required"}]
    if not target: checks.append({"name":"label_availability", "status":"NEEDS_USER_INPUT", "detail":"outcome is not confirmed"})
    else:
        mask = label_availability_mask(rows, str(target)); values: dict[str, list[int]] = {}
        column = decision.get("column")
        for row in rows:
            value = str(row.get(column, "")); values.setdefault(value, [0,0]); values[value][0] += 1; values[value][1] += int(row.get(target) not in (None,"","NA","N/A","nan"))
        rates = [{"decision_value": key, "sample_count": item[0], "visible_label_count": item[1], "visible_label_rate": item[1]/max(1,item[0])} for key,item in values.items()]
        difference = max((item["visible_label_rate"] for item in rates), default=0)-min((item["visible_label_rate"] for item in rates), default=0)
        if mask["missing_count"] == 0 and confirmed: state, detail = "PASS_WITH_WARNINGS", "REPLAY MODE: mapping confirmed but raw labels are retained only for private evaluator reconstruction"
        elif mask["missing_count"] == 0: state, detail = "NOT_SELECTIVE_LABEL", "fully observed labels do not establish selective-label causality"
        else: state, detail = "PASS", "empirical decision-dependent availability requires semantic confirmation"
        checks.append({"name":"label_availability", "status":state, "detail":detail, "mask":mask, "by_decision_value":rates, "max_visible_rate_difference":difference})
    checks.append({"name":"observation_action", "status":"PASS" if action.get("confirmed") and action.get("reversible") is True and action.get("simulatable") is True else "NEEDS_USER_INPUT", "detail":"action requires human confirmation"})
    time = content.get("time", {}); checks.append({"name":"time_order", "status":"PASS" if time.get("decision_time") and time.get("outcome_time") else "NEEDS_USER_INPUT", "detail":"time columns need confirmation"})
    statuses = {check["status"] for check in checks}; status = "NOT_SELECTIVE_LABEL" if "NOT_SELECTIVE_LABEL" in statuses else "NEEDS_USER_INPUT" if "NEEDS_USER_INPUT" in statuses else "BLOCKED" if "BLOCKED" in statuses else "PASS_WITH_WARNINGS" if "PASS_WITH_WARNINGS" in statuses else "PASS"
    return {"status":status, "checks":checks, "description":description, "semantic_confirmation_required":status != "PASS"}
