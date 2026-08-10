"""Semantic and temporal audit for a human-confirmed selective-label protocol."""
from __future__ import annotations

from datetime import datetime
from math import exp, log, sqrt
from statistics import NormalDist
from typing import Any

from ..schemas import DomainSpec


def _missing(value: Any) -> bool:
    return value is None or str(value).strip().lower() in {"", "na", "n/a", "nan", "none", "null"}


def _time(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def label_availability_mask(rows: list[dict[str, Any]], target_column: str) -> dict[str, Any]:
    missing_count = sum(_missing(row.get(target_column)) for row in rows)
    return {
        "target_column": target_column,
        "observed_count": len(rows) - missing_count,
        "missing_count": missing_count,
        "missing_rate": missing_count / max(1, len(rows)),
        "availability_by_row": "private",
    }


def _availability_statistics(rows: list[dict[str, Any]], decision_column: str, target_column: str) -> tuple[list[dict[str, Any]], float, dict[str, Any] | None]:
    groups: dict[str, list[int]] = {}
    for row in rows:
        decision = str(row.get(decision_column, ""))
        count, visible = groups.setdefault(decision, [0, 0])
        groups[decision] = [count + 1, visible + int(not _missing(row.get(target_column)))]
    by_value = [
        {"decision_value": value, "sample_count": count, "visible_label_count": visible, "visible_label_rate": visible / max(1, count)}
        for value, (count, visible) in sorted(groups.items())
    ]
    difference = max((row["visible_label_rate"] for row in by_value), default=0.0) - min((row["visible_label_rate"] for row in by_value), default=0.0)
    # A transparent 2x2 odds ratio for the most separated values; it is descriptive, not semantic proof.
    odds: dict[str, Any] | None = None
    if len(by_value) >= 2:
        high, low = max(by_value, key=lambda row: row["visible_label_rate"]), min(by_value, key=lambda row: row["visible_label_rate"])
        a, b = high["visible_label_count"], high["sample_count"] - high["visible_label_count"]
        c, d = low["visible_label_count"], low["sample_count"] - low["visible_label_count"]
        # Haldane–Anscombe correction makes a finite, explicitly labelled estimate with zero cells.
        estimate = ((a + 0.5) * (d + 0.5)) / ((b + 0.5) * (c + 0.5))
        standard_error = sqrt(sum(1.0 / (cell + 0.5) for cell in (a, b, c, d)))
        z = NormalDist().inv_cdf(0.975)
        odds = {
            "comparison": {"higher_visibility": high["decision_value"], "lower_visibility": low["decision_value"]},
            "odds_ratio": estimate,
            "ci_95": [exp(log(estimate) - z * standard_error), exp(log(estimate) + z * standard_error)],
            "method": "Haldane-Anscombe corrected descriptive 2x2 odds ratio",
        }
    return by_value, difference, odds


def audit_semantics(spec: DomainSpec | dict[str, Any], rows: list[dict[str, Any]], description: str = "") -> dict[str, Any]:
    content = spec.to_dict() if isinstance(spec, DomainSpec) else spec
    decision = content.get("historical_decision", {})
    target = content.get("outcome", {}).get("column")
    action = content.get("observation_action", {})
    observed_values = set(map(str, decision.get("observed_action_values", [])))
    non_observed_values = set(map(str, decision.get("non_observed_action_values", [])))
    checks: list[dict[str, Any]] = [{
        "name": "decision_mapping_confirmed",
        "status": "PASS" if decision.get("confirmed") and observed_values and non_observed_values and not observed_values & non_observed_values else "NEEDS_USER_INPUT",
        "detail": "Historical decision values require explicit human confirmation.",
    }]
    if not target or not decision.get("column"):
        checks.append({"name": "label_availability", "status": "NEEDS_USER_INPUT", "detail": "Outcome and decision fields need confirmation."})
    else:
        mask = label_availability_mask(rows, str(target))
        by_value, difference, odds = _availability_statistics(rows, str(decision["column"]), str(target))
        if mask["missing_count"] == 0:
            status = "PASS_WITH_WARNINGS" if decision.get("confirmed") else "NEEDS_USER_INPUT"
            detail = "REPLAY MODE: all labels are present in this file; the file alone does not establish a historical selection mechanism."
        elif difference < 0.01:
            status, detail = "NOT_SELECTIVE_LABEL", "Label availability does not materially differ across observed decision values."
        else:
            status, detail = "PASS", "Decision-dependent label availability is descriptive evidence only; semantic confirmation remains required."
        checks.append({"name": "label_availability", "status": status, "detail": detail, "mask": mask, "by_decision_value": by_value, "max_visible_rate_difference": difference, "odds_ratio": odds})
    time = content.get("time", {})
    decision_time, outcome_time = time.get("decision_time"), time.get("outcome_time")
    if not decision_time or not outcome_time:
        checks.append({"name": "time_order", "status": "NEEDS_USER_INPUT", "detail": "Decision and outcome time fields require confirmation."})
    else:
        valid = invalid = missing = 0
        for row in rows:
            left, right = _time(row.get(decision_time)), _time(row.get(outcome_time))
            if left is None or right is None:
                missing += 1
            elif right >= left:
                valid += 1
            else:
                invalid += 1
        comparable = valid + invalid
        invalid_rate = invalid / max(1, len(rows))
        status = "BLOCKED" if invalid_rate > 0.05 else "PASS_WITH_WARNINGS" if missing else "PASS"
        checks.append({"name": "time_order", "status": status, "decision_time": decision_time, "outcome_time": outcome_time, "valid_order_rate": valid / max(1, comparable), "invalid_order_count": invalid, "missing_time_count": missing})
    checks.append({
        "name": "observation_action",
        "status": "PASS" if action.get("confirmed") and action.get("reversible") is True and action.get("simulatable") is True else "NEEDS_USER_INPUT",
        "detail": "A human must separately confirm that the observation action is reversible and simulatable; neither defaults to true.",
    })
    statuses = {check["status"] for check in checks}
    status = "BLOCKED" if "BLOCKED" in statuses else "NEEDS_USER_INPUT" if "NEEDS_USER_INPUT" in statuses else "NOT_SELECTIVE_LABEL" if "NOT_SELECTIVE_LABEL" in statuses else "PASS_WITH_WARNINGS" if "PASS_WITH_WARNINGS" in statuses else "PASS"
    return {"status": status, "checks": checks, "description": description, "semantic_confirmation_required": status in {"NEEDS_USER_INPUT", "BLOCKED"}}
