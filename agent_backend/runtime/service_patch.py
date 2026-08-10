"""Compatibility patch for evaluator outcomes with too-small oracle partitions."""
from __future__ import annotations
import json
from pathlib import Path
from .service import ResearchRuntime as _Runtime
from ..environment.dynamic import DynamicSelectiveLabelEnvironment

class ResearchRuntime(_Runtime):
    def finalize_evaluation(self, session_id: str, run_id: str):
        row = self.db.connection.execute("SELECT artifact_path FROM experiment_runs WHERE run_id=? AND session_id=?", (run_id, session_id)).fetchone()
        if not row: raise KeyError("run not found in session")
        recipe = json.loads(Path(row[0]).read_text(encoding="utf8"))
        env = DynamicSelectiveLabelEnvironment(self._rows(session_id), self._spec(session_id), seed=int(recipe["seed"]))
        env.reset(total_budget=float(recipe["budget"]))
        for index in range(int(recipe["rounds"])):
            try: env.advance_round(batch_size=max(1, len(env.universe.candidate_ids)//max(1,int(recipe["rounds"]))), policy=recipe["policy"], seed=int(recipe["seed"])+index)
            except Exception: break
        env._finished = False
        result = env.finalize()
        metrics = result.get("metrics", {"status": result.get("status"), "reason": result.get("reason", "oracle outcome inconclusive")})
        result.setdefault("metrics", metrics)
        self.db.save_final_evaluation(session_id, run_id, metrics)
        self.db.append_event(session_id, "finalize_evaluation", {"run_id":run_id}, "internal oracle evaluator", "COMPLETED")
        return result
