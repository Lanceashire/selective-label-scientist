"""Agent-loop extensions for the single public ResearchRuntime surface.

These methods intentionally expose only researcher-visible metadata and
SQLite-backed lineage.  They never return Oracle labels or final metrics.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
from typing import Any

from .service_v7 import ResearchRuntime as BaseRuntime
from ..domains.semantic_auditor import audit_semantics
from ..ingestion.handle import DatasetHandle
from ..ingestion.semantic_features import infer_semantics


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
    def list_sessions(self) -> list[dict[str, Any]]:
        """Return rich but research-safe history cards for the desktop UI."""
        result: list[dict[str, Any]] = []
        for session in self.db.list_sessions():
            dataset = self.db.connection.execute(
                "SELECT original_path FROM datasets WHERE dataset_id=?", (session["dataset_id"],)
            ).fetchone()
            spec_row = self.db.connection.execute(
                "SELECT content_json FROM domain_specs WHERE session_id=? ORDER BY version DESC LIMIT 1",
                (session["session_id"],),
            ).fetchone()
            spec = json.loads(spec_row[0]) if spec_row else {}
            result.append({
                "session_id": session["session_id"],
                "status": session["status"],
                "dataset": Path(dataset[0]).name if dataset else "dataset unavailable",
                "dataset_path": str(dataset[0]) if dataset else None,
                "domain": str(spec.get("domain_name", "unknown")),
                "model": session.get("model") or session.get("provider") or "未配置模型",
                "hypothesis_count": self.db.connection.execute("SELECT count(*) FROM hypotheses WHERE session_id=?", (session["session_id"],)).fetchone()[0],
                "run_count": self.db.connection.execute("SELECT count(*) FROM experiment_runs WHERE session_id=?", (session["session_id"],)).fetchone()[0],
                "updated_at": session["updated_at"],
                "created_at": session["created_at"],
                "final_evaluation_revealed": bool(session["final_evaluation_revealed"]),
            })
        return result

    def resume_desktop_session(self, session_id: str) -> dict[str, Any]:
        """Rehydrate the exact persisted session metadata for the desktop, never a fresh Session."""
        state = self._session(session_id)
        dataset = self.db.connection.execute(
            "SELECT original_path FROM datasets WHERE dataset_id=?", (state["dataset_id"],)
        ).fetchone()
        if dataset is None:
            raise KeyError("dataset for session is missing")
        handle = DatasetHandle.open(str(dataset[0]))
        try:
            rows = handle.materialize_for_experiment(handle.columns)
            candidates = infer_semantics(
                {"path": str(handle.path), "hash": handle.sha256, "columns": handle.columns, "rows": rows}, ""
            )["candidates"]
            spec = json.loads(state["domain_specs"][-1]["content_json"]) if state["domain_specs"] else {}
            return {
                "session_id": session_id,
                "status": state["status"],
                "schema": handle.profile(),
                "candidates": candidates,
                "domain_spec": spec,
                "snapshot": self.db.latest_environment_snapshot(session_id),
                "research_plan_locked": bool(state["research_plan_locked"]),
                "final_evaluation_revealed": bool(state["final_evaluation_revealed"]),
            }
        finally:
            handle.connection.close()

    def delete_session(self, session_id: str) -> dict[str, str]:
        """Delete one explicitly selected session and its generated artifacts, never the source dataset."""
        self._session(session_id)
        with self.db.transaction():
            self.db.connection.execute("DELETE FROM claim_evidence WHERE claim_id IN (SELECT claim_id FROM claims WHERE session_id=?) OR run_id IN (SELECT run_id FROM experiment_runs WHERE session_id=?)", (session_id, session_id))
            self.db.connection.execute("DELETE FROM environment_snapshots WHERE session_id=?", (session_id,))
            self.db.connection.execute("DELETE FROM final_evaluations WHERE session_id=?", (session_id,))
            self.db.connection.execute("DELETE FROM artifacts WHERE session_id=?", (session_id,))
            self.db.connection.execute("DELETE FROM agent_events WHERE session_id=?", (session_id,))
            self.db.connection.execute("DELETE FROM human_confirmations WHERE session_id=?", (session_id,))
            self.db.connection.execute("DELETE FROM claims WHERE session_id=?", (session_id,))
            self.db.connection.execute("DELETE FROM experiment_runs WHERE session_id=?", (session_id,))
            self.db.connection.execute("DELETE FROM experiment_plans WHERE session_id=?", (session_id,))
            self.db.connection.execute("DELETE FROM hypotheses WHERE session_id=?", (session_id,))
            self.db.connection.execute("DELETE FROM domain_specs WHERE session_id=?", (session_id,))
            self.db.connection.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
        artifact_dir = (self.state_dir / "agent_runs" / session_id).resolve()
        root = (self.state_dir / "agent_runs").resolve()
        if artifact_dir.is_relative_to(root) and artifact_dir.exists():
            shutil.rmtree(artifact_dir)
        return {"status": "DELETED", "session_id": session_id}
    def _report_path(self, session_id: str) -> Path:
        self._session(session_id)
        path = self.state_dir / "agent_runs" / session_id / "final_report.md"
        if not path.is_file():
            path = Path(self.generate_report(session_id)["final_report"])
        return path

    def read_report(self, session_id: str) -> dict[str, str]:
        """Return the stable session-bound Chinese Markdown report for the GUI."""
        report = self._report_path(session_id)
        return {"session_id": session_id, "path": str(report), "content": report.read_text(encoding="utf-8")}

    def export_report(self, session_id: str, destination: str) -> dict[str, str]:
        """Copy only the generated Markdown report to an explicit user-selected destination."""
        target = Path(destination).expanduser()
        if target.suffix.lower() != ".md":
            raise ValueError("report export destination must end in .md")
        if not target.parent.exists() or not target.parent.is_dir():
            raise ValueError("report export directory is unavailable")
        source = self._report_path(session_id)
        if source.resolve() == target.resolve():
            return {"status": "EXISTS", "path": str(target)}
        shutil.copy2(source, target)
        return {"status": "EXPORTED", "path": str(target)}
    def set_research_question(self, session_id: str, question: str) -> dict[str, str]:
        self._open(session_id)
        self.db.set_research_question(session_id, question)
        self.db.append_event(session_id, "set_research_question", {"length": len(question.strip())}, "research question persisted", "COMPLETED")
        return {"status": "SAVED", "session_id": session_id}
