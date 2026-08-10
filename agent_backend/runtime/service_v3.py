from __future__ import annotations
from .service_v2 import ResearchRuntime as BaseRuntime
from ..evidence.claim_guard_v2 import ClaimCandidate, assess_claim

class ResearchRuntime(BaseRuntime):
    def claim_guard(self, session_id: str, claim: str, domain_scope: str, dataset_scope: str, policy_scope: str, budget_scope: str, metric_scope: str, evidence_run_ids: list[str], strength: str = "cautious"):
        candidate = ClaimCandidate(claim, domain_scope, dataset_scope, policy_scope, budget_scope, metric_scope, evidence_run_ids, strength)
        verdict = assess_claim(self.db, session_id, candidate)
        claim_id = self.db.save_claim(session_id, claim, domain_scope, verdict["status"], {"evidence_run_ids": evidence_run_ids}, verdict.get("limitations", []))
        for run_id in evidence_run_ids:
            if verdict["status"] != "BLOCKED": self.db.link_claim_evidence(claim_id, run_id, metric_scope, None)
        verdict["claim_id"] = claim_id
        return verdict
