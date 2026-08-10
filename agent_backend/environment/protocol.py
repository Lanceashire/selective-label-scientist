"""Strict selective-label partitioning protocol.

The research-side API only receives ``ResearchDataView``.  Raw labels live in
the private environment and in ``OracleEvaluationStore``; policy functions are
never passed those objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
import random


class ProtocolViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class DecisionValueMapping:
    column: str
    observed_action_values: frozenset[str]
    non_observed_action_values: frozenset[str]
    unknown_action_values: frozenset[str] = frozenset()
    confidence: float = 0.0
    confirmed: bool = False

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> "DecisionValueMapping":
        value = spec.get("historical_decision", {})
        required = ("column", "observed_action_values", "non_observed_action_values", "confirmed")
        if any(key not in value for key in required) or not value.get("confirmed"):
            raise ProtocolViolation("历史决策取值映射尚未人工确认，不能构建候选池")
        observed = frozenset(str(x) for x in value["observed_action_values"])
        hidden = frozenset(str(x) for x in value["non_observed_action_values"])
        if not observed or not hidden or observed & hidden:
            raise ProtocolViolation("历史决策 observed/non-observed 映射无效或重叠")
        return cls(
            column=str(value["column"]),
            observed_action_values=observed,
            non_observed_action_values=hidden,
            unknown_action_values=frozenset(str(x) for x in value.get("unknown_action_values", [])),
            confidence=float(value.get("confidence", 0.0)),
            confirmed=True,
        )


@dataclass
class PartitionedUniverse:
    visible_ids: set[int]
    candidate_ids: set[int]
    forbidden_ids: set[int]
    oracle_ids: set[int]
    label_by_id: dict[int, int]
    rows_by_id: dict[int, dict[str, Any]]
    current_batch_ids: set[int] = field(default_factory=set)
    departed_candidate_ids: set[int] = field(default_factory=set)

    def validate(self) -> None:
        groups = (self.visible_ids, self.candidate_ids, self.forbidden_ids, self.oracle_ids)
        names = ("visible", "candidate", "forbidden", "oracle")
        for i, left in enumerate(groups):
            for right_name, right in zip(names[i + 1 :], groups[i + 1 :]):
                if left & right:
                    raise ProtocolViolation(f"协议分区重叠：{names[i]} 与 {right_name}")
        if not self.current_batch_ids <= self.candidate_ids:
            raise ProtocolViolation("current batch 不属于 hidden candidate set")
        if self.departed_candidate_ids & self.candidate_ids:
            raise ProtocolViolation("历史 backlog 重新进入 candidate set")

    def activate_batch(self, size: int) -> set[int]:
        if self.current_batch_ids:
            raise ProtocolViolation("当前 batch 尚未关闭，不能激活下一 batch")
        chosen = set(sorted(self.candidate_ids - self.departed_candidate_ids)[:size])
        self.current_batch_ids = chosen
        return set(chosen)

    def consume_batch(self, selected_ids: Iterable[int]) -> set[int]:
        selected = set(selected_ids)
        self.validate_selection(selected)
        not_selected = self.current_batch_ids - selected
        self.candidate_ids -= self.current_batch_ids
        self.departed_candidate_ids |= self.current_batch_ids
        self.visible_ids |= selected
        self.forbidden_ids |= not_selected
        self.current_batch_ids = set()
        self.validate()
        return selected

    def validate_selection(self, selected_ids: set[int]) -> None:
        self.validate()
        if not selected_ids <= self.current_batch_ids:
            raise ProtocolViolation("selected_ids 必须属于当前 hidden acquirable candidate batch")
        for forbidden in (self.visible_ids, self.forbidden_ids, self.oracle_ids):
            if selected_ids & forbidden:
                raise ProtocolViolation("选择集包含 visible / forbidden / oracle 样本")


def build_partition(
    rows: list[dict[str, Any]],
    spec: dict[str, Any],
    *,
    oracle_fraction: float = 0.2,
    seed: int = 0,
) -> PartitionedUniverse:
    mapping = DecisionValueMapping.from_spec(spec)
    target = spec.get("outcome", {}).get("column")
    if not target:
        raise ProtocolViolation("未确认 outcome 字段")
    visible: set[int] = set(); candidate: set[int] = set(); forbidden: set[int] = set(); labels: dict[int, int] = {}
    by_id = {index: row for index, row in enumerate(rows)}
    for index, row in by_id.items():
        raw = row.get(target)
        decision = str(row.get(mapping.column, ""))
        if raw in (None, "", "NA", "N/A", "nan"):
            forbidden.add(index)
            continue
        try:
            labels[index] = int(float(raw))
        except (TypeError, ValueError) as exc:
            raise ProtocolViolation(f"结果标签 {target} 不是二分类数值") from exc
        if decision in mapping.observed_action_values:
            visible.add(index)
        elif decision in mapping.non_observed_action_values:
            candidate.add(index)
        else:
            forbidden.add(index)
    candidates = sorted(candidate)
    rng = random.Random(seed)
    rng.shuffle(candidates)
    oracle_n = int(len(candidates) * oracle_fraction)
    oracle = set(candidates[:oracle_n])
    candidate -= oracle
    result = PartitionedUniverse(visible, candidate, forbidden, oracle, labels, by_id)
    result.validate()
    return result


@dataclass(frozen=True)
class ResearchDataView:
    """Deliberately label-free view passed to policies and research tools."""
    candidate_ids: frozenset[int]
    feature_rows: dict[int, dict[str, Any]]
    costs: dict[int, float]
    probabilities: dict[int, float]
    remaining_budget: float
    round_index: int

    @classmethod
    def from_universe(
        cls,
        universe: PartitionedUniverse,
        feature_rows: dict[int, dict[str, Any]],
        costs: dict[int, float],
        probabilities: dict[int, float],
        remaining_budget: float,
        round_index: int,
    ) -> "ResearchDataView":
        return cls(frozenset(universe.current_batch_ids), feature_rows, costs, probabilities, remaining_budget, round_index)


@dataclass(frozen=True)
class OracleEvaluationStore:
    """Private evaluator-only labels.  It is never referenced by ResearchDataView."""
    labels: dict[int, int]
    oracle_ids: frozenset[int]

    def labels_for_evaluation(self) -> dict[int, int]:
        return {key: self.labels[key] for key in self.oracle_ids}
