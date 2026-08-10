from __future__ import annotations

import unittest
from pathlib import Path

from agent_backend.domains.credit_reference_adapter import CreditReferenceAdapter


class CreditReferenceAdapterTests(unittest.TestCase):
    def test_reference_is_read_only_and_frozen_files_are_recorded(self):
        root = Path(__file__).parents[1] / "vendor" / "LexiRiskLabel"
        if not (root / "src" / "phase0_engine.py").exists():
            self.skipTest("未克隆 LexiRiskLabel；vendor/README.md 提供只读克隆命令")
        adapter = CreditReferenceAdapter(root)
        manifest = adapter.manifest()
        self.assertTrue(manifest["read_only"])
        self.assertIn("src/phase0_engine.py", manifest["frozen_files"])
        summary = adapter.frozen_result_summary(limit=1)
        self.assertTrue(summary["read_only"])

