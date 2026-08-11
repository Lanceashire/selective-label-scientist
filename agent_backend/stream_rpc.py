"""One-request JSONL RPC with real per-round experiment progress for desktop Agent streaming."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from .rpc import dispatch
from .runtime import ResearchRuntime

def emit(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False), flush=True)

def main() -> int:
    for line in sys.stdin:
        try:
            query = json.loads(line)
            action = str(query.get("action", ""))
            payload = dict(query.get("payload", {}))
            if action != "run_experiment":
                emit(dispatch(action, payload))
                continue
            runtime = ResearchRuntime(payload.get("state_dir") or Path.home() / ".ecomic")
            try:
                result = runtime.run_experiment(str(payload["session_id"]), str(payload["plan_id"]), str(payload["policy"]), float(payload["budget"]), int(payload.get("seed", 0)), int(payload["rounds"]), progress=emit)
            finally:
                runtime.close()
            emit(result)
        except Exception as error:
            emit({"status": "ERROR", "message": str(error)})
    return 0

if __name__ == "__main__": raise SystemExit(main())