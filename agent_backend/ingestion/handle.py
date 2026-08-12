"""DuckDB-native scalable dataset ingestion without pandas materialisation."""
from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
from typing import Any, Callable, Iterator

import duckdb

MAX_SAMPLE_ROWS_FOR_LLM = 50
MAX_PROFILE_SAMPLE_ROWS = 10_000
HASH_CHUNK_BYTES = 1024 * 1024
DATASET_TABLE = "ecomic_dataset"
PROFILE_SAMPLE_TABLE = "ecomic_profile_sample"
ProgressCallback = Callable[[str, int], None]


def streaming_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


class _HashingReader(io.RawIOBase):
    """Read a file once while updating its content digest."""

    def __init__(self, source: io.BufferedReader, digest: object) -> None:
        self._source = source
        self._digest = digest

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: bytearray) -> int:
        data = self._source.read(len(buffer))
        if not data:
            return 0
        self._digest.update(data)
        buffer[: len(data)] = data
        return len(data)


def validate_csv_and_hash(source: Path) -> str:
    """Strictly validate a CSV while calculating its SHA-256 in the same pass."""
    digest = hashlib.sha256()
    try:
        with source.open("rb") as raw:
            hashed = _HashingReader(raw, digest)
            with io.TextIOWrapper(io.BufferedReader(hashed), encoding="utf-8-sig", newline="") as handle:
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
    return digest.hexdigest()

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
    def open(cls, path: str | Path, progress: ProgressCallback | None = None) -> "DatasetHandle":
        source = Path(path).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(source)
        suffix = source.suffix.lower()
        if suffix not in {".csv", ".parquet", ".pq"}:
            raise ValueError("only CSV and Parquet are supported")
        if progress:
            progress("读取文件", 8)
        sha256 = validate_csv_and_hash(source) if suffix == ".csv" else streaming_sha256(source)
        if progress:
            progress("解析 Schema", 35)
        connection = duckdb.connect(":memory:")
        escaped = str(source).replace("'", "''")
        reader = (
            f"read_csv_auto('{escaped}', sample_size=20000, ignore_errors=false)"
            if suffix == ".csv"
            else f"read_parquet('{escaped}')"
        )
        try:
            # This is the only full DuckDB parse of the source file.  All later
            # schema/profile/sample queries target the in-memory table instead.
            connection.execute(f"CREATE TEMP TABLE {DATASET_TABLE} AS SELECT * FROM {reader}")
            relation = connection.sql(f"SELECT * FROM {DATASET_TABLE} LIMIT 0")
            columns = [str(column) for column in relation.columns]
            if not columns or len(set(columns)) != len(columns):
                raise ValueError("dataset has no columns or has duplicate names")
            row_count = int(connection.sql(f"SELECT count(*) FROM {DATASET_TABLE}").fetchone()[0])
            if row_count <= 0:
                raise ValueError("dataset has no data rows")
            connection.execute(
                f"CREATE TEMP TABLE {PROFILE_SAMPLE_TABLE} AS "
                f"SELECT * FROM {DATASET_TABLE} USING SAMPLE {MAX_PROFILE_SAMPLE_ROWS} ROWS"
            )
            if progress:
                progress("解析 Schema", 60)
            return cls(source, sha256, suffix.lstrip("."), row_count, columns, source.stat().st_size, connection)
        except Exception:
            connection.close()
            raise

    @staticmethod
    def _quote(name: str) -> str:
        return '"' + name.replace('"', '""') + '"'

    def _reader(self) -> str:
        return DATASET_TABLE

    def query(self, sql: str) -> list[tuple[Any, ...]]:
        return self.connection.sql(sql).fetchall()

    def sample(self, limit: int = MAX_SAMPLE_ROWS_FOR_LLM, progress: ProgressCallback | None = None) -> list[dict[str, Any]]:
        if progress:
            progress("生成样本", 94)
        cursor = self.connection.execute(
            f"SELECT * FROM {PROFILE_SAMPLE_TABLE} LIMIT {min(max(0, int(limit)), MAX_SAMPLE_ROWS_FOR_LLM)}"
        )
        names = [str(item[0]) for item in cursor.description]
        rows = [{name: None if value is None else str(value) for name, value in zip(names, row)} for row in cursor.fetchall()]
        if progress:
            progress("生成样本", 99)
        return rows

    def profile(self, progress: ProgressCallback | None = None) -> dict[str, Any]:
        # Missing counts and cardinalities run in one aggregate scan of the
        # materialised table.  Top values use a bounded sample so wide files
        # never trigger a full source-file scan for every column.
        aggregate_fields: list[str] = []
        for index, column in enumerate(self.columns):
            name = self._quote(column)
            aggregate_fields.extend((
                f"count(*) - count({name}) AS missing_{index}",
                f"approx_count_distinct({name}) AS unique_{index}",
            ))
        if progress:
            progress("统计字段", 68)
        aggregate = self.connection.execute(
            f"SELECT {', '.join(aggregate_fields)} FROM {DATASET_TABLE}"
        ).fetchone()
        dtypes = {
            str(name): str(dtype)
            for name, dtype, *_ in self.connection.execute(f"DESCRIBE {DATASET_TABLE}").fetchall()
        }
        columns: dict[str, Any] = {}
        for index, column in enumerate(self.columns):
            name = self._quote(column)
            values = self.connection.execute(
                f"SELECT CAST({name} AS VARCHAR), count(*) FROM {PROFILE_SAMPLE_TABLE} "
                f"WHERE {name} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 8"
            ).fetchall()
            missing_count = int(aggregate[index * 2] or 0)
            columns[column] = {
                "dtype": dtypes.get(column, "UNKNOWN"),
                "missing_count": missing_count,
                "missing_rate": round(missing_count / max(1, self.row_count), 6),
                "unique_count": int(aggregate[index * 2 + 1] or 0),
                "top_values": {str(value): int(count) for value, count in values},
            }
        return {
            "row_count": self.row_count,
            "column_count": len(self.columns),
            "columns": columns,
            "sample_limit_for_llm": MAX_SAMPLE_ROWS_FOR_LLM,
            "profile_mode": "sampled_top_values",
            "profile_sample_rows": min(self.row_count, MAX_PROFILE_SAMPLE_ROWS),
        }

    def stream_batches(self, columns: list[str] | None = None, batch_size: int = 10_000) -> Iterator[list[dict[str, Any]]]:
        fields = "*" if columns is None else ", ".join(self._quote(item) for item in columns)
        cursor = self.connection.execute(f"SELECT {fields} FROM {DATASET_TABLE}")
        names = [str(item[0]) for item in cursor.description]
        while rows := cursor.fetchmany(batch_size):
            yield [dict(zip(names, row)) for row in rows]

    def materialize_for_experiment(self, columns: list[str], max_rows: int = 100_000) -> list[dict[str, Any]]:
        if self.row_count > max_rows:
            raise ValueError(f"experiment materialization limited to {max_rows} rows; use profile/sample for larger files")
        fields = ", ".join(self._quote(item) for item in columns)
        cursor = self.connection.execute(f"SELECT {fields} FROM {DATASET_TABLE}")
        names = [str(item[0]) for item in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]