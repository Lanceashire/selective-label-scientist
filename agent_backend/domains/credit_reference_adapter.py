from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .credit_reference import FROZEN_FILES, credit_reference_manifest


class CreditReferenceAdapter:
    """Read-only bridge to frozen LexiRiskLabel evidence.

    It deliberately does not import or fork the frozen runners during a generic
    session. A credit-specific run can request a summary of committed results;
    numerical changes remain inside the reference repository and are never
    written back by ECOMIC.
    """

    name = "CreditReferenceAdapter"

    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path).resolve()

    def manifest(self) -> dict[str, Any]:
        return credit_reference_manifest(self.repo_path)

    def frozen_result_summary(self, limit: int = 20) -> dict[str, Any]:
        candidates = [
            self.repo_path / "results_phase4" / "QUANTITY_PERFORMANCE_ANALYSIS_FINAL.csv",
            self.repo_path / "results_phase4" / "PHASE4_MECHANISM_FINDINGS_FINAL.csv",
            self.repo_path / "results_phase3" / "PHASE3_FINAL_SYNTHESIS.md",
        ]
        output: dict[str, Any] = {"adapter": self.name, "read_only": True, "files": []}
        for path in candidates:
            if not path.exists():
                continue
            entry: dict[str, Any] = {"path": str(path.relative_to(self.repo_path)), "format": path.suffix.lower()}
            if path.suffix.lower() == ".csv":
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    entry["rows"] = [row for _, row in zip(range(limit), reader)]
            else:
                entry["preview"] = path.read_text(encoding="utf-8", errors="replace")[:4000]
            output["files"].append(entry)
        output["frozen_files"] = list(FROZEN_FILES)
        return output

