import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_sandiego_historical_audit import run_audit


class SanDiegoHistoricalAuditTests(unittest.TestCase):
    def test_real_selection_audit_does_not_impute_unsearched_outcomes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "stops.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["searched", "contraband_found", "date_time", "stop_cause", "service_area", "subject_race", "subject_sex", "subject_age", "sd_resident", "arrested"])
                writer.writeheader()
                writer.writerows([
                    {"searched": "Y", "contraband_found": "Y", "date_time": "2018-01-01 10:00:00"},
                    {"searched": "Y", "contraband_found": "N", "date_time": "2018-01-02 10:00:00"},
                    {"searched": "N", "contraband_found": "", "date_time": "2018-01-03 10:00:00"},
                    {"searched": "N", "contraband_found": "", "date_time": "2018-01-04 10:00:00"},
                ])
            result = run_audit(source, root / "out")
            availability = next(check for check in result["audit"]["checks"] if check["name"] == "label_availability")
            self.assertEqual(availability["status"], "PASS")
            self.assertEqual(availability["max_visible_rate_difference"], 1.0)
            self.assertEqual(result["metadata"]["eligibility"]["dynamic_oracle_evaluation"], "BLOCKED")
            saved = json.loads((root / "out" / "san_diego_historical_selection_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["historical_selection_counts"]["missing_contraband_labels"], 2)
