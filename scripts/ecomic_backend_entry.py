import sys
from agent_backend.desktop_sidecar import main as sidecar_main
from agent_backend.stream_rpc import main as stream_main

if __name__ == "__main__":
    raise SystemExit(stream_main() if "--stream" in sys.argv[1:] else sidecar_main())