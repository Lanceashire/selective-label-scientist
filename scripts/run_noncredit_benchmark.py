"""Run a transparent non-credit REPLAY MODE benchmark matrix.

The WDBC data are real public data, but the decision/visibility mechanism is
synthetic. Results validate protocol plumbing only and never establish a
historical clinical selection mechanism.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean, stdev

from sklearn.datasets import load_breast_cancer

from agent_backend.environment.dynamic import DynamicSelectiveLabelEnvironment

ROOT = Path(__file__).parents[1]
OUT = ROOT / "benchmarks" / "results"


def _ci(values: list[float]) -> list[float]:
    if len(values) < 2: return [values[0], values[0]] if values else [0.0, 0.0]
    margin = 1.96 * stdev(values) / (len(values) ** 0.5)
    return [mean(values) - margin, mean(values) + margin]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = load_breast_cancer()
    threshold = float(data.data[:, 0].mean())
    rows = [{"feature_0": float(features[0]), "feature_1": float(features[1]), "decision": "observed" if features[0] >= threshold else "hidden", "label": int(label), "cost": 1 + float(features[1] > data.data[:, 1].mean()), "decision_time": f"2020-01-{index % 28 + 1:02d}", "outcome_time": f"2020-02-{index % 28 + 1:02d}"} for index, (features, label) in enumerate(zip(data.data, data.target))]
    spec = {"domain_name": "medical-diagnostic-replay", "features": ["feature_0", "feature_1"], "historical_decision": {"column": "decision", "observed_action_values": ["observed"], "non_observed_action_values": ["hidden"], "unknown_action_values": [], "confidence": 1.0, "confirmed": True}, "outcome": {"column": "label"}, "observation_cost": {"column": "cost", "proxy": True}, "observation_action": {"confirmed": True, "reversible": True, "simulatable": True}, "selection_mechanism": {"type": "simulated-replay", "simulated": True, "mode": "REPLAY MODE"}, "time": {"decision_time": "decision_time", "outcome_time": "outcome_time"}}
    records: list[dict[str, object]] = []
    trajectories: list[dict[str, object]] = []
    for seed in range(5):
        for budget in (30.0, 60.0, 90.0):
            for policy in ("Random", "CountOnly-MinCost", "LRBE-Uncertainty"):
                env = DynamicSelectiveLabelEnvironment(rows, spec, seed=seed)
                env.reset(total_budget=budget)
                for round_index in range(5):
                    result = env.advance_round(batch_size=30, policy=policy, seed=seed + round_index)
                    state = env.observe_state()
                    trajectories.append({"dataset": "UCI_WDBC", "mode": "REPLAY_MODE_SIMULATION", "seed": seed, "budget": budget, "policy": policy, "round": round_index, "feedback_count": state["visible_label_count"], "round_revealed": result.get("revealed_label_count", 0), "round_cost": result.get("predicted_cost", 0.0), "remaining_budget": state["remaining_budget"]})
                    if result["status"] == "EXHAUSTED": break
                final = env.finalize().get("metrics", {})
                state = env.observe_state()
                records.append({"dataset": "UCI_WDBC", "mode": "REPLAY_MODE_SIMULATION", "seed": seed, "budget": budget, "policy": policy, "feedback_count": state["visible_label_count"], "spent_cost": budget - float(state["remaining_budget"]), "remaining_budget": state["remaining_budget"], "roc_auc": final.get("roc_auc"), "average_precision": final.get("average_precision")})
    fields = list(records[0])
    with (OUT / "uci_wdbc_replay_matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(records)
    with (OUT / "uci_wdbc_replay_trajectories.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(trajectories[0])); writer.writeheader(); writer.writerows(trajectories)
    comparisons = []
    for budget in (30.0, 60.0, 90.0):
        for metric in ("roc_auc", "average_precision", "feedback_count", "spent_cost"):
            pairs = []
            for seed in range(5):
                lrbe = next(row for row in records if row["seed"] == seed and row["budget"] == budget and row["policy"] == "LRBE-Uncertainty")
                random = next(row for row in records if row["seed"] == seed and row["budget"] == budget and row["policy"] == "Random")
                pairs.append(float(lrbe[metric] or 0.0) - float(random[metric] or 0.0))
            comparisons.append({"budget": budget, "comparison": "LRBE-Uncertainty minus Random", "metric": metric, "effect_size_mean": mean(pairs), "ci_95_normal": _ci(pairs), "n_seeds": len(pairs)})
    metadata = {"source": "UCI Wisconsin Diagnostic Breast Cancer via sklearn.datasets.load_breast_cancer", "license": "UCI dataset terms; verify before competition redistribution", "domain": "medical diagnosis (non-credit)", "decision_semantics": "synthetic replay threshold; not historical clinical workflow", "visibility_semantics": "private evaluator retains labels; protocol hides candidate labels", "observation_action": "offline replay only", "cost": "synthetic proxy cost", "time_ordering": "synthetic decision_time before outcome_time", "simulation": True, "matrix": "5 seeds × 3 budgets × 3 policies", "effect_sizes": comparisons, "competition_ready": False}
    (OUT / "uci_wdbc_replay_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__": main()
