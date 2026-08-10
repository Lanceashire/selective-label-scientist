from __future__ import annotations

import json
import sys
from pathlib import Path

from .domains.generic_tabular import audit_selective_label_environment
from .evidence.claim_guard import claim_guard
from .ingestion.loader import load_dataset
from .ingestion.profiler import inspect_schema
from .ingestion.semantic_features import infer_semantics
from .policies.registry import list_applicable_policies
from .schemas import build_domain_spec
from .session import ResearchSession


def _state_path(payload: dict) -> Path:
    run_dir = payload.get("run_dir")
    if not run_dir:
        raise ValueError("需要 run_dir")
    path = Path(run_dir).resolve() / "state.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def dispatch(action: str, payload: dict) -> dict:
    if action == "claim_guard":
        return claim_guard(payload.get("claim", ""), payload.get("evidence", {}), payload.get("domain", "unknown"))
    if action == "lock_research_plan":
        state_path = _state_path(payload); state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("finalEvaluationRevealed"): raise RuntimeError("final evaluation 后不能锁定新计划")
        state["researchPlanLocked"] = True; state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        plan = state_path.parent / "experiment_plan.json"
        if plan.exists():
            value = json.loads(plan.read_text(encoding="utf-8")); value["locked"] = True; plan.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"status": "LOCKED", "run_dir": str(state_path.parent), "researchPlanLocked": True, "finalEvaluationRevealed": False}
    if action == "finalize_evaluation":
        state_path = _state_path(payload); state = json.loads(state_path.read_text(encoding="utf-8"))
        if not state.get("researchPlanLocked"): raise RuntimeError("必须先 lock_research_plan")
        if state.get("finalEvaluationRevealed"): raise RuntimeError("final evaluation 只能揭示一次")
        metrics = payload.get("metrics", {}); state["finalEvaluationRevealed"] = True; state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        result = {"status": "FINAL_EVALUATION_REVEALED", "outer_test_revealed": True, "metrics": metrics}
        (state_path.parent / "final_evaluation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    path = payload.get("data_path")
    if not path:
        return {"status": "NEEDS_USER_INPUT", "message": "需要 data_path"}
    dataset = load_dataset(path)
    if action == "load_dataset": return {"path": dataset["path"], "hash": dataset["hash"], "row_count": len(dataset["rows"]), "columns": dataset["columns"]}
    schema = inspect_schema(dataset)
    if action == "inspect_schema": return schema
    inference = infer_semantics(dataset, payload.get("description", ""))
    spec = build_domain_spec(inference, payload.get("overrides"))
    if action == "infer_domain_spec": return spec.to_dict()
    if action == "audit_selective_labels": return audit_selective_label_environment(spec, dataset, payload.get("description", ""))
    if action == "list_applicable_policies": return {"policies": list_applicable_policies(spec.to_dict())}
    if action in {"run_experiment", "generate_report", "plan_experiment", "observe_state"}:
        return ResearchSession(path, Path(__file__).parents[1], payload.get("description", ""), payload.get("overrides")).run(payload.get("budget"), payload.get("seeds", [7]))
    if action in {"confirm_field_mapping", "define_budget", "revise_hypothesis", "compare_visible_evidence", "diagnose_selection"}:
        return {"status": "IMPLEMENTED_IN_SESSION", "message": "请在 run_experiment 中提供 overrides/budget；研究状态写入 agent_runs。"}
    return {"status": "UNKNOWN_ACTION", "action": action}


def main() -> int:
    for line in sys.stdin:
        try:
            request = json.loads(line); response = dispatch(request.get("action", ""), request.get("payload", {}))
        except Exception as exc:
            response = {"status": "ERROR", "message": str(exc)}
        print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
