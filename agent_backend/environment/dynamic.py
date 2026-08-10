"""Round-based environment with a hard research/oracle boundary."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from .protocol import OracleEvaluationStore, PartitionedUniverse, ProtocolViolation, ResearchDataView, build_partition
from ..models.adapter import LogisticModelAdapter
from ..policies.registry import PolicyResult, execute_policy


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        # Python's built-in hash is process-randomized; SHA-256 is deterministic across restarts.
        digest = hashlib.sha256(str(value).encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)


@dataclass
class RoundRecord:
    round_index: int
    batch_ids: list[int]
    selected_ids: list[int]
    revealed_count: int
    spent: float
    remaining_budget: float
    policy: str


class DynamicSelectiveLabelEnvironment:
    def __init__(self, rows: list[dict[str, Any]], spec: dict[str, Any], *, oracle_fraction: float = .2, seed: int = 0):
        self.spec = spec
        self.universe: PartitionedUniverse = build_partition(rows, spec, oracle_fraction=oracle_fraction, seed=seed)
        self.target_column = str(spec["outcome"]["column"])
        self.cost_column = spec.get("observation_cost", {}).get("column")
        self.feature_columns = list(spec.get("features") or [key for key in rows[0] if key not in {self.target_column, spec["historical_decision"]["column"], self.cost_column}])
        if not self.feature_columns: raise ProtocolViolation("no feature columns available for dynamic model")
        self._model = LogisticModelAdapter(seed=seed)
        self._revealed: dict[int, int] = {idx: self.universe.label_by_id[idx] for idx in self.universe.visible_ids}
        self._remaining_budget = 0.0; self._round_index = 0; self._finished = False; self.records: list[RoundRecord] = []
        self._oracle = OracleEvaluationStore(self.universe.label_by_id, frozenset(self.universe.oracle_ids)); self._fit()

    def _matrix(self, ids: list[int] | set[int]) -> np.ndarray:
        return np.asarray([[_number(self.universe.rows_by_id[idx].get(column)) for column in self.feature_columns] for idx in ids], dtype=float)

    def _fit(self) -> None:
        if self._revealed:
            ids = sorted(self._revealed); self._model.fit(self._matrix(ids), np.asarray([self._revealed[idx] for idx in ids], dtype=int))

    def reset(self, *, total_budget: float) -> dict[str, Any]:
        if total_budget < 0: raise ValueError("budget must be non-negative")
        self._remaining_budget = float(total_budget); return self.observe_state()

    def observe_state(self) -> dict[str, Any]:
        return {"round_index": self._round_index, "remaining_budget": self._remaining_budget, "visible_label_count": len(self._revealed), "candidate_remaining": len(self.universe.candidate_ids - self.universe.departed_candidate_ids), "oracle_count": len(self.universe.oracle_ids), "finished": self._finished}

    def _view(self, batch_ids: set[int]) -> ResearchDataView:
        costs = {idx: max(0.0, _number(self.universe.rows_by_id[idx].get(self.cost_column, 1.0))) if self.cost_column else 1.0 for idx in batch_ids}
        probabilities = {idx: float(value) for idx, value in zip(sorted(batch_ids), self._model.predict_proba(self._matrix(sorted(batch_ids))))}
        features = {idx: {column: self.universe.rows_by_id[idx].get(column) for column in self.feature_columns} for idx in batch_ids}
        return ResearchDataView.from_universe(self.universe, features, costs, probabilities, self._remaining_budget, self._round_index)

    def advance_round(self, *, batch_size: int, policy: str, seed: int = 0) -> dict[str, Any]:
        if self._finished: raise ProtocolViolation("research is finished; no further adaptive round is allowed")
        batch = self.universe.activate_batch(batch_size)
        if not batch: self._finished = True; return {"status": "EXHAUSTED", **self.observe_state()}
        view = self._view(batch); result: PolicyResult = execute_policy(view, policy, seed=seed); selected = self.universe.consume_batch(result.selected_ids)
        revealed = {idx: self.universe.label_by_id[idx] for idx in selected}; self._revealed.update(revealed); self._remaining_budget = max(0.0, self._remaining_budget - result.predicted_cost)
        self.records.append(RoundRecord(self._round_index, sorted(batch), sorted(selected), len(revealed), result.predicted_cost, self._remaining_budget, policy)); self._round_index += 1; self._fit()
        return {"status": result.status, "policy": policy, "selected_ids": list(result.selected_ids), "revealed_label_count": len(revealed), "predicted_cost": result.predicted_cost, "k_star": result.k_star, **self.observe_state()}

    def finalize(self) -> dict[str, Any]:
        if self._finished: raise ProtocolViolation("final evaluation was already performed")
        self._finished = True; oracle_ids = sorted(self._oracle.oracle_ids)
        if not oracle_ids: return {"status": "INCONCLUSIVE", "reason": "no oracle partition"}
        y_true = np.asarray([self._oracle.labels[idx] for idx in oracle_ids], dtype=int); y_prob = self._model.predict_proba(self._matrix(oracle_ids)); metrics: dict[str, Any] = {"oracle_n": len(oracle_ids), "rounds": len(self.records), "revealed_labels": len(self._revealed)}
        if len(set(y_true)) > 1: metrics["roc_auc"] = float(roc_auc_score(y_true, y_prob)); metrics["average_precision"] = float(average_precision_score(y_true, y_prob))
        else: metrics["status"] = "INCONCLUSIVE_SINGLE_CLASS_ORACLE"
        return {"status": "FINAL_EVALUATION_REVEALED", "metrics": metrics}
