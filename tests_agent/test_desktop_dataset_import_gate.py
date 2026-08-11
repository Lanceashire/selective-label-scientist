import csv
import tempfile
import unittest
from pathlib import Path

import duckdb

from agent_backend.persistence.database import DatabaseManager
from agent_backend.rpc import dispatch


class DesktopDatasetImportGateTests(unittest.TestCase):
    def csv(self, root: Path, name="valid.csv", rows=12) -> Path:
        path = root / name
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["id", "decision", "label", "cost"])
            writer.writeheader()
            for index in range(rows):
                writer.writerow({"id": index, "decision": "yes" if index % 2 else "no", "label": index % 2, "cost": index % 3})
        return path

    def test_csv_parquet_empty_corrupt_encoding_dedup_and_large_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            root, state = Path(directory), Path(directory) / "state"
            csv_path = self.csv(root)
            parquet = root / "valid.parquet"
            source = str(csv_path).replace("'", "''")
            destination = str(parquet).replace("'", "''")
            duckdb.connect().execute(f"COPY (SELECT * FROM read_csv_auto('{source}')) TO '{destination}' (FORMAT PARQUET)")

            self.assertEqual(dispatch("inspect_dataset", {"path": str(csv_path)})["schema"]["row_count"], 12)
            self.assertEqual(dispatch("inspect_dataset", {"path": str(parquet)})["schema"]["row_count"], 12)

            empty = root / "empty.csv"
            empty.write_text("", encoding="utf-8")
            with self.assertRaises(Exception):
                dispatch("inspect_dataset", {"path": str(empty)})

            # Valid UTF-8, but syntactically malformed CSV must not be silently accepted.
            malformed = root / "malformed.csv"
            malformed.write_text('id,decision\n1,"unterminated', encoding="utf-8")
            with self.assertRaises(Exception):
                dispatch("inspect_dataset", {"path": str(malformed)})

            wrong_encoding = root / "wrong-encoding.csv"
            wrong_encoding.write_bytes(b"a,b\n\xff,\xfe\n")
            with self.assertRaises(Exception):
                dispatch("inspect_dataset", {"path": str(wrong_encoding)})

            dispatch("load_dataset", {"path": str(csv_path), "state_dir": str(state)})
            dispatch("load_dataset", {"path": str(csv_path), "state_dir": str(state)})
            db = DatabaseManager(state / "ecomic.db")
            try:
                self.assertEqual(db.connection.execute("SELECT count(*) FROM datasets").fetchone()[0], 1)
            finally:
                db.close()

            large = self.csv(root, "million.csv", rows=1_000_000)
            preview = dispatch("inspect_dataset", {"path": str(large)})
            self.assertEqual(preview["schema"]["row_count"], 1_000_000)
            self.assertLessEqual(len(preview["sample"]), 50)
            self.assertNotIn("rows", preview)


if __name__ == "__main__":
    unittest.main()
