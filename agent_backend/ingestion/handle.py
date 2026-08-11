"""DuckDB-native scalable dataset ingestion without pandas materialisation."""
from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Iterator

import duckdb

MAX_SAMPLE_ROWS_FOR_LLM = 50
HASH_CHUNK_BYTES = 1024 * 1024


def streaming_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def validate_csv(source: Path) -> None:
    """Reject empty, non-UTF8, and structurally malformed CSV before DuckDB profiles it."""
    try:
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            header = next(reader, None)
            if not header or not any(cell.strip() for cell in header):
                raise ValueError("CSV has no header")
            if len(header) != len(set(header)):
                raise ValueError("CSV has duplicate column names")
            expected_width = len(header)
            found_row = False
            for row_number, row in enumerate(reader, start=2):
                found_row = True
                if len(row) != expected_width:
                    raise ValueError(f"CSV row {row_number} has {len(row)} fields; expected {expected_width}")
            if not found_row:
                raise ValueError("CSV has no data rows")
    except UnicodeDecodeError as error:
        raise ValueError("CSV must be UTF-8 encoded") from error
    except csv.Error as error:
        raise ValueError("CSV is structurally malformed") from error


@dataclass
class DatasetHandle:
    path: Path
    sha256: str
    format: str
    row_count: int
    columns: list[str]
    size_bytes: int
    connection: duckdb.DuckDBPyConnection

    @classmethod
    def open(cls, path: str | Path) -> "DatasetHandle":
        source = Path(path).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(source)
        suffix = source.suffix.lower()
        if suffix not in {".csv", ".parquet", ".pq"}:
            raise ValueError("only CSV and Parquet are supported")
        if suffix == ".csv":
            validate_csv(source)
        connection = duckdb.connect(":memory:")
        escaped = str(source).replace("'", "''")
        reader = f"read_csv_auto('{escaped}', sample_size=20000, ignore_errors=false)" if suffix == ".csv" else f"read_parquet('{escaped}')"
        try:
            relation = connection.sql(f"SELECT * FROM {reader}")
            columns = list(relation.columns)
            if not columns or len(set(columns)) != len(columns):
                raise ValueError("dataset has no columns or has duplicate names")
            row_count = int(connection.sql(f"SELECT count(*) FROM {reader}").fetchone()[0])
            if row_count <= 0:
                raise ValueError("dataset has no data rows")
            return cls(source, streaming_sha256(source), suffix.lstrip("."), row_count, columns, source.stat().st_size, connection)
        except Exception:
            connection.close()
            raise

    def _reader(self) -> str:
        escaped = str(self.path).replace("'", "''")
        return f"read_csv_auto('{escaped}', sample_size=20000, ignore_errors=false)" if self.format == "csv" else f"read_parquet('{escaped}')"

    def query(self, sql: str) -> list[tuple[Any, ...]]:
        return self.connection.sql(sql).fetchall()

    def sample(self, limit: int = MAX_SAMPLE_ROWS_FOR_LLM) -> list[dict[str, Any]]:
        cursor = self.connection.execute(f"SELECT * FROM {self._reader()} USING SAMPLE {min(max(0, int(limit)), MAX_SAMPLE_ROWS_FOR_LLM)} ROWS")
        names = [str(item[0]) for item in cursor.description]
        return [{name: None if value is None else str(value) for name, value in zip(names, row)} for row in cursor.fetchall()]

    def profile(self) -> dict[str, Any]:
        columns: dict[str, Any] = {}
        quote = lambda name: '"' + name.replace('"', '""') + '"'
        for column in self.columns:
            name = quote(column)
            dtype = self.connection.sql(f"SELECT typeof({name}) FROM {self._reader()} LIMIT 1").fetchone()[0]
            row = self.connection.sql(f"SELECT count(*) - count({name}), count(DISTINCT {name}) FROM {self._reader()}").fetchone()
            values = self.connection.sql(f"SELECT CAST({name} AS VARCHAR), count(*) FROM {self._reader()} WHERE {name} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 8").fetchall()
            columns[column] = {"dtype": str(dtype), "missing_count": int(row[0]), "missing_rate": round(int(row[0]) / max(1, self.row_count), 6), "unique_count": int(row[1]), "top_values": {str(value): int(count) for value, count in values}}
        return {"row_count": self.row_count, "column_count": len(self.columns), "columns": columns, "sample_limit_for_llm": MAX_SAMPLE_ROWS_FOR_LLM}

    def stream_batches(self, columns: list[str] | None = None, batch_size: int = 10_000) -> Iterator[list[dict[str, Any]]]:
        fields = "*" if columns is None else ", ".join('"' + item.replace('"', '""') + '"' for item in columns)
        cursor = self.connection.execute(f"SELECT {fields} FROM {self._reader()}")
        names = [str(item[0]) for item in cursor.description]
        while rows := cursor.fetchmany(batch_size):
            yield [dict(zip(names, row)) for row in rows]

    def materialize_for_experiment(self, columns: list[str], max_rows: int = 100_000) -> list[dict[str, Any]]:
        if self.row_count > max_rows:
            raise ValueError(f"experiment materialization limited to {max_rows} rows; use profile/sample for larger files")
        fields = ", ".join('"' + item.replace('"', '""') + '"' for item in columns)
        cursor = self.connection.execute(f"SELECT {fields} FROM {self._reader()}")
        names = [str(item[0]) for item in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]
