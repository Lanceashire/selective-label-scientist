"""Audit a real historical selective-label dataset without inventing missing labels.

The City of San Diego vehicle-stops release records whether an officer searched a
vehicle and records contraband fields in the historical administrative record.
It is useful for a non-credit historical-selection audit, but it is deliberately
not an oracle-labelled dynamic-policy benchmark.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from agent_backend.domains.semantic_auditor import audit_semantics


ROOT = Path(__file__).parents[1]
DEFAULT_INPUT = ROOT / "benchmarks" / "data" / "san_diego_vehicle_stops_2017_2018.csv"
DEFAULT_OUTPUT = ROOT / "benchmarks" / "results"
SOURCE_URL = "https://seshat.datasd.org/police_vehicle_stops/vehicle_stops_final_datasd.csv"
SOURCE_PAGE = "https://data.sandiego.gov/datasets/police-vehicle-stops/"


def _read_rows(source: Path) -> list[dict[str, str]]:
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("San Diego CSV is missing a header")
        required = {"searched", "contraband_found", "date_time"}
        missing = sorted(required - set(reader.fieldnames))
        if missing:
            raise ValueError(f"San Diego CSV is missing required columns: {', '.join(missing)}")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def build_spec() -> dict[str, Any]:
    """Return only semantics supported by the public data dictionary."""
    return {
        "domain_name": "san-diego-police-vehicle-searches",
        "features": ["stop_cause", "service_area", "subject_race", "subject_sex", "subject_age", "sd_resident", "arrested"],
        "historical_decision": {"column": "searched", "observed_action_values": ["Y"], "non_observed_action_values": ["N"], "unknown_action_values": [""], "confidence": 1.0, "confirmed": True},
        "outcome": {"column": "contraband_found"},
        "observation_cost": {"column": None, "proxy": False, "description": "No observation-cost field is present in this release."},
        "observation_action": {"description": "Officer vehicle/person search following a vehicle stop; the public release retains a contraband field as administrative evidence.", "reversible": False, "simulatable": False, "confirmed": True},
        "selection_mechanism": {"type": "historical-search-selection", "simulated": False, "mode": "HISTORICAL_SELECTION_AUDIT"},
        "time": {"decision_time": "date_time", "outcome_time": None},
    }


def run_audit(source: Path, output: Path) -> dict[str, Any]:
    rows = _read_rows(source)
    audit = audit_semantics(build_spec(), rows, "Real City of San Diego vehicle-stop history; missing and unexpected administrative values are retained, never imputed.")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    searched = sum(row["searched"] == "Y" for row in rows)
    unsearched = sum(row["searched"] == "N" for row in rows)
    label_visible = sum(bool(row["contraband_found"]) for row in rows)
    unsearched_visible = sum(row["searched"] == "N" and bool(row["contraband_found"]) for row in rows)
    metadata: dict[str, Any] = {
        "dataset": "City of San Diego Police Vehicle Stops (Oct 2017–Jun 2018, new format)",
        "source_url": SOURCE_URL,
        "source_page": SOURCE_PAGE,
        "license": "City of San Diego Open Data portal; verify portal license terms before redistribution.",
        "sha256": digest,
        "domain": "police vehicle stops / public safety (non-credit)",
        "rows": len(rows),
        "historical_decision_semantics": "searched=Y means an officer conducted a search; searched=N means no recorded search.",
        "visibility_semantics": "All searched=Y records have contraband_found values. The downloaded file also has a small number of searched=N records with values, so this is strong descriptive evidence that requires source-level reconciliation rather than an assumed perfect mapping.",
        "observation_action": "physical police search; irreversible and not safely simulatable by this project.",
        "cost": "No observation-cost field is released; no synthetic cost is added.",
        "time_ordering": "date_time records the stop/decision time, but the release has no separate contraband-observation timestamp; ordering remains unconfirmed.",
        "simulation": False,
        "historical_selection_counts": {"searched": searched, "unsearched": unsearched, "visible_contraband_labels": label_visible, "visible_contraband_labels_when_unsearched": unsearched_visible, "missing_contraband_labels": len(rows) - label_visible},
        "eligibility": {"historical_selection_audit": "SUPPORTED_WITH_LIMITATIONS", "dynamic_oracle_evaluation": "BLOCKED", "reason": "Most unsearched stops have no contraband label, a small subset has an unexpected recorded value, and the release has no separate outcome timestamp. ECOMIC must not invent or silently reconcile missing labels before final evaluation."},
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "san_diego_historical_selection_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "san_diego_historical_selection_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"audit": audit, "metadata": metadata}


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit San Diego historical search-label availability without imputing hidden outcomes.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run_audit(args.input.expanduser().resolve(), args.output.expanduser().resolve())
    print(json.dumps({"status": result["audit"]["status"], "rows": result["metadata"]["rows"], "sha256": result["metadata"]["sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
