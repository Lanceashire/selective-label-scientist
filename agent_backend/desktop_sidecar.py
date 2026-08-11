"""Long-lived UTF-8 JSONL backend process for ECOMIC Desktop."""
from __future__ import annotations
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from .rpc import dispatch

def respond(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")), flush=True)

def main() -> int:
    # Windows console code pages must never affect the Rust JSONL protocol.
    sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    started_at = datetime.now(timezone.utc).isoformat(); state_dir = Path(os.environ.get("ECOMIC_STATE_DIR") or Path.home() / ".ecomic"); requests = 0
    for raw_line in sys.stdin:
        requests += 1
        try:
            request = json.loads(raw_line); action = str(request.get("action", "")); payload = dict(request.get("payload", {}))
            if action == "health_check": respond({"status":"OK","backend":"正常","database":"正常","agent_host":"未启动","pid":os.getpid(),"started_at":started_at,"request_count":requests}); continue
            if action == "shutdown": respond({"status":"OK","stopped":True}); return 0
            payload.setdefault("state_dir", str(state_dir)); respond({"status":"OK","result":dispatch(action, payload)})
        except Exception as error: respond({"status":"ERROR","message":str(error)})
    return 0

if __name__ == "__main__": raise SystemExit(main())
