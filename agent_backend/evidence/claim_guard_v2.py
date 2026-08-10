"""Database-backed Claim Guard: every assertion must have a real lineage."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

@dataclass(frozen=True)
class ClaimCandidate:
    claim: str
    domain_scope: str
    dataset_scope: str
    policy_scope: str
    budget_scope: str
    metric_scope: str
    evidence_run_ids: list[str]
    strength: str = "cautious"

def assess_claim(db: Any, session_id: str, candidate: ClaimCandidate) -> dict[str, Any]:
    runs = []
    for run_id in candidate.evidence_run_ids:
        row = db.connection.execute("SELECT * FROM experiment_runs WHERE run_id=? AND session_id=?", (run_id, session_id)).fetchone()
        if not row: return {"status":"BLOCKED","reason":"evidence run is missing or belongs to another session","candidate":asdict(candidate)}
        runs.append(dict(row))
    if not runs: return {"status":"INCONCLUSIVE","reason":"claim has no evidence runs","candidate":asdict(candidate)}
    budgets = {run["budget"] for run in runs}; seeds = {run["seed"] for run in runs}; final_count = db.connection.execute("SELECT count(*) FROM final_evaluations WHERE session_id=?", (session_id,)).fetchone()[0]
    limitations = []
    if len(seeds) < 5: limitations.append("fewer than five seeds")
    if len(budgets) < 3: limitations.append("fewer than three budgets")
    if final_count == 0: limitations.append("no final oracle evaluation")
    if candidate.strength in {"strong","causal"} and limitations: status = "REFUTED"
    else: status = "SUPPORTED" if not limitations else "SUPPORTED_WITH_LIMITATIONS"
    return {"status":status,"candidate":asdict(candidate),"run_count":len(runs),"seed_count":len(seeds),"budget_count":len(budgets),"final_evaluation_count":final_count,"limitations":limitations}
