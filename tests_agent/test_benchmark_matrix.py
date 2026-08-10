import csv
import subprocess
import sys
import unittest
from pathlib import Path

class BenchmarkMatrixTests(unittest.TestCase):
    def test_noncredit_replay_matrix_has_required_coverage(self):
        root=Path(__file__).parents[1]
        subprocess.run([sys.executable,"scripts/run_noncredit_benchmark.py"],cwd=root,check=True)
        with (root/"benchmarks/results/uci_wdbc_replay_matrix.csv").open(encoding="utf8",newline="") as handle:
            rows=list(csv.DictReader(handle))
        self.assertEqual(len(rows),45)
        self.assertEqual({r["mode"] for r in rows},{"REPLAY_MODE_SIMULATION"})
        self.assertEqual({r["policy"] for r in rows},{"Random","CountOnly-MinCost","LRBE-Uncertainty"})
        self.assertEqual({r["seed"] for r in rows},{"0","1","2","3","4"})
        self.assertEqual({r["budget"] for r in rows},{"30.0","60.0","90.0"})
