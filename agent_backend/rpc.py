from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Callable

from .ingestion.handle import DatasetHandle
from .runtime import ResearchRuntime

_DATASET_HANDLES: dict[str, DatasetHandle] = {}
_RUNTIMES: dict[str, ResearchRuntime] = {}


def _runtime_for(state_dir: str | Path) -> ResearchRuntime:
    """Reuse one SQLite runtime for the lifetime of the persistent sidecar."""
    key = str(Path(state_dir).expanduser().resolve())
    runtime = _RUNTIMES.get(key)
    if runtime is None:
        runtime = ResearchRuntime(key)
        _RUNTIMES[key] = runtime
    return runtime


def active_runtime_count() -> int:
    return len(_RUNTIMES)

def close_all_runtimes() -> None:
    for runtime in list(_RUNTIMES.values()):
        runtime.close()
    _RUNTIMES.clear()

def _discard_handle(handle: DatasetHandle | None) -> None:
    if handle is not None:
        handle.connection.close()


def inspect_dataset(path: str, progress: Callable[[str, int], None] | None = None) -> dict:
    """Return bounded metadata and retain the parsed handle for one immediate load."""
    handle = DatasetHandle.open(path, progress=progress)
    try:
        preview = {
            "path": str(handle.path),
            "sha256": handle.sha256,
            "format": handle.format,
            "size_bytes": handle.size_bytes,
            "schema": handle.profile(progress=progress),
            "sample": handle.sample(progress=progress),
        }
    except Exception:
        _discard_handle(handle)
        raise
    # A precheck is normally followed by one create-session click. Keep the
    # cache intentionally small so abandoned previews cannot consume memory.
    while len(_DATASET_HANDLES) >= 2:
        _, stale = _DATASET_HANDLES.popitem()
        _discard_handle(stale)
    handle_id = f"dataset_tmp_{uuid.uuid4().hex}"
    _DATASET_HANDLES[handle_id] = handle
    preview["dataset_handle_id"] = handle_id
    if progress:
        progress("完成", 100)
    return preview


def dispatch(action: str, payload: dict, *, persistent: bool = False) -> dict:
    if action == "finalize_evaluation" and "metrics" in payload:
        raise ValueError("schema validation failed: finalize_evaluation accepts only session_id and run_id; metrics are evaluator-owned")
    if action == "inspect_dataset":
        return inspect_dataset(str(payload["path"]))
    runtime = _runtime_for(payload.get("state_dir") or Path.home() / ".ecomic") if persistent else ResearchRuntime(payload.get("state_dir") or Path.home() / ".ecomic")
    try:
        session_id = str(payload.get("session_id", ""))
        if action == "list_sessions": return {"sessions": runtime.list_sessions()}
        if action == "resume_session": return runtime.resume_desktop_session(session_id)
        if action == "delete_session": return runtime.delete_session(session_id)
        if action == "get_session": return runtime.get_session(session_id)
        if action == "chart_data": return runtime.chart_data(session_id)
        if action == "load_dataset":
            handle = _DATASET_HANDLES.pop(str(payload.get("dataset_handle_id", "")), None)
            if handle is None:
                return runtime.create_session(str(payload["path"]), str(payload.get("description", "")))
            try:
                result = runtime.create_session_from_handle(handle, str(payload.get("description", "")))
                runtime.retain_dataset_handle(result["session_id"], handle)
                handle = None
                return result
            finally:
                _discard_handle(handle)
        if action == "confirm_domain_spec": return runtime.confirm_domain_spec(session_id, str(payload["decision_column"]), list(payload["observed_values"]), list(payload["non_observed_values"]), reversible=bool(payload["reversible"]), simulatable=bool(payload["simulatable"]), description=str(payload.get("description", "")), target_column=payload.get("target_column"), cost_column=payload.get("cost_column"), decision_time=payload.get("decision_time"), outcome_time=payload.get("outcome_time"))
        if action == "confirm_decision_mapping": return runtime.confirm_decision_mapping(session_id, str(payload["decision_column"]), list(payload["observed_values"]), list(payload["non_observed_values"]), target_column=payload.get("target_column"), cost_column=payload.get("cost_column"), decision_time=payload.get("decision_time"), outcome_time=payload.get("outcome_time"))
        if action == "confirm_observation_action": return runtime.confirm_observation_action(session_id, reversible=bool(payload["reversible"]), simulatable=bool(payload["simulatable"]), description=str(payload.get("description", "")))
        if action == "audit_environment": return runtime.audit_environment(session_id)
        if action == "set_research_question": return runtime.set_research_question(session_id, str(payload["question"]))
        if action == "create_hypothesis": return runtime.create_hypothesis(session_id, str(payload["content"]))
        if action == "revise_hypothesis": return runtime.revise_hypothesis(session_id, str(payload["parent_hypothesis_id"]), str(payload["content"]))
        if action == "plan_experiment": return runtime.plan_experiment(session_id, str(payload["hypothesis_id"]), str(payload["policy"]), float(payload["budget"]), int(payload["rounds"]))
        if action == "run_experiment": return runtime.run_experiment(session_id, str(payload["plan_id"]), str(payload["policy"]), float(payload["budget"]), int(payload.get("seed", 0)), int(payload["rounds"]))
        if action == "compare_visible_evidence": return runtime.compare_visible_evidence(session_id, [str(run_id) for run_id in payload["run_ids"]])
        if action == "lock_research_plan": return runtime.lock_research_plan(session_id, str(payload["plan_id"]))
        if action == "lock_run_plan": return runtime.lock_run_plan(session_id, str(payload["run_id"]))
        if action == "finalize_evaluation": return runtime.finalize_evaluation(session_id, str(payload["run_id"]))
        if action == "claim_guard": return runtime.claim_guard(session_id, str(payload["claim"]), str(payload.get("domain_scope", "run-local")), str(payload.get("dataset_scope", "current-dataset")), str(payload.get("policy_scope", "current-policy")), str(payload.get("budget_scope", "current-budget")), str(payload.get("metric_scope", "feedback_count")), list(payload.get("evidence_run_ids", [])), str(payload.get("strength", "cautious")))
        if action == "observe_state": return runtime.observe_state(session_id)
        if action == "resume_environment": return runtime.resume_environment(session_id)
        if action == "resume_next_round": return runtime.resume_next_round(session_id, str(payload["run_id"]))
        if action == "generate_report": return runtime.generate_report(session_id)
        if action == "read_report": return runtime.read_report(session_id)
        if action == "export_report": return runtime.export_report(session_id, str(payload["destination"]))
        raise ValueError(f"unknown typed tool: {action}")
    finally:
        if not persistent:
            runtime.close()


def main() -> int:
    for line in sys.stdin:
        try: output = dispatch(str((query := json.loads(line)).get("action", "")), dict(query.get("payload", {})))
        except Exception as error: output = {"status": "ERROR", "message": str(error)}
        print(json.dumps(output, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__": raise SystemExit(main())