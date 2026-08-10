from __future__ import annotations
from .service_v5 import ResearchRuntime as BaseRuntime
from .report_service import export_session
class ResearchRuntime(BaseRuntime):
 def generate_report(self,session_id:str):
  paths=export_session(self.db,session_id,self.state_dir/"agent_runs"); self.db.append_event(session_id,"generate_report",paths,"SQLite report export","COMPLETED"); return paths
