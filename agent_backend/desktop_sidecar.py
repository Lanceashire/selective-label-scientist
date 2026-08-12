"""JSONL desktop sidecar with one stable RPC response contract."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .rpc import active_runtime_count, close_all_runtimes, dispatch, inspect_dataset


def respond(request_id: str, *, ok: bool, data: object = None, code: str | None = None, message: str | None = None) -> None:
    """Write exactly one JSON RPC response to stdout; diagnostics belong on stderr."""
    response = {"request_id": request_id, "ok": ok, "data": data, "error": None}
    if not ok:
        response["error"] = {"code": code or "BACKEND_ERROR", "message": message or "Backend request failed."}
    print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)

def emit_progress(request_id: str, stage: str, percent: int) -> None:
    """Emit a bounded in-band notification; it is not an RPC response envelope."""
    event = {
        "event": {
            "type": "precheck_progress",
            "request_id": request_id,
            "stage": stage,
            "percent": max(0, min(100, int(percent))),
        }
    }
    print(json.dumps(event, ensure_ascii=False, separators=(",", ":")), flush=True)


def error_code(error: Exception) -> str:
    name = type(error).__name__.upper()
    return "_".join(part for part in name.replace("ERROR", "_ERROR").split("_") if part) or "BACKEND_ERROR"


def main() -> int:
    # Windows console code pages must never affect the Rust JSONL protocol.
    sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    state_dir = Path(os.environ.get("ECOMIC_STATE_DIR", Path.cwd() / "state"))
    state_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()
    requests = 0
    for raw_line in sys.stdin:
        request_id = "req_invalid"
        try:
            request = json.loads(raw_line)
            if not isinstance(request, dict):
                raise ValueError("request must be a JSON object")
            request_id = str(request.get("request_id") or f"req_{requests + 1}")
            action = str(request.get("action", ""))
            payload = dict(request.get("payload", {}))
            requests += 1
            if action == "health_check":
                respond(request_id, ok=True, data={"status": "OK", "backend": "ready", "database": "ready", "agent_host": "idle", "pid": os.getpid(), "started_at": started_at, "request_count": requests, "runtime_count": active_runtime_count()})
                continue
            if action == "shutdown":
                close_all_runtimes()
                respond(request_id, ok=True, data={"status": "OK", "stopped": True})
                return 0
            payload.setdefault("state_dir", str(state_dir))
            if action == "inspect_dataset":
                output = inspect_dataset(str(payload["path"]), progress=lambda stage, percent: emit_progress(request_id, stage, percent))
            else:
                output = dispatch(action, payload, persistent=True)
            respond(request_id, ok=True, data=output)
        except Exception as error:  # transport boundary: convert all backend failures to one contract
            print(f"ECOMIC sidecar request failed ({request_id}): {error}", file=sys.stderr, flush=True)
            respond(request_id, ok=False, code=error_code(error), message=str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())