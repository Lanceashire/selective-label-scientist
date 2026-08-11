"""Tool-oriented Scientist agent; real provider calls live in Pi Agent Core, mock is CI-only."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any
from ..domains.semantic_auditor import audit_semantics
from ..environment.dynamic import DynamicSelectiveLabelEnvironment
from ..persistence.database import DatabaseManager
from ..runtime.report_service import export_session


class MockLLM:
    """Deterministic provider double that selects a follow-up from tool evidence."""
    def next_after_run(self, observation: dict[str, Any]) -> str:
        return "revise_hypothesis" if int(observation.get("revealed_label_count", 0)) > 0 else "claim_inconclusive"


class ScientistAgent:
    def __init__(self, rows: list[dict[str, Any]], spec: dict[str, Any], run_root: str | Path, *, provider: str = "mock", model: str = "deterministic"):
        self.rows, self.spec = rows, spec
        root = Path(run_root); root.mkdir(parents=True, exist_ok=True)
        self.run_root = root; self.db = DatabaseManager(root / "state.db")
        digest = hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()
        dataset_id = self.db.register_dataset(digest, "in_memory_rows", "json", len(rows), len(rows[0]) if rows else 0, 0)
        self.session_id = self.db.create_session(dataset_id, provider=provider, model=model)
        self.mock_provider = MockLLM()

    def _event(self, name: str, payload: dict[str, Any], status: str = "COMPLETED") -> None:
        self.db.append_event(self.session_id, name, payload, name, status)

    def close(self) -> None: self.db.close()

    def _execute_run(self, *, hypothesis_id: str, policy: str, budget: float, rounds: int, seed: int) -> tuple[str, list[dict[str, Any]], DynamicSelectiveLabelEnvironment]:
        plan = self.db.save_plan(self.session_id, hypothesis_id, {"policy": policy, "budget": budget, "rounds": rounds, "seed": seed})
        self._event("plan_experiment", {"plan_id": plan, "hypothesis_id": hypothesis_id, "policy": policy, "budget": budget})
        env = DynamicSelectiveLabelEnvironment(self.rows, self.spec, seed=seed); env.reset(total_budget=budget)
        run_id = self.db.save_run(self.session_id, plan, policy, budget, seed, 0); observations: list[dict[str, Any]] = []
        for round_index in range(rounds):
            observation = env.advance_round(batch_size=max(1, len(self.rows) // max(1, rounds * 3)), policy=policy, seed=seed + round_index)
            observations.append(observation)
            self._event("run_experiment", {"run_id": run_id, "round": round_index, "policy": policy, "revealed_label_count": observation.get("revealed_label_count", 0), "remaining_budget": observation.get("remaining_budget")}, observation["status"])
            if observation["status"] == "EXHAUSTED": break
        artifact_root = self.run_root / "agent_runs" / self.session_id; artifact_root.mkdir(parents=True, exist_ok=True)
        artifact = artifact_root / f"{run_id}.json"; artifact.write_text(json.dumps({"policy": policy, "budget": budget, "seed": seed, "rounds": len(observations)}, ensure_ascii=False), encoding="utf-8")
        self.db.finish_run(run_id, status="COMPLETED", round_end=len(observations), artifact_path=str(artifact))
        return run_id, observations, env

    def run_mock(self, *, budget: float, rounds: int = 2, policy: str = "LRBE-Uncertainty") -> dict[str, Any]:
        """Full deterministic typed-tool workflow for CI; production uses Pi Agent Core."""
        audit = audit_semantics(self.spec, self.rows); confirmed = audit["status"] in {"PASS", "PASS_WITH_WARNINGS"}
        self.db.save_domain_spec(self.session_id, self.spec, confirmed, audit["status"])
        self._event("observe_state", {"session_id": self.session_id}); self._event("audit_environment", {"audit": audit["status"]})
        if not confirmed:
            state = {"status": audit["status"], "session_id": self.session_id, "audit": audit}; self.close(); return state
        hyp1 = self.db.save_hypothesis(self.session_id, "At low budget, uncertainty-aware selection may improve feedback observability relative to count-only selection.")
        self._event("create_hypothesis", {"hypothesis_id": hyp1, "version": 1})
        run1, observations1, _ = self._execute_run(hypothesis_id=hyp1, policy=policy, budget=budget, rounds=rounds, seed=17)
        evidence_feedback = sum(int(observation.get("revealed_label_count", 0)) for observation in observations1)
        next_action = self.mock_provider.next_after_run({"revealed_label_count": evidence_feedback})
        self._event("inspect_evidence", {"run_id": run1, "revealed_label_count": evidence_feedback, "next_tool": next_action})
        if next_action != "revise_hypothesis":
            self.db.save_claim(self.session_id, "The first run yielded insufficient researcher-visible feedback; the result is inconclusive.", "run-local", "INCONCLUSIVE", {"run_id": run1}, ["No adaptive follow-up was justified by available evidence."])
            self._event("claim_guard", {"run_id": run1, "status": "INCONCLUSIVE"}); report = export_session(self.db, self.session_id, self.run_root / "agent_runs"); self._event("generate_report", report); state = self.db.resume_session(self.session_id); self.close()
            return {"status": "INCONCLUSIVE", "session_id": self.session_id, "run_id": run1, "state": state, "report": report, "agent_decisions": ["run_experiment", "inspect_evidence", next_action]}
        hyp2 = self.db.save_hypothesis(self.session_id, "Follow-up: compare count-only minimum-cost selection against uncertainty-aware selection under a fresh seed.", status="FOLLOW_UP", parent_hypothesis_id=hyp1)
        self._event("revise_hypothesis", {"parent_hypothesis_id": hyp1, "hypothesis_id": hyp2, "reason": "run_1_revealed_feedback"})
        run2, observations2, env2 = self._execute_run(hypothesis_id=hyp2, policy="CountOnly-MinCost", budget=budget, rounds=rounds, seed=29)
        comparison = {"comparison_scope": "RESEARCH_VISIBLE_ONLY", "run_ids": [run1, run2], "policies": [policy, "CountOnly-MinCost"], "observed_feedback": [evidence_feedback, sum(int(item.get("revealed_label_count", 0)) for item in observations2)]}
        self._event("compare_visible_evidence", comparison)
        plan2 = self.db.connection.execute("SELECT plan_id FROM experiment_runs WHERE run_id=?", (run2,)).fetchone()[0]
        self.db.lock_plan(self.session_id, str(plan2)); self._event("lock_research_plan", {"plan_id": str(plan2)})
        final = env2.finalize(); self.db.save_final_evaluation(self.session_id, run2, final["metrics"]); self._event("finalize_evaluation", {"run_id": run2})
        self.db.save_claim(self.session_id, "The observed feedback difference is run-local; it does not establish downstream recall recovery or a cross-domain winner.", "run-local", "CAUTIOUS", {"comparison": comparison, "final_evaluation": "evaluator-owned"}, ["Mock provider", "synthetic or replay dataset", "Final metrics were not used for adaptive planning."])
        self._event("claim_guard", {"run_ids": [run1, run2], "status": "CAUTIOUS"}); report = export_session(self.db, self.session_id, self.run_root / "agent_runs"); self._event("generate_report", report); state = self.db.resume_session(self.session_id); self.close()
        return {"status": "COMPLETED", "session_id": self.session_id, "run_id": run2, "final": final, "state": state, "comparison": comparison, "report": report, "agent_decisions": ["run_experiment", "inspect_evidence", next_action, "plan_experiment", "run_experiment", "compare_visible_evidence", "lock_research_plan", "finalize_evaluation", "generate_report"]}
