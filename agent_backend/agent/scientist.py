"""Tool-oriented Scientist agent, runnable with a deterministic mock LLM in CI."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..domains.semantic_auditor import audit_semantics
from ..environment.dynamic import DynamicSelectiveLabelEnvironment
from ..persistence.database import DatabaseManager


class MockLLM:
    def plan(self, _state: dict[str, Any]) -> list[str]:
        return ["inspect_schema", "infer_domain_spec", "audit_selective_labels", "propose_hypothesis", "plan_experiment", "run_experiment", "lock_research_plan", "finalize_evaluation"]


class ScientistAgent:
    def __init__(self, rows: list[dict[str, Any]], spec: dict[str, Any], run_root: str | Path, *, provider: str = "mock", model: str = "deterministic"):
        self.rows, self.spec = rows, spec
        root = Path(run_root); root.mkdir(parents=True, exist_ok=True)
        self.db = DatabaseManager(root / "state.db")
        import hashlib, json
        digest = hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()
        dataset_id = self.db.register_dataset(digest, "in_memory_rows", "json", len(rows), len(rows[0]) if rows else 0, 0)
        self.session_id = self.db.create_session(dataset_id, provider=provider, model=model)

    def _event(self, name: str, payload: dict[str, Any], status: str = "COMPLETED") -> None:
        self.db.append_event(self.session_id, name, payload, name, status)

    def close(self) -> None:
        self.db.close()

    def run_mock(self, *, budget: float, rounds: int = 2, policy: str = "LRBE-Uncertainty") -> dict[str, Any]:
        audit = audit_semantics(self.spec, self.rows)
        confirmed = audit["status"] in {"PASS", "PASS_WITH_WARNINGS"}
        self.db.save_domain_spec(self.session_id, self.spec, confirmed, audit["status"])
        self._event("infer_domain_spec", {"audit": audit["status"]})
        if not confirmed:
            state = {"status": audit["status"], "session_id": self.session_id, "audit": audit}
            self.close()
            return state
        hyp1 = self.db.save_hypothesis(self.session_id, "Higher uncertainty among the same maximum feasible count yields more useful feedback.")
        self.db.save_hypothesis(self.session_id, "Policy benefit is domain-conditional and needs private-oracle evaluation.", parent_hypothesis_id=hyp1)
        plan = self.db.save_plan(self.session_id, hyp1, {"policy": policy, "budget": budget, "rounds": rounds})
        env = DynamicSelectiveLabelEnvironment(self.rows, self.spec, seed=17)
        env.reset(total_budget=budget)
        run_id = self.db.save_run(self.session_id, plan, policy, budget, 17, 0)
        self._event("plan_experiment", {"plan_id": plan, "policy": policy})
        for round_index in range(rounds):
            observation = env.advance_round(batch_size=max(1, len(self.rows) // (rounds * 3)), policy=policy, seed=round_index)
            self._event("run_experiment", {"round": round_index, "selected": observation.get("selected_ids", [])}, observation["status"])
            if observation["status"] == "EXHAUSTED":
                break
        self.db.finish_run(run_id, status="COMPLETED", round_end=len(env.records))
        self.db.lock_plan(self.session_id, plan)
        self._event("lock_research_plan", {"plan_id": plan})
        final = env.finalize()
        self.db.save_final_evaluation(self.session_id, run_id, final["metrics"])
        self._event("finalize_evaluation", {"run_id": run_id})
        self.db.save_claim(self.session_id, "The run improved feedback observability only; downstream recovery is not inferred.", "run-local", "SUPPORTED", {"run_id": run_id, "final": final}, ["mock LLM", "simulated selection unless audited otherwise"])
        state = self.db.resume_session(self.session_id)
        self.close()
        return {"status": "COMPLETED", "session_id": self.session_id, "run_id": run_id, "final": final, "state": state}
