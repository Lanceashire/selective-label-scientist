"""Final public runtime surface: human confirmation, session discovery, and reports."""
from __future__ import annotations

from copy import deepcopy

from .service_v6 import ResearchRuntime as BaseRuntime
from ..domains.semantic_auditor import audit_semantics


class ResearchRuntime(BaseRuntime):
    def list_sessions(self) -> list[dict[str, object]]:
        """Return safe session metadata for the TUI; never include credentials or Oracle data."""
        return [
            {
                "session_id": row["session_id"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in self.db.list_sessions()
        ]

    def confirm_decision_mapping(
        self,
        session_id: str,
        decision_column: str,
        observed_values: list[str],
        non_observed_values: list[str],
        **kwargs: object,
    ) -> dict[str, object]:
        """Persist only the decision/outcome semantics. Observation action is a separate approval."""
        self._open(session_id)
        if not observed_values or not non_observed_values or set(observed_values) & set(non_observed_values):
            raise ValueError("observed/non-observed values must both be nonempty and disjoint")
        spec = deepcopy(self._spec(session_id))
        spec["historical_decision"] = {
            "column": decision_column,
            "observed_action_values": [str(value) for value in observed_values],
            "non_observed_action_values": [str(value) for value in non_observed_values],
            "unknown_action_values": [],
            "confidence": 1.0,
            "confirmed": True,
        }
        if kwargs.get("target_column"):
            spec["outcome"]["column"] = str(kwargs["target_column"])
        if kwargs.get("cost_column"):
            spec["observation_cost"]["column"] = str(kwargs["cost_column"])
        spec["time"] = {
            "decision_time": kwargs.get("decision_time"),
            "outcome_time": kwargs.get("outcome_time"),
        }
        # Never carry a guessed action approval forward from a prior draft.
        spec["observation_action"] = {
            "description": "requires separate human confirmation",
            "reversible": None,
            "simulatable": None,
            "confirmed": False,
        }
        audit = audit_semantics(spec, self._rows(session_id))
        spec["audit_status"] = audit["status"]
        self.db.save_confirmation(
            session_id,
            "decision_mapping",
            {"column": decision_column, "observed_values": observed_values, "non_observed_values": non_observed_values},
            decision_column,
        )
        spec_id = self.db.save_domain_spec(session_id, spec, False, audit["status"])
        self.db.append_event(session_id, "confirm_decision_mapping", {"spec_id": spec_id, "column": decision_column}, "human decision mapping confirmation", "COMPLETED")
        return {"session_id": session_id, "domain_spec": spec, "audit": audit, "next_step": "confirm_observation_action"}

    def confirm_observation_action(
        self,
        session_id: str,
        *,
        reversible: bool,
        simulatable: bool,
        description: str,
    ) -> dict[str, object]:
        """Require explicit human approval before a replay/simulation experiment can start."""
        self._open(session_id)
        spec = deepcopy(self._spec(session_id))
        if not spec.get("historical_decision", {}).get("confirmed"):
            raise RuntimeError("NEEDS_USER_INPUT: confirm the decision mapping before confirming an observation action")
        spec["observation_action"] = {
            "description": description.strip() or "human-confirmed observation action",
            "reversible": bool(reversible),
            "simulatable": bool(simulatable),
            "confirmed": True,
        }
        audit = audit_semantics(spec, self._rows(session_id))
        spec["audit_status"] = audit["status"]
        self.db.save_confirmation(
            session_id,
            "observation_action",
            {"reversible": bool(reversible), "simulatable": bool(simulatable), "description": spec["observation_action"]["description"]},
            "confirmed",
        )
        spec_id = self.db.save_domain_spec(session_id, spec, audit["status"] in {"PASS", "PASS_WITH_WARNINGS"}, audit["status"])
        self.db.append_event(session_id, "confirm_observation_action", {"spec_id": spec_id}, "human observation action confirmation", "COMPLETED")
        return {"session_id": session_id, "domain_spec": spec, "audit": audit}
