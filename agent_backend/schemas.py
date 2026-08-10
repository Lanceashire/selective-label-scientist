from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any

EVIDENCE_STATUSES = {"UNTESTED", "TESTING", "SUPPORTED", "REFUTED", "INCONCLUSIVE", "BLOCKED"}

@dataclass
class DomainSpec:
    domain_name: str = "unknown"; task_type: str = "binary_classification"; entity_id: str | None = None; features: list[str] = field(default_factory=list)
    historical_decision: dict[str, Any] = field(default_factory=dict); outcome: dict[str, Any] = field(default_factory=dict); selection_mechanism: dict[str, Any] = field(default_factory=dict)
    candidate_pool: dict[str, Any] = field(default_factory=dict); observation_action: dict[str, Any] = field(default_factory=dict); observation_cost: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, Any] = field(default_factory=dict); time: dict[str, Any] = field(default_factory=dict); sensitive_fields: list[str] = field(default_factory=list); leakage_fields: list[str] = field(default_factory=list); unknown_fields: list[str] = field(default_factory=list); audit_status: str = "UNTESTED"
    def to_dict(self) -> dict[str, Any]: return asdict(self)

def _choice(candidates: dict[str, Any], key: str, override: str | None) -> tuple[str | None, bool]:
    if override: return override, False
    items = candidates.get(key, [])
    if not items: return None, True
    if len(items) == 1 or (items[0]["confidence"] > items[1]["confidence"] and items[0]["confidence"] >= .6): return items[0]["column"], False
    return items[0]["column"], True

def build_domain_spec(inference: dict[str, Any], overrides: dict[str, str] | None = None) -> DomainSpec:
    overrides = overrides or {}; columns = inference["schema"]["columns"]; candidates = inference["candidates"]
    decision, decision_unknown = _choice(candidates, "decision", overrides.get("decision")); target, target_unknown = _choice(candidates, "target", overrides.get("target")); cost, cost_unknown = _choice(candidates, "cost", overrides.get("cost")); entity, _ = _choice(candidates, "id", overrides.get("id"))
    time_cols = [x["column"] for x in candidates.get("time", [])]; reserved = {decision, target, cost, entity, *time_cols}; features = [c for c in columns if c not in reserved]
    unknown = [key for key, flag in (("target", target_unknown), ("decision", decision_unknown), ("cost", cost_unknown)) if flag]
    values = columns.get(target, {}).get("top_values", {}) if target else {}; positive = next((x for x in ("1", "yes", "true", "positive", "fraud", "default") if x in values), None)
    return DomainSpec(entity_id=entity, features=features, historical_decision={"column": decision, "confidence": (candidates.get("decision") or [{}])[0].get("confidence", 0.0)}, outcome={"column": target, "positive_class": positive, "availability_rule": "由历史决策与观察行为决定", "confidence": (candidates.get("target") or [{}])[0].get("confidence", 0.0)}, selection_mechanism={"type": "historical_decision_gated_observation" if decision and target else "unknown", "description": "历史决策是否影响结果标签可见性需要数据描述或人工确认", "confidence": .5 if decision and target else 0.0}, candidate_pool={"definition": "所有满足基础特征完整性的行"}, observation_action={"description": "对候选样本执行额外观察以获得后续标签", "reversible": True, "simulatable": True}, observation_cost={"type": "column_proxy" if cost else "unknown", "column": cost, "formula": "observation_cost_i", "proxy": True, "confidence": (candidates.get("cost") or [{}])[0].get("confidence", 0.0)}, budget={"type": "sum_cost", "unit": "dataset_cost_units"}, time={"decision_time": time_cols[0] if time_cols else None, "outcome_time": time_cols[1] if len(time_cols) > 1 else None}, sensitive_fields=[x["column"] for x in candidates.get("sensitive", [])], leakage_fields=[x["column"] for x in candidates.get("leakage", [])], unknown_fields=unknown, audit_status="NEEDS_USER_INPUT" if unknown else "UNTESTED")
