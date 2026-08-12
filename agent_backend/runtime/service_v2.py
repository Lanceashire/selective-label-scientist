"""Official runtime extensions for snapshots and database-backed claims."""
from __future__ import annotations
from pathlib import Path
from .service_patch import ResearchRuntime as BaseRuntime
from ..persistence.database_v2 import DatabaseManager

class ResearchRuntime(BaseRuntime):
    def __init__(self, state_dir: str | Path | None = None):
        super().__init__(state_dir)
        # Keep the richer migration-backed database while preserving the base
        # runtime's dataset-handle cache and close lifecycle.
        self.db.close()
        self.db = DatabaseManager(self.state_dir / "ecomic.db")

    def run_experiment(self, *args, **kwargs):
        result = super().run_experiment(*args, **kwargs)
        session_id = str(args[0])
        summary = result["visible_summary"]
        self.db.save_environment_snapshot(
            session_id,
            result["run_id"],
            int(result["rounds"]),
            {
                "round": int(result["rounds"]),
                "remaining_budget": summary.get("remaining_budget"),
                "visible_label_count": summary.get("visible_label_count"),
                "candidate_remaining": summary.get("candidate_remaining"),
                "random_seed": kwargs.get("seed", args[4] if len(args) > 4 else 0),
                "policy_state": {"mode": "replay"},
            },
            result["artifact_ref"],
        )
        return result

    def resume_environment(self, session_id: str):
        snapshot = self.db.latest_environment_snapshot(session_id)
        if not snapshot: raise KeyError("no environment snapshot exists for session")
        return snapshot
