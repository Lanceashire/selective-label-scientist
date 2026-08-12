from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import duckdb

from agent_backend.ingestion.handle import DatasetHandle


class _CountingConnection:
    def __init__(self, connection: duckdb.DuckDBPyConnection, statements: list[str]) -> None:
        self._connection = connection
        self._statements = statements

    def execute(self, statement: str, *args, **kwargs):
        self._statements.append(statement)
        return self._connection.execute(statement, *args, **kwargs)

    def sql(self, statement: str, *args, **kwargs):
        self._statements.append(statement)
        return self._connection.sql(statement, *args, **kwargs)

    def close(self) -> None:
        self._connection.close()


class IngestionScanBudgetTests(unittest.TestCase):
    def write_csv(self, root: Path, name: str, rows: int, columns: int) -> Path:
        fields = [f"feature_{index}" for index in range(columns)]
        path = root / name
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row_index in range(rows):
                writer.writerow({field: (row_index + column_index) % 17 for column_index, field in enumerate(fields)})
        return path

    def test_100k_rows_and_200_columns_use_one_duckdb_source_parse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tall = self.write_csv(root, "rows_100k.csv", rows=100_000, columns=6)
            wide = self.write_csv(root, "wide_200.csv", rows=500, columns=200)
            statements: list[str] = []
            original_connect = duckdb.connect

            def counted_connect(*args, **kwargs):
                return _CountingConnection(original_connect(*args, **kwargs), statements)

            with patch("agent_backend.ingestion.handle.duckdb.connect", side_effect=counted_connect):
                tall_handle = DatasetHandle.open(tall)
                wide_handle = DatasetHandle.open(wide)
                try:
                    tall_profile = tall_handle.profile()
                    wide_profile = wide_handle.profile()
                finally:
                    tall_handle.connection.close()
                    wide_handle.connection.close()

            self.assertEqual(tall_profile["row_count"], 100_000)
            self.assertEqual(wide_profile["column_count"], 200)
            self.assertEqual(wide_profile["profile_mode"], "sampled_top_values")
            source_parses = [statement for statement in statements if "read_csv_auto(" in statement.lower()]
            self.assertEqual(len(source_parses), 2, source_parses)
            self.assertEqual(sum("read_csv_auto(" in statement.lower() for statement in source_parses), 2)
            profile_queries = [statement for statement in statements if "ecomic_dataset" in statement.lower() and "read_csv_auto(" not in statement.lower()]
            self.assertTrue(profile_queries)
            self.assertTrue(all("read_csv_auto(" not in statement.lower() for statement in profile_queries))


if __name__ == "__main__":
    unittest.main()