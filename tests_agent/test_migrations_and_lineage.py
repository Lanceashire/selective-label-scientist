import tempfile
import unittest
from pathlib import Path
from agent_backend.persistence.database_v2 import DatabaseManager

class MigrationAndLineageTests(unittest.TestCase):
    def test_migrations_snapshots_and_same_session_evidence_fk(self):
        with tempfile.TemporaryDirectory() as directory:
            db = DatabaseManager(Path(directory) / "state.db")
            versions = [row[0] for row in db.connection.execute("SELECT version FROM schema_version ORDER BY version")]
            self.assertEqual(versions, [1,2,3,4])
            dataset = db.register_dataset("a"*64, "dataset.csv", "csv", 2, 2, 8)
            session = db.create_session(dataset)
            hypothesis = db.save_hypothesis(session, "H1")
            plan = db.save_plan(session, hypothesis, {"policy":"Random"})
            run = db.save_run(session, plan, "Random", 1, 1, 0)
            db.finish_run(run, status="COMPLETED", round_end=1)
            snapshot = db.save_environment_snapshot(session, run, 1, {"visible_ids":[1],"candidate_ids":[2],"remaining_budget":0,"random_seed":1})
            self.assertTrue(snapshot.startswith("snapshot_"))
            self.assertEqual(db.latest_environment_snapshot(session)["state"]["visible_ids"], [1])
            claim = db.save_claim(session, "run-local statement", "run-local", "SUPPORTED", {}, [])
            db.link_claim_evidence(claim, run, "feedback_count", 1.0)
            self.assertEqual(db.connection.execute("SELECT count(*) FROM claim_evidence").fetchone()[0], 1)
            other = db.create_session(dataset)
            foreign_claim = db.save_claim(other, "other", "run-local", "INCONCLUSIVE", {}, [])
            with self.assertRaises(ValueError): db.link_claim_evidence(foreign_claim, run, "feedback_count", 1.0)
            db.close()

if __name__ == "__main__": unittest.main()
