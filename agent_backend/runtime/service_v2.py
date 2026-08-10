"""Official runtime extensions for snapshots and database-backed claims."""
from __future__ import annotations
from pathlib import Path
from .service_patch import ResearchRuntime as BaseRuntime
from ..persistence.database_v2 import DatabaseManager

class ResearchRuntime(BaseRuntime):
    def __init__(self, state_dir: str | Path | None = None):
        self.state_dir = Path(state_dir or Path.home()/".ecomic"); self.state_dir.mkdir(parents=True, exist_ok=True); self.db = DatabaseManager(self.state_dir/"ecomic.db")
    def run_experiment(self, *args, **kwargs):
        result = super().run_experiment(*args, **kwargs)
        session_id = str(args[0]); run_id = result["run_id"]
        self.db.save_environment_snapshot(session_id, run_id, len(result["observations"]), {"round": len(result["observations"]), "remaining_budget": result["state"]["remaining_budget"], "visible_label_count": result["state"]["visible_label_count"], "candidate_remaining": result["state"]["candidate_remaining"], "random_seed": kwargs.get("seed", args[4] if len(args)>4 else 0), "policy_state": {"mode": "replay"}})
        return result
    def resume_environment(self, session_id: str):
        snapshot = self.db.latest_environment_snapshot(session_id)
        if not snapshot: raise KeyError("no environment snapshot exists for session")
        return snapshot
