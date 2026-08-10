import unittest
from agent_backend.evidence.claim_guard_v2 import ClaimCandidate, assess_claim

class ClaimGuardV2Tests(unittest.TestCase):
    def test_claim_guard_uses_database_lineage(self):
        from tests_agent.test_migrations_and_lineage import MigrationAndLineageTests
        import tempfile
        from pathlib import Path
        from agent_backend.persistence.database_v2 import DatabaseManager
        with tempfile.TemporaryDirectory() as directory:
            db=DatabaseManager(Path(directory)/"db.sqlite"); dataset=db.register_dataset("b"*64,"x.csv","csv",1,1,1); session=db.create_session(dataset); hyp=db.save_hypothesis(session,"H"); plan=db.save_plan(session,hyp,{}); run=db.save_run(session,plan,"Random",1,1,0); db.finish_run(run,status="COMPLETED",round_end=1)
            verdict=assess_claim(db,session,ClaimCandidate("local result","run-local","dataset","Random","1","feedback_count",[run]))
            self.assertEqual(verdict["status"],"SUPPORTED_WITH_LIMITATIONS")
            blocked=assess_claim(db,session,ClaimCandidate("bad","run-local","dataset","Random","1","x",["missing"]))
            self.assertEqual(blocked["status"],"BLOCKED")
            db.close()
