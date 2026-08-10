"""Agent-loop extensions for the single public ResearchRuntime surface.

These methods intentionally expose only researcher-visible metadata and
SQLite-backed lineage.  They never return Oracle labels or final metrics.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .service_v7 import ResearchRuntime as BaseRuntime
from ..domains.semantic_auditor import audit_semantics


class ResearchRuntime(BaseRuntime):
    def audit_environment(self, session_id: str) -> dict[str, Any]:
        """Re-run the current semantic audit without mutating its confirmation state."""
        self._open(session_id)
        spec = deepcopy(self._spec(session_id))
        audit = audit_semantics(spec, self._rows(session_id))
        self.db.append_event(
            session_id,
            "audit_environment",
            {"domain_spec_version": len(self._session(session_id)["domain_specs"])},
            "SemanticAuditor on researcher-visible data",
            "COMPLETED",
        )
        return {
            "session_id": session_id,
            "audit": audit,
            "domain_spec": spec,
            "research_state": self.observe_state(session_id),
        }

    def revise_hypothesis(self, session_id: str, parent_hypothesis_id: str, content: str) -> dict[str, str]:
        """Persist a follow-up hypothesis with a real parent-child lineage edge."""
        self._open(session_id)
        parent = self.db.connection.execute(
            "SELECT hypothesis_id FROM hypotheses WHERE hypothesis_id=? AND session_id=?",
            (parent_hypothesis_id, session_id),
        ).fetchone()
        if parent is None:
            raise KeyError("parent hypothesis is missing or belongs to another session")
        text = content.strip()
        if not text:
            raise ValueError("revised hypothesis content must not be empty")
        hypothesis_id = self.db.save_hypothesis(
            session_id, text, status="FOLLOW_UP", parent_hypothesis_id=parent_hypothesis_id
        )
        self.db.append_event(
            session_id,
            "revise_hypothesis",
            {"parent_hypothesis_id": parent_hypothesis_id, "hypothesis_id": hypothesis_id},
            "follow-up hypothesis persisted",
            "COMPLETED",
        )
        return {"hypothesis_id": hypothesis_id, "parent_hypothesis_id": parent_hypothesis_id}

    def compare_visible_evidence(self, session_id: str, run_ids: list[str]) -> dict[str, Any]:
        """Compare auditable run metadata without exposing evaluator-owned metrics."""
        self._open(session_id)
        if len(run_ids) < 2:
            raise ValueError("compare_visible_evidence requires at least two run_ids")
        rows: list[dict[str, Any]] = []
        for run_id in run_ids:
            row = self.db.connection.execute(
                "SELECT run_id, plan_id, policy, budget, seed, round_end, status FROM experiment_runs "
                "WHERE run_id=? AND session_id=?",
                (run_id, session_id),
            ).fetchone()
            if row is None:
                raise KeyError("evidence run is missing or belongs to another session")
            item = dict(row)
            snapshot = self.db.latest_environment_snapshot(session_id)
            # Snapshot state itself is safe: it carries counts, round and recipe metadata only.
            item["visible_snapshot"] = snapshot["state"] if snapshot and snapshot.get("run_id") == run_id else None
            rows.append(item)
        self.db.append_event(
            session_id,
            "compare_visible_evidence",
            {"run_ids": run_ids},
            "research-visible run metadata comparison",
            "COMPLETED",
        )
        return {
            "session_id": session_id,
            "comparison_scope": "RESEARCH_VISIBLE_ONLY",
            "runs": rows,
            "limitations": [
                "No Oracle labels or final metrics are visible during research.",
                "Compare multiple fresh seeds and budgets before making a strong claim.",
            ],
        }
