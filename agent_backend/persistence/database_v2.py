"""Migration-backed database extensions: evidence edges and resumable snapshots."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from typing import Any
from .database import DatabaseManager as BaseDatabaseManager

class DatabaseManager(BaseDatabaseManager):
    def migrate(self) -> None:
        super().migrate()
        directory = Path(__file__).with_name("migrations")
        for file in sorted(directory.glob("*.sql")):
            version = int(file.name.split("_", 1)[0])
            if version <= 1 or self.connection.execute("SELECT 1 FROM schema_version WHERE version=?", (version,)).fetchone():
                continue
            with self.transaction():
                self.connection.executescript(file.read_text(encoding="utf-8"))
                self.connection.execute("INSERT INTO schema_version(version, applied_at) VALUES(?,?)", (version, datetime.now(timezone.utc).isoformat()))

    def save_environment_snapshot(self, session_id: str, run_id: str, round_index: int, state: dict[str, Any], artifact_path: str | None = None) -> str:
        identifier = f"snapshot_{uuid.uuid4().hex}"
        with self.transaction():
            self.connection.execute("INSERT INTO environment_snapshots VALUES(?,?,?,?,?,?,?)", (identifier, session_id, run_id, round_index, json.dumps(state, ensure_ascii=False, sort_keys=True), artifact_path, datetime.now(timezone.utc).isoformat()))
        return identifier

    def latest_environment_snapshot(self, session_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM environment_snapshots WHERE session_id=? ORDER BY round_index DESC, created_at DESC LIMIT 1", (session_id,)).fetchone()
        if row is None: return None
        value = dict(row); value["state"] = json.loads(value.pop("state_json")); return value

    def link_claim_evidence(self, claim_id: str, run_id: str, metric_name: str, metric_value: float | None, effect_size: float | None = None, ci_low: float | None = None, ci_high: float | None = None) -> None:
        claim = self.connection.execute("SELECT session_id FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
        run = self.connection.execute("SELECT session_id FROM experiment_runs WHERE run_id=?", (run_id,)).fetchone()
        if not claim or not run or claim[0] != run[0]: raise ValueError("claim evidence must reference a real run in the same session")
        with self.transaction():
            self.connection.execute("INSERT OR REPLACE INTO claim_evidence VALUES(?,?,?,?,?,?,?)", (claim_id, run_id, metric_name, metric_value, effect_size, ci_low, ci_high))
    def set_research_question(self, session_id: str, question: str) -> None:
        text = question.strip()
        if not text:
            raise ValueError("research question must not be empty")
        with self.transaction():
            self.connection.execute(
                "UPDATE sessions SET research_question=?, updated_at=? WHERE session_id=?",
                (text, datetime.now(timezone.utc).isoformat(), session_id),
            )
