from __future__ import annotations
from .service_v3 import ResearchRuntime as BaseRuntime
class ResearchRuntime(BaseRuntime):
    def lock_run_plan(self, session_id: str, run_id: str):
        row=self.db.connection.execute("SELECT plan_id FROM experiment_runs WHERE run_id=? AND session_id=?",(run_id,session_id)).fetchone()
        if not row: raise KeyError("run not found in session")
        self.db.lock_plan(session_id,str(row[0]))
        self.db.append_event(session_id,"lock_research_plan",{"run_id":run_id,"plan_id":str(row[0])},"plan locked from run", "COMPLETED")
        return {"status":"LOCKED","plan_id":str(row[0]),"run_id":run_id}
