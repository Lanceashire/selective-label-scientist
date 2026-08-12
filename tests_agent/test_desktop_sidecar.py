from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest


class DesktopSidecarTests(unittest.TestCase):
    def start_sidecar(self, directory: str) -> subprocess.Popen[str]:
        return subprocess.Popen(
            [sys.executable, "-m", "agent_backend.desktop_sidecar"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env={**os.environ, "ECOMIC_STATE_DIR": directory},
        )

    @staticmethod
    def request(process: subprocess.Popen[str], request_id: str, action: str, payload: dict | None = None) -> dict:
        assert process.stdin and process.stdout
        process.stdin.write(json.dumps({"request_id": request_id, "action": action, "payload": payload or {}}) + "\n")
        process.stdin.flush()
        return json.loads(process.stdout.readline())

    def test_persistent_health_protocol_uses_one_success_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            process = self.start_sidecar(directory)
            try:
                pids = set()
                for expected_count in range(1, 21):
                    response = self.request(process, f"req_health_{expected_count}", "health_check")
                    self.assertEqual(response["request_id"], f"req_health_{expected_count}")
                    self.assertTrue(response["ok"])
                    self.assertIsNone(response["error"])
                    self.assertEqual(response["data"]["status"], "OK")
                    self.assertEqual(response["data"]["request_count"], expected_count)
                    pids.add(response["data"]["pid"])
                self.assertEqual(len(pids), 1)
                shutdown = self.request(process, "req_shutdown", "shutdown")
                self.assertTrue(shutdown["ok"])
                self.assertTrue(shutdown["data"]["stopped"])
                self.assertEqual(process.wait(timeout=5), 0)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if process.stdin:
                    process.stdin.close()
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()

    def test_invalid_action_is_a_typed_failure_not_a_fake_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            process = self.start_sidecar(directory)
            try:
                response = self.request(process, "req_invalid", "invalid_action")
                self.assertEqual(response["request_id"], "req_invalid")
                self.assertFalse(response["ok"])
                self.assertIsNone(response["data"])
                self.assertEqual(response["error"]["code"], "VALUE_ERROR")
                self.assertIn("unknown typed tool", response["error"]["message"])
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if process.stdin:
                    process.stdin.close()
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
    def test_precheck_emits_real_ordered_progress_before_its_response(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "progress.csv")
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write("decision,label,cost\nyes,1,2\nno,0,3\n")
            process = self.start_sidecar(directory)
            try:
                assert process.stdin and process.stdout
                process.stdin.write(json.dumps({"request_id": "req_precheck", "action": "inspect_dataset", "payload": {"path": path}}) + "\n")
                process.stdin.flush()
                events: list[dict] = []
                response: dict | None = None
                while response is None:
                    frame = json.loads(process.stdout.readline())
                    if "event" in frame:
                        events.append(frame["event"])
                    else:
                        response = frame
                self.assertTrue(response["ok"])
                stages = [event["stage"] for event in events]
                self.assertEqual(list(dict.fromkeys(stages)), ["读取文件", "解析 Schema", "统计字段", "生成样本", "完成"])
                self.assertEqual([event["percent"] for event in events], sorted(event["percent"] for event in events))
                self.assertEqual(events[-1]["percent"], 100)
                self.assertTrue(all(event["request_id"] == "req_precheck" for event in events))
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if process.stdin:
                    process.stdin.close()
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
    def test_burst_of_mixed_requests_completes_without_deadlock(self) -> None:
        """A sidecar must drain a queued mixed burst without a permanent read lock."""
        with tempfile.TemporaryDirectory() as directory:
            process = self.start_sidecar(directory)
            try:
                assert process.stdin and process.stdout
                expected: dict[str, str] = {}
                for index in range(100):
                    request_id = f"req_burst_{index}"
                    action = ("health_check", "list_sessions", "get_session", "chart_data")[index % 4]
                    payload = {} if action in {"health_check", "list_sessions"} else {"session_id": "session_missing"}
                    expected[request_id] = action
                    process.stdin.write(json.dumps({"request_id": request_id, "action": action, "payload": payload}) + "\n")
                process.stdin.flush()

                responses: list[dict] = []
                import threading
                reader = threading.Thread(
                    target=lambda: [responses.append(json.loads(process.stdout.readline())) for _ in range(100)],
                    daemon=True,
                )
                reader.start()
                reader.join(timeout=15)
                self.assertFalse(reader.is_alive(), "sidecar did not drain the mixed request burst")
                self.assertEqual(len(responses), 100)
                self.assertEqual({response["request_id"] for response in responses}, set(expected))
                for response in responses:
                    if expected[response["request_id"]] in {"health_check", "list_sessions"}:
                        self.assertTrue(response["ok"])
                    else:
                        self.assertFalse(response["ok"])
                self.assertTrue(self.request(process, "req_shutdown_burst", "shutdown")["ok"])
                self.assertEqual(process.wait(timeout=5), 0)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if process.stdin:
                    process.stdin.close()
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
    def test_cancelled_precheck_releases_file_and_fresh_sidecar_recovers(self) -> None:
        """Desktop cancellation restarts only the local sidecar; the source must be immediately usable again."""
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "cancel.csv")
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write("id,decision,label,cost\n")
                for index in range(250_000):
                    handle.write(f"{index},{'reviewed' if index % 4 == 0 else 'hidden'},{index % 2},1\n")
            process = self.start_sidecar(directory)
            try:
                assert process.stdin and process.stdout
                process.stdin.write(json.dumps({"request_id": "req_cancel", "action": "inspect_dataset", "payload": {"path": path}}) + "\n")
                process.stdin.flush()
                first = json.loads(process.stdout.readline())
                self.assertEqual(first["event"]["type"], "precheck_progress")
                self.assertEqual(first["event"]["stage"], "读取文件")
                process.kill()
                self.assertIsNotNone(process.wait(timeout=10))

                moved = path + ".moved"
                os.replace(path, moved)
                os.replace(moved, path)

                replacement = self.start_sidecar(directory)
                try:
                    recovered = self.request(replacement, "req_recovered", "health_check")
                    self.assertTrue(recovered["ok"])
                    self.assertEqual(recovered["data"]["status"], "OK")
                finally:
                    if replacement.poll() is None:
                        replacement.kill()
                        replacement.wait()
                    if replacement.stdin:
                        replacement.stdin.close()
                    if replacement.stdout:
                        replacement.stdout.close()
                    if replacement.stderr:
                        replacement.stderr.close()
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if process.stdin:
                    process.stdin.close()
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
    def test_sidecar_reuses_runtime_until_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_path = os.path.join(directory, "runtime.csv")
            with open(csv_path, "w", encoding="utf-8", newline="") as handle:
                handle.write("decision,label\nreviewed,1\nnot_reviewed,0\n")
            process = self.start_sidecar(directory)
            try:
                self.assertEqual(self.request(process, "req_before", "health_check")["data"]["runtime_count"], 0)
                loaded = self.request(process, "req_load", "load_dataset", {"path": csv_path})
                self.assertTrue(loaded["ok"])
                after = self.request(process, "req_after", "health_check")
                self.assertEqual(after["data"]["runtime_count"], 1)
                self.assertTrue(self.request(process, "req_shutdown", "shutdown")["ok"])
                self.assertEqual(process.wait(timeout=5), 0)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if process.stdin:
                    process.stdin.close()
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
    def test_twenty_sidecar_restart_cycles_recover_without_orphans(self) -> None:
        """Exercise the backend restart boundary repeatedly: each replacement must answer health."""
        with tempfile.TemporaryDirectory() as directory:
            terminated_pids: set[int] = set()
            for index in range(20):
                process = self.start_sidecar(directory)
                try:
                    before = self.request(process, f"req_soak_{index}_before", "health_check")
                    self.assertTrue(before["ok"])
                    pid = int(before["data"]["pid"])
                    self.assertEqual(pid, process.pid)
                    process.kill()
                    self.assertIsNotNone(process.wait(timeout=5))
                    terminated_pids.add(pid)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=5)
                    if process.stdin:
                        process.stdin.close()
                    if process.stdout:
                        process.stdout.close()
                    if process.stderr:
                        process.stderr.close()

                replacement = self.start_sidecar(directory)
                try:
                    after = self.request(replacement, f"req_soak_{index}_after", "health_check")
                    self.assertTrue(after["ok"])
                    self.assertEqual(after["data"]["status"], "OK")
                    self.assertNotIn(int(after["data"]["pid"]), terminated_pids)
                finally:
                    if replacement.poll() is None:
                        replacement.kill()
                        replacement.wait(timeout=5)
                    if replacement.stdin:
                        replacement.stdin.close()
                    if replacement.stdout:
                        replacement.stdout.close()
                    if replacement.stderr:
                        replacement.stderr.close()