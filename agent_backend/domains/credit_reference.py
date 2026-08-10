from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


FROZEN_FILES = ("src/phase0_engine.py", "src/phase1_runner.py", "src/phase2_runner.py", "src/phase3_runner.py")


def credit_reference_manifest(repo_path: str | Path) -> dict[str, Any]:
    root = Path(repo_path).resolve()
    files = {}
    for relative in FROZEN_FILES:
        path = root / relative
        if path.exists():
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    commit = "unknown"
    head = root / ".git" / "HEAD"
    if head.exists():
        commit = head.read_text(encoding="utf-8", errors="ignore").strip()
    return {"adapter": "CreditReferenceAdapter", "repo_path": str(root), "git_head": commit, "frozen_files": files, "read_only": True, "note": "只读引用，不修改 frozen seeds、rho、TAU、LRBE、FAVE 或既有结果。"}

