from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .domains.credit_reference import credit_reference_manifest
from .domains.generic_tabular import audit_selective_label_environment, build_generic_environment
from .environment.evaluation_barrier import EvaluationBarrier
from .environment.visibility import ResearchVisibility
from .evidence.claim_guard import claim_guard
from .evidence.logger import RunLogger
from .evidence.report import generate_report
from .ingestion.loader import load_dataset
from .ingestion.semantic_features import infer_semantics
from .policies.registry import list_applicable_policies, run_policy
from .schemas import build_domain_spec


class ResearchSession:
    def __init__(self, data_path: str, root: str | Path, description: str = "", overrides: dict[str, str] | None = None):
        self.dataset = load_dataset(data_path)
        self.inference = infer_semantics(self.dataset, description)
        self.spec = build_domain_spec(self.inference, overrides)
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + self.dataset["hash"][:8]
        self.run_dir = Path(root) / "agent_runs" / self.session_id
        self.logger = RunLogger(self.run_dir)
        self.barrier = EvaluationBarrier()
        self.environment: dict[str, Any] | None = None
        self.audit: dict[str, Any] | None = None
        self.results: list[dict[str, Any]] = []

    def run(self, budget: float | None = None, seeds: list[int] | None = None) -> dict[str, Any]:
        budget = float(budget if budget is not None else max(1.0, len(self.dataset["rows"]) * 0.25))
        seeds = seeds or [7]
        self.spec.audit_status = "UNTESTED"
        self.audit = audit_selective_label_environment(self.spec, self.dataset, self.inference.get("description", ""))
        self.spec.audit_status = self.audit["status"]
        self.environment = build_generic_environment(self.spec, self.dataset)
        self.logger.write_json("schema_profile.json", self.inference["schema"])
        self.logger.write_json("domain_spec.json", self.spec.to_dict())
        self.logger.append("domain_spec_history.jsonl", {"version": 1, **self.spec.to_dict()})
        self.logger.write_json("audit_report.json", self.audit)
        self.logger.write_json("manifest.json", {"sessionId": self.session_id, "datasetPath": self.dataset["path"], "datasetHash": self.dataset["hash"], "domainSpecVersion": 1, "oracleLocked": False, "researchPlanLocked": False, "finalEvaluationRevealed": False, "frozen_reference": credit_reference_manifest(Path(__file__).parents[1] / "vendor" / "LexiRiskLabel")})
        self.logger.append("actions.jsonl", {"action": "load_dataset", "status": "COMPLETED"})
        self.logger.append("actions.jsonl", {"action": "audit_selective_labels", "status": self.audit["status"]})
        policies = list_applicable_policies(self.spec.to_dict())
        self.logger.write_json("available_policies.json", policies)
        self.logger.append("actions.jsonl", {"action": "list_applicable_policies", "policies": policies})
        if self.audit["status"] in {"INCONCLUSIVE", "NEEDS_USER_INPUT", "BLOCKED"}:
            evidence_status = "BLOCKED" if self.audit["status"] == "BLOCKED" else "INCONCLUSIVE"
        else:
            evidence_status = "TESTING"
            self.barrier.assert_research()
            for seed in seeds:
                for item in policies:
                    if item["status"] != "APPLICABLE":
                        continue
                    result = run_policy(self.environment, item["policy"], budget, seed)
                    result["research_snapshot"] = ResearchVisibility(self.environment).research_snapshot(budget, result.get("selected", []), result.get("predicted_cost", 0.0))
                    self.results.append(result)
                    self.logger.write_json(f"experiment_results/{item['policy']}_seed{seed}.json", result)
                    self.logger.append("actions.jsonl", {"action": "run_experiment", "policy": item["policy"], "seed": seed, "outer_test_revealed": False})
            evidence_status = "SUPPORTED" if self.results else "INCONCLUSIVE"
        self.logger.write_json("experiment_plan.json", {"budget": budget, "seeds": seeds, "policies": [x["policy"] for x in policies if x["status"] == "APPLICABLE"], "locked": False})
        claims = [claim_guard("当前数据可执行预算化选择性标签探索。", {"audit": self.audit["status"], "results": len(self.results)}, self.spec.domain_name), claim_guard("该策略适用于所有领域。", {"audit": self.audit["status"]}, self.spec.domain_name)]
        self.logger.write_json("final_claims.json", claims)
        context = {"session_id": self.session_id, "dataset_path": self.dataset["path"], "dataset_hash": self.dataset["hash"], "schema": self.inference["schema"], "domain_spec": self.spec.to_dict(), "audit": self.audit, "budget": budget, "results": self.results, "evidence_status": evidence_status, "domain_evidence_level": "EXECUTABLE_ONLY" if evidence_status == "SUPPORTED" else "INCONCLUSIVE"}
        (self.run_dir / "final_report.md").write_text(generate_report(context), encoding="utf-8")
        self.logger.write_json("final_evaluation.json", {"revealed": False, "note": "研究阶段保持 outer-test 隔离；调用 finalize_evaluation 后才可揭示。"})
        self.logger.write_json("state.json", {"sessionId": self.session_id, "datasetPath": self.dataset["path"], "datasetHash": self.dataset["hash"], "domainSpec": self.spec.to_dict(), "schemaAudit": self.audit, "currentHypothesis": "数量优先安全采集在固定预算下提升反馈可观测性，但下游恢复需要独立评价。", "currentExperimentPlan": {"budget": budget, "seeds": seeds}, "availablePolicies": policies, "selectedSeeds": seeds, "selectedBudgets": [budget], "agentVisibleEvidence": ["feedback_count", "predicted_cost", "budget_utilization", "visible_feedback_coverage"], "oracleLocked": False, "researchPlanLocked": False, "finalEvaluationRevealed": False, "humanReviewRequired": bool(self.spec.unknown_fields), "evidenceStatus": evidence_status})
        return {"session_id": self.session_id, "run_dir": str(self.run_dir), "audit_status": self.audit["status"], "evidence_status": evidence_status, "results": self.results, "domain_spec": self.spec.to_dict(), "needs_confirmation": self.spec.unknown_fields}

    def lock_research_plan(self) -> dict[str, Any]:
        return self.barrier.lock_research_plan()

    def finalize_evaluation(self, metrics: dict[str, Any]) -> dict[str, Any]:
        result = self.barrier.reveal(metrics)
        self.logger.write_json("final_evaluation.json", result)
        self.logger.append("actions.jsonl", {"action": "finalize_evaluation", "outer_test_revealed": True})
        return result

