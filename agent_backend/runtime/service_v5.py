"""Deterministic replay restores the next dynamic round from persisted run recipe."""
from __future__ import annotations
import json
from pathlib import Path
from .service_v4 import ResearchRuntime as BaseRuntime
from ..environment.dynamic import DynamicSelectiveLabelEnvironment
class ResearchRuntime(BaseRuntime):
 def resume_next_round(self, session_id: str, run_id: str):
  row=self.db.connection.execute("SELECT artifact_path FROM experiment_runs WHERE run_id=? AND session_id=?",(run_id,session_id)).fetchone()
  if not row: raise KeyError("run not found in session")
  recipe=json.loads(Path(row[0]).read_text(encoding="utf8")); env=DynamicSelectiveLabelEnvironment(self._rows(session_id),self._spec(session_id),seed=int(recipe["seed"])); env.reset(total_budget=float(recipe["budget"]))
  completed=int(recipe["rounds"])
  for index in range(completed): env.advance_round(batch_size=max(1,len(env.universe.candidate_ids)//max(1,completed)),policy=recipe["policy"],seed=int(recipe["seed"])+index)
  state=env.observe_state(); state.update({"run_id":run_id,"next_round":completed,"mode":"DETERMINISTIC_REPLAY_RESTORE"})
  self.db.save_environment_snapshot(session_id,run_id,completed,state,str(row[0])); return state
