from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def load_dataset(path: str | Path) -> dict[str, Any]:
    """Load a small/medium tabular file without exposing labels to the caller."""
    source = Path(path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    suffix = source.suffix.lower()
    if suffix == ".csv":
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError("CSV 缺少表头")
            rows = [{k: _jsonable(v) for k, v in row.items()} for row in reader]
            columns = list(reader.fieldnames)
    elif suffix in {".parquet", ".pq"}:
        try:
            import pandas as pd  # type: ignore
        except ImportError as exc:
            raise RuntimeError("读取 Parquet 需要安装 pandas 和 pyarrow") from exc
        frame = pd.read_parquet(source)
        columns = [str(c) for c in frame.columns]
        rows = [{str(k): _jsonable(v) for k, v in row.items()} for row in frame.to_dict("records")]
    else:
        raise ValueError("仅支持 CSV；Parquet 需要 pandas/pyarrow")
    return {"path": str(source), "hash": digest, "columns": columns, "rows": rows}


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)

