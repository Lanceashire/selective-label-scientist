from __future__ import annotations

import json, os, subprocess, sys, tempfile, unittest


class DesktopSidecarTests(unittest.TestCase):
    def test_persistent_health_protocol_has_twenty_successful_requests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            process = subprocess.Popen([sys.executable, "-m", "agent_backend.desktop_sidecar"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", env={**os.environ, "ECOMIC_STATE_DIR": directory})
            assert process.stdin and process.stdout
            try:
                pids = set()
                for expected_count in range(1, 21):
                    process.stdin.write('{"action":"health_check","payload":{}}\n'); process.stdin.flush()
                    response = json.loads(process.stdout.readline())
                    self.assertEqual(response["status"], "OK"); self.assertEqual(response["backend"], "正常"); self.assertEqual(response["database"], "正常"); self.assertEqual(response["request_count"], expected_count); pids.add(response["pid"])
                self.assertEqual(len(pids), 1)
                process.stdin.write('{"action":"shutdown","payload":{}}\n'); process.stdin.flush(); self.assertTrue(json.loads(process.stdout.readline())["stopped"]); self.assertEqual(process.wait(timeout=5), 0)
            finally:
                if process.poll() is None: process.kill(); process.wait()
                process.stdin.close(); process.stdout.close()
