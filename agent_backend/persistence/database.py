"""Versioned SQLite source of truth for ECOMIC research sessions."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator
import uuid


def _now() -> str: return datetime.now(timezone.utc).isoformat()
def _id(prefix: str) -> str: return f"{prefix}_{uuid.uuid4().hex}"
def _json(value: Any) -> str: return json.dumps(value, ensure_ascii=False, sort_keys=True)


MIGRATION_001 = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS datasets (dataset_id TEXT PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL, original_path TEXT NOT NULL, stored_path TEXT, format TEXT NOT NULL, row_count INTEGER NOT NULL, column_count INTEGER NOT NULL, size_bytes INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id), status TEXT NOT NULL, provider TEXT, model TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, current_hypothesis_id TEXT, current_domain_spec_id TEXT, research_plan_locked INTEGER NOT NULL DEFAULT 0, final_evaluation_revealed INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS domain_specs (spec_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id), version INTEGER NOT NULL, content_json TEXT NOT NULL, confirmed INTEGER NOT NULL, audit_status TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(session_id, version));
CREATE TABLE IF NOT EXISTS hypotheses (hypothesis_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id), version INTEGER NOT NULL, parent_hypothesis_id TEXT REFERENCES hypotheses(hypothesis_id), content TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(session_id, version));
CREATE TABLE IF NOT EXISTS experiment_plans (plan_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id), hypothesis_id TEXT NOT NULL REFERENCES hypotheses(hypothesis_id), content_json TEXT NOT NULL, locked INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS experiment_runs (run_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id), plan_id TEXT NOT NULL REFERENCES experiment_plans(plan_id), policy TEXT NOT NULL, budget REAL NOT NULL, seed INTEGER NOT NULL, round_start INTEGER NOT NULL, round_end INTEGER, status TEXT NOT NULL, artifact_path TEXT, created_at TEXT NOT NULL, finished_at TEXT);
CREATE TABLE IF NOT EXISTS agent_events (event_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id), turn_id TEXT, tool_name TEXT NOT NULL, arguments_hash TEXT NOT NULL, summary TEXT NOT NULL, status TEXT NOT NULL, timestamp TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claims (claim_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id), content TEXT NOT NULL, scope TEXT NOT NULL, status TEXT NOT NULL, evidence_json TEXT NOT NULL, limitations_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS artifacts (artifact_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id), artifact_type TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL, metadata_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS final_evaluations (evaluation_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id), run_id TEXT NOT NULL REFERENCES experiment_runs(run_id), metrics_json TEXT NOT NULL, revealed_at TEXT NOT NULL, UNIQUE(session_id));
CREATE TABLE IF NOT EXISTS human_confirmations (confirmation_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id), field_type TEXT NOT NULL, candidate_json TEXT NOT NULL, selected_value TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS session_metadata (session_id TEXT PRIMARY KEY REFERENCES sessions(session_id), schema_json TEXT NOT NULL, candidates_json TEXT NOT NULL, created_at TEXT NOT NULL);
"""


class DatabaseManager:
    def __init__(self, path: str | Path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA busy_timeout=5000")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.migrate()

    def close(self) -> None: self.connection.close()
    def migrate(self) -> None:
        with self.transaction():
            self.connection.executescript(MIGRATION_001)
            self.connection.execute("INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES(1, ?)", (_now(),))
    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield; self.connection.commit()
        except Exception:
            self.connection.rollback(); raise
    def _one(self, sql: str, values: tuple[Any, ...]) -> dict[str, Any]:
        row = self.connection.execute(sql, values).fetchone()
        if row is None: raise KeyError("记录不存在")
        return dict(row)

    def register_dataset(self, sha256: str, original_path: str, fmt: str, row_count: int, column_count: int, size_bytes: int, stored_path: str | None = None) -> str:
        row = self.connection.execute("SELECT dataset_id FROM datasets WHERE sha256=?", (sha256,)).fetchone()
        if row: return str(row["dataset_id"])
        dataset_id = _id("dataset")
        with self.transaction(): self.connection.execute("INSERT INTO datasets VALUES(?,?,?,?,?,?,?,?,?)", (dataset_id, sha256, original_path, stored_path, fmt, row_count, column_count, size_bytes, _now()))
        return dataset_id
    def create_session(self, dataset_id: str, *, provider: str = "mock", model: str | None = None) -> str:
        session_id = _id("session"); now = _now()
        with self.transaction(): self.connection.execute("INSERT INTO sessions(session_id,dataset_id,status,provider,model,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (session_id, dataset_id, "RESEARCH", provider, model, now, now))
        return session_id
    def update_session_state(self, session_id: str, **values: Any) -> None:
        allowed = {"status", "current_hypothesis_id", "current_domain_spec_id", "research_plan_locked", "final_evaluation_revealed"}; unknown = set(values) - allowed
        if unknown: raise ValueError(f"不允许更新的 session 字段: {unknown}")
        values["updated_at"] = _now(); names = list(values)
        with self.transaction(): self.connection.execute(f"UPDATE sessions SET {', '.join(f'{n}=?' for n in names)} WHERE session_id=?", tuple(values[n] for n in names) + (session_id,))
    def save_domain_spec(self, session_id: str, content: dict[str, Any], confirmed: bool, audit_status: str) -> str:
        version = int(self.connection.execute("SELECT COALESCE(MAX(version),0)+1 FROM domain_specs WHERE session_id=?", (session_id,)).fetchone()[0]); spec_id = _id("spec")
        with self.transaction(): self.connection.execute("INSERT INTO domain_specs VALUES(?,?,?,?,?,?,?)", (spec_id, session_id, version, _json(content), int(confirmed), audit_status, _now()))
        self.update_session_state(session_id, current_domain_spec_id=spec_id); return spec_id
    def confirm_domain_spec_transaction(
        self,
        session_id: str,
        content: dict[str, Any],
        audit_status: str,
        decision_confirmation: dict[str, Any],
        observation_confirmation: dict[str, Any],
    ) -> str:
        """Persist the whole human DomainSpec approval as one SQLite transaction."""
        spec_id = _id("spec")
        now = _now()
        with self.transaction():
            session = self.connection.execute("SELECT session_id FROM sessions WHERE session_id=?", (session_id,)).fetchone()
            if session is None:
                raise KeyError("session does not exist")
            version = int(self.connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM domain_specs WHERE session_id=?", (session_id,)
            ).fetchone()[0])
            self.connection.execute(
                "INSERT INTO human_confirmations VALUES(?,?,?,?,?,?)",
                (_id("confirm"), session_id, "decision_mapping", _json(decision_confirmation), str(decision_confirmation["column"]), now),
            )
            self.connection.execute(
                "INSERT INTO human_confirmations VALUES(?,?,?,?,?,?)",
                (_id("confirm"), session_id, "observation_action", _json(observation_confirmation), "confirmed", now),
            )
            self.connection.execute(
                "INSERT INTO domain_specs VALUES(?,?,?,?,?,?,?)",
                (spec_id, session_id, version, _json(content), 1, audit_status, now),
            )
            self.connection.execute(
                "UPDATE sessions SET current_domain_spec_id=?, updated_at=? WHERE session_id=?",
                (spec_id, now, session_id),
            )
        return spec_id
    def save_session_metadata(self, session_id: str, schema: dict[str, Any], candidates: dict[str, Any]) -> None:
        with self.transaction():
            self.connection.execute(
                "INSERT OR REPLACE INTO session_metadata(session_id, schema_json, candidates_json, created_at) VALUES(?,?,?,?)",
                (session_id, _json(schema), _json(candidates), _now()),
            )

    def get_session_metadata(self, session_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT schema_json, candidates_json FROM session_metadata WHERE session_id=?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return {"schema": json.loads(row["schema_json"]), "candidates": json.loads(row["candidates_json"])}
    def save_hypothesis(self, session_id: str, content: str, status: str = "TESTING", parent_hypothesis_id: str | None = None) -> str:
        version = int(self.connection.execute("SELECT COALESCE(MAX(version),0)+1 FROM hypotheses WHERE session_id=?", (session_id,)).fetchone()[0]); hypothesis_id = _id("hyp")
        with self.transaction(): self.connection.execute("INSERT INTO hypotheses VALUES(?,?,?,?,?,?,?)", (hypothesis_id, session_id, version, parent_hypothesis_id, content, status, _now()))
        self.update_session_state(session_id, current_hypothesis_id=hypothesis_id); return hypothesis_id
    def save_plan(self, session_id: str, hypothesis_id: str, content: dict[str, Any], locked: bool = False) -> str:
        plan_id = _id("plan")
        with self.transaction(): self.connection.execute("INSERT INTO experiment_plans VALUES(?,?,?,?,?,?)", (plan_id, session_id, hypothesis_id, _json(content), int(locked), _now()))
        return plan_id
    def lock_plan(self, session_id: str, plan_id: str) -> None:
        session = self._one("SELECT final_evaluation_revealed FROM sessions WHERE session_id=?", (session_id,))
        if session["final_evaluation_revealed"]: raise RuntimeError("final evaluation 后不能修改研究计划")
        with self.transaction(): self.connection.execute("UPDATE experiment_plans SET locked=1 WHERE plan_id=? AND session_id=?", (plan_id, session_id))
        self.update_session_state(session_id, research_plan_locked=1)
    def save_run(self, session_id: str, plan_id: str, policy: str, budget: float, seed: int, round_start: int, status: str = "RUNNING") -> str:
        run_id = _id("run")
        with self.transaction(): self.connection.execute("INSERT INTO experiment_runs(run_id,session_id,plan_id,policy,budget,seed,round_start,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (run_id, session_id, plan_id, policy, budget, seed, round_start, status, _now()))
        return run_id
    def finish_run(self, run_id: str, *, status: str, round_end: int, artifact_path: str | None = None) -> None:
        with self.transaction(): self.connection.execute("UPDATE experiment_runs SET status=?,round_end=?,artifact_path=?,finished_at=? WHERE run_id=?", (status, round_end, artifact_path, _now(), run_id))
    def append_event(self, session_id: str, tool_name: str, arguments: dict[str, Any], summary: str, status: str, turn_id: str | None = None) -> str:
        event_id = _id("event"); digest = hashlib.sha256(_json(arguments).encode()).hexdigest()
        with self.transaction(): self.connection.execute("INSERT INTO agent_events VALUES(?,?,?,?,?,?,?,?)", (event_id, session_id, turn_id, tool_name, digest, summary, status, _now()))
        return event_id
    def save_claim(self, session_id: str, content: str, scope: str, status: str, evidence: dict[str, Any], limitations: list[str]) -> str:
        claim_id = _id("claim")
        with self.transaction(): self.connection.execute("INSERT INTO claims VALUES(?,?,?,?,?,?,?,?)", (claim_id, session_id, content, scope, status, _json(evidence), _json(limitations), _now()))
        return claim_id
    def register_artifact(self, session_id: str, artifact_type: str, path: str, metadata: dict[str, Any]) -> str:
        artifact = Path(path); digest = hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact.exists() else "MISSING"; artifact_id = _id("artifact")
        with self.transaction(): self.connection.execute("INSERT INTO artifacts VALUES(?,?,?,?,?,?,?)", (artifact_id, session_id, artifact_type, path, digest, _json(metadata), _now()))
        return artifact_id
    def save_confirmation(self, session_id: str, field_type: str, candidate: dict[str, Any], selected_value: str) -> str:
        confirmation_id = _id("confirm")
        with self.transaction(): self.connection.execute("INSERT INTO human_confirmations VALUES(?,?,?,?,?,?)", (confirmation_id, session_id, field_type, _json(candidate), selected_value, _now()))
        return confirmation_id
    def save_final_evaluation(self, session_id: str, run_id: str, metrics: dict[str, Any]) -> str:
        state = self._one("SELECT research_plan_locked, final_evaluation_revealed FROM sessions WHERE session_id=?", (session_id,))
        if not state["research_plan_locked"]: raise RuntimeError("必须先锁定研究计划")
        if state["final_evaluation_revealed"]: raise RuntimeError("最终评价只能执行一次")
        evaluation_id = _id("eval")
        with self.transaction(): self.connection.execute("INSERT INTO final_evaluations VALUES(?,?,?,?,?)", (evaluation_id, session_id, run_id, _json(metrics), _now()))
        self.update_session_state(session_id, final_evaluation_revealed=1, status="FINALIZED"); return evaluation_id
    def resume_session(self, session_id: str) -> dict[str, Any]:
        session = self._one("SELECT * FROM sessions WHERE session_id=?", (session_id,)); session["domain_specs"] = [dict(r) for r in self.connection.execute("SELECT * FROM domain_specs WHERE session_id=? ORDER BY version", (session_id,))]; session["hypotheses"] = [dict(r) for r in self.connection.execute("SELECT * FROM hypotheses WHERE session_id=? ORDER BY version", (session_id,))]; session["plans"] = [dict(r) for r in self.connection.execute("SELECT * FROM experiment_plans WHERE session_id=?", (session_id,))]; session["runs"] = [dict(r) for r in self.connection.execute("SELECT * FROM experiment_runs WHERE session_id=?", (session_id,))]; return session
    def list_sessions(self) -> list[dict[str, Any]]: return [dict(row) for row in self.connection.execute("SELECT * FROM sessions ORDER BY created_at DESC")]
    def find_runs_by_policy(self, policy: str) -> list[dict[str, Any]]: return [dict(row) for row in self.connection.execute("SELECT * FROM experiment_runs WHERE policy=?", (policy,))]
    def find_claim_evidence(self, claim_id: str) -> dict[str, Any]: return self._one("SELECT * FROM claims WHERE claim_id=?", (claim_id,))
