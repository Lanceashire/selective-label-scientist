"""The single official runtime for CLI, RPC, Pi and the future TUI.

No caller receives the dynamic environment or an oracle object.  Those are
created only inside this service and final metrics are evaluator-owned.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..domains.semantic_auditor import audit_semantics
from ..environment.dynamic import DynamicSelectiveLabelEnvironment
from ..ingestion.handle import DatasetHandle
from ..ingestion.semantic_features import infer_semantics
from ..persistence.database import DatabaseManager


class ResearchRuntime:
    def __init__(self, state_dir: str | Path | None = None):
        self.state_dir = Path(state_dir or Path.home() / ".ecomic")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db = DatabaseManager(self.state_dir / "ecomic.db")

    def close(self) -> None:
        self.db.close()

    def _session(self, session_id: str) -> dict[str, Any]:
        return self.db.resume_session(session_id)

    def _spec(self, session_id: str) -> dict[str, Any]:
        specs = self._session(session_id)["domain_specs"]
        if not specs:
            raise RuntimeError("session has no DomainSpec")
        return json.loads(specs[-1]["content_json"])

    def _rows(self, session_id: str) -> list[dict[str, Any]]:
        row = self.db.connection.execute("SELECT d.original_path FROM datasets d JOIN sessions s ON s.dataset_id=d.dataset_id WHERE s.session_id=?", (session_id,)).fetchone()
        if row is None:
            raise KeyError("session dataset is missing")
        handle = DatasetHandle.open(str(row[0]))
        return handle.materialize_for_experiment(handle.columns)

    def _ensure_research_open(self, session_id: str) -> None:
        if self._session(session_id)["final_evaluation_revealed"]:
            raise RuntimeError("FINALIZED: final evaluation has been revealed; research mutations are blocked")

    def create_session(self, path: str, description: str = "") -> dict[str, Any]:
        handle = DatasetHandle.open(path)
        rows = handle.materialize_for_experiment(handle.columns)
        dataset = {"path": str(handle.path), "hash": handle.sha256, "columns": handle.columns, "rows": rows}
        inference = infer_semantics(dataset, description)
        candidates = inference["candidates"]
        pick = lambda key: (candidates.get(key) or [{}])[0]
        decision, target, cost, entity = pick("decision"), pick("target"), pick("cost"), pick("id")
        reserved = {decision.get("column"), target.get("column"), cost.get("column"), entity.get("column")}
        spec = {
            "domain_name": "unknown", "task_type": "binary_classification", "entity_id": entity.get("column"),
            "features": [column for column in handle.columns if column not in reserved],
            "historical_decision": {"column": decision.get("column"), "observed_action_values": [], "non_observed_action_values": [], "unknown_action_values": [], "confidence": decision.get("confidence", 0.0), "confirmed": False},
            "outcome": {"column": target.get("column"), "confidence": target.get("confidence", 0.0)},
            "observation_cost": {"column": cost.get("column"), "proxy": True, "confidence": cost.get("confidence", 0.0)},
            "observation_action": {"description": "additional observation action requires human confirmation", "reversible": None, "simulatable": None, "confirmed": False},
            "selection_mechanism": {"type": "unknown", "simulated": False}, "time": {"decision_time": None, "outcome_time": None}, "audit_status": "NEEDS_USER_INPUT",
        }
        dataset_id = self.db.register_dataset(handle.sha256, str(handle.path), handle.format, handle.row_count, len(handle.columns), handle.size_bytes)
        session_id = self.db.create_session(dataset_id)
        self.db.save_domain_spec(session_id, spec, False, "NEEDS_USER_INPUT")
        self.db.append_event(session_id, "load_dataset", {"path": str(handle.path), "sha256": handle.sha256}, "DuckDB DatasetHandle", "COMPLETED")
        return {"session_id": session_id, "schema": handle.profile(), "candidates": candidates, "domain_spec": spec, "status": "NEEDS_USER_INPUT"}

    def confirm_decision_mapping(self, session_id: str, decision_column: str, observed_values: list[str], non_observed_values: list[str], *, target_column: str | None = None, cost_column: str | None = None, decision_time: str | None = None, outcome_time: str | None = None, observation_reversible: bool | None = None, observation_simulatable: bool | None = None) -> dict[str, Any]:
        self._ensure_research_open(session_id)
        if not observed_values or not non_observed_values or set(observed_values) & set(non_observed_values):
            raise ValueError("observed/non-observed values must both be nonempty and disjoint")
        spec = self._spec(session_id)
        spec["historical_decision"] = {"column": decision_column, "observed_action_values": observed_values, "non_observed_action_values": non_observed_values, "unknown_action_values": [], "confidence": 1.0, "confirmed": True}
        if target_column: spec["outcome"]["column"] = target_column
        if cost_column: spec["observation_cost"]["column"] = cost_column
        spec["observation_action"].update({"reversible": observation_reversible, "simulatable": observation_simulatable, "confirmed": observation_reversible is not None and observation_simulatable is not None})
        spec["time"] = {"decision_time": decision_time, "outcome_time": outcome_time}
        audit = audit_semantics(spec, self._rows(session_id))
        spec["audit_status"] = audit["status"]
        self.db.save_confirmation(session_id, "decision_mapping", {"column": decision_column, "observed": observed_values, "hidden": non_observed_values}, decision_column)
        self.db.save_domain_spec(session_id, spec, audit["status"] in {"PASS", "PASS_WITH_WARNINGS"}, audit["status"])
        self.db.append_event(session_id, "confirm_decision_mapping", {"column": decision_column, "observed_count": len(observed_values), "hidden_count": len(non_observed_values)}, "human confirmation", "COMPLETED")
        return {"session_id": session_id, "domain_spec": spec, "audit": audit}

    def create_hypothesis(self, session_id: str, content: str) -> dict[str, Any]:
        self._ensure_research_open(session_id)
        identifier = self.db.save_hypothesis(session_id, content)
        self.db.append_event(session_id, "create_hypothesis", {"content": content}, "hypothesis versioned", "COMPLETED")
        return {"hypothesis_id": identifier}

    def plan_experiment(self, session_id: str, hypothesis_id: str, policy: str, budget: float, rounds: int) -> dict[str, Any]:
        self._ensure_research_open(session_id)
        identifier = self.db.save_plan(session_id, hypothesis_id, {"policy": policy, "budget": budget, "rounds": rounds})
        return {"plan_id": identifier}

    def run_experiment(self, session_id: str, plan_id: str, policy: str, budget: float, seed: int, rounds: int) -> dict[str, Any]:
        self._ensure_research_open(session_id)
        spec = self._spec(session_id)
        if not (spec["historical_decision"].get("confirmed") and spec["observation_action"].get("confirmed")):
            raise RuntimeError("NEEDS_USER_INPUT: confirm decision mapping and observation action in TUI first")
        environment = DynamicSelectiveLabelEnvironment(self._rows(session_id), spec, seed=seed)
        environment.reset(total_budget=budget)
        run_id = self.db.save_run(session_id, plan_id, policy, budget, seed, 0)
        observations = []
        for index in range(rounds):
            observation = environment.advance_round(batch_size=max(1, len(environment.universe.candidate_ids) // max(1, rounds)), policy=policy, seed=seed + index)
            observations.append(observation)
            if observation["status"] == "EXHAUSTED": break
        artifact_dir = self.state_dir / "agent_runs" / session_id; artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact = artifact_dir / f"{run_id}.json"
        artifact.write_text(json.dumps({"policy": policy, "budget": budget, "seed": seed, "rounds": len(observations)}, ensure_ascii=False), encoding="utf-8")
        self.db.finish_run(run_id, status="COMPLETED", round_end=len(observations), artifact_path=str(artifact))
        self.db.append_event(session_id, "run_experiment", {"run_id": run_id, "policy": policy, "rounds": len(observations)}, "DynamicSelectiveLabelEnvironment", "COMPLETED")
        return {"run_id": run_id, "observations": observations, "state": environment.observe_state()}

    def lock_research_plan(self, session_id: str, plan_id: str) -> dict[str, Any]:
        self.db.lock_plan(session_id, plan_id)
        self.db.append_event(session_id, "lock_research_plan", {"plan_id": plan_id}, "plan locked", "COMPLETED")
        return {"status": "LOCKED"}

    def finalize_evaluation(self, session_id: str, run_id: str) -> dict[str, Any]:
        """No metrics parameter by design: only the private evaluator calculates them."""
        run = self.db.connection.execute("SELECT artifact_path FROM experiment_runs WHERE run_id=? AND session_id=?", (run_id, session_id)).fetchone()
        if run is None: raise KeyError("run not found in session")
        recipe = json.loads(Path(run[0]).read_text(encoding="utf-8"))
        environment = DynamicSelectiveLabelEnvironment(self._rows(session_id), self._spec(session_id), seed=int(recipe["seed"]))
        environment.reset(total_budget=float(recipe["budget"]))
        for index in range(int(recipe["rounds"])):
            environment.advance_round(batch_size=max(1, len(environment.universe.candidate_ids) // max(1, int(recipe["rounds"]))), policy=recipe["policy"], seed=int(recipe["seed"]) + index)
        result = environment.finalize()
        self.db.save_final_evaluation(session_id, run_id, result["metrics"])
        self.db.append_event(session_id, "finalize_evaluation", {"run_id": run_id}, "internal oracle evaluator", "COMPLETED")
        return result

    def observe_state(self, session_id: str) -> dict[str, Any]:
        state = self._session(session_id)
        return {"session_id": session_id, "status": state["status"], "final_evaluation_revealed": bool(state["final_evaluation_revealed"]), "runs": len(state["runs"]), "hypotheses": len(state["hypotheses"]), "plans": len(state["plans"])}
