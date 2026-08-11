# Loop 13 Gate — PASS

PyInstaller creates `release/runtime/ecomic-backend.exe` (133,914,858 bytes) from the official long-lived JSONL sidecar entrypoint. The executable bundles ECOMIC backend code and the runtime dependencies used by the research workflow, including DuckDB, NumPy, SciPy, scikit-learn and PyArrow.

PASS: direct EXE health check succeeds with PATH restricted to `C:\Windows\System32;C:\Windows`.
PASS: independent acceptance script runs CSV import, Session creation, DomainSpec confirmations, hypothesis/plan creation and a two-round smoke experiment with `python_on_path=false`.
PASS: executable exits through the JSONL shutdown protocol.