import tempfile
import threading
import time
import unittest
from pathlib import Path

from agent_backend.persistence.database import DatabaseManager


class SQLiteBusyTimeoutTests(unittest.TestCase):
    def test_every_database_manager_configures_a_five_second_busy_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = DatabaseManager(Path(directory) / "ecomic.db")
            try:
                self.assertEqual(database.connection.execute("PRAGMA busy_timeout").fetchone()[0], 5000)
            finally:
                database.close()

    def test_second_writer_waits_for_a_short_owned_write_lock_and_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ecomic.db"
            first = DatabaseManager(path)
            second = DatabaseManager(path)
            entered = threading.Event()
            finished = threading.Event()
            failures: list[BaseException] = []

            def competing_writer() -> None:
                try:
                    entered.set()
                    second.register_dataset("concurrent-dataset", "source.csv", "csv", 1, 1, 1)
                except BaseException as error:  # assertion is made on the parent thread
                    failures.append(error)
                finally:
                    finished.set()

            try:
                first.connection.execute("BEGIN IMMEDIATE")
                worker = threading.Thread(target=competing_writer, daemon=True)
                worker.start()
                self.assertTrue(entered.wait(timeout=1))
                time.sleep(0.25)
                self.assertFalse(finished.is_set(), "second writer must wait rather than racing past the owned lock")
                first.connection.commit()
                self.assertTrue(finished.wait(timeout=3), "second writer did not recover after the lock was released")
                worker.join(timeout=1)
                self.assertEqual(failures, [])
                self.assertEqual(second.connection.execute("SELECT COUNT(*) FROM datasets WHERE sha256='concurrent-dataset'").fetchone()[0], 1)
            finally:
                if first.connection.in_transaction:
                    first.connection.rollback()
                first.close()
                second.close()


if __name__ == "__main__":
    unittest.main()