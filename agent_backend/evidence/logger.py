from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RunLogger:
    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "experiment_results").mkdir(exist_ok=True)

    def write_json(self, name: str, value: Any) -> None:
        (self.run_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def append(self, name: str, value: Any) -> None:
        with (self.run_dir / name).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")

