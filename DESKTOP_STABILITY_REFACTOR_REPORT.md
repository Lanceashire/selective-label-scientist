# ECOMIC Desktop Stability Refactor Report

> Status: **IN PROGRESS** — this report is an evidence ledger, not a declaration that the desktop application is release-ready.
>
> Updated: 2026-08-12 (Asia/Shanghai)

## A. Architecture

### Before

```text
React invoke → synchronous Rust bridge / one global lock → one-shot Python backend
Pi tool call → repeatedly spawn onefile Python executable
```

Failures could be hidden by shape mismatches, unbounded blocking reads, optional catches, or pages without explicit error states.

### After

```text
React state machines + ErrorBoundary
  → Tauri invoke
  → Rust RpcManager (request_id, JSONL framing cap, timeout, sidecar restart)
  → persistent Python sidecar (JSONL success/error envelope)
  → SQLite + DuckDB scientific runtime

Rust TaskManager → persistent-per-Scientist-task Node runner
                 → persistent Python worker for typed tools
```

Python remains the boundary for DuckDB, NumPy/SciPy/sklearn and selective-label scientific computations. No research semantics, Oracle isolation, or final-evaluation gate was intentionally changed.

## B. Requirement ledger

Legend: **FIXED** = implementation plus direct local evidence; **PARTIAL** = implementation exists but full required evidence or scope is incomplete; **NOT FIXED** = not yet implemented/proven.

### P0

| Item | Status | Evidence / remaining condition |
|---|---|---|
| P0-1 RPC envelope | FIXED | `agent_backend/desktop_sidecar.py`; sidecar protocol tests. |
| P0-2 error propagation | FIXED | `ok:false` envelope converts to Rust `Err`; typed invalid-action test. |
| P0-3 Dataset blank screen | FIXED | runtime validator, page states, ErrorBoundary, preview UI tests. |
| P0-4 History RPC shape | FIXED | parsed bridge/history page tests. |
| P0-5 Workbench shape | FIXED | parsed research session and explicit error state. |
| P0-6 ExperimentCharts | FIXED | loading/error/retry test coverage. |
| P0-7 ReportViewer | FIXED | loading/error/retry test coverage. |
| P0-8 report location | FIXED | bridge reads validated report document before open. |
| P0-9 DomainSpec fake success | FIXED | atomic backend transaction and wizard test. |
| P0-10 delete Session fake success | PARTIAL | backend deletion is transactional; full desktop failure-injection E2E pending. |
| P0-11 blocking read lock | FIXED | async reader thread + pending request map. |
| P0-12 RPC timeout | FIXED | action-specific deadline in Rust RpcManager. |
| P0-13 sidecar restart | FIXED | timed-out/failed sidecar is invalidated and restarted on next request. |
| P0-14 JSONL framing | FIXED | 4 MiB cap, malformed/missing request ID detection. |
| P0-15 background Scientist | FIXED | immediate task ID, background Rust TaskManager. |
| P0-16 Scientist cancel | FIXED | cancel command with task state and events. |
| P0-17 Scientist deadline | FIXED | 30-minute hard deadline and process termination. |
| P0-18 Node tool timeout | FIXED | persistent Node worker uses per-request timeout. |
| P0-19 no onefile per tool | FIXED | one persistent Python worker per Scientist task. |
| P0-20 onefile reassessment | PARTIAL | persistent worker eliminates per-tool cold start; onefile benchmark/report still pending. |
| P0-21 repeated CSV scans | FIXED | DuckDB materialization plus aggregate profile scan. |
| P0-22 large-data sampling | FIXED | bounded profile sample and approximate cardinality. |
| P0-23 validation extra scan | FIXED | CSV structural validation and SHA-256 in one pass. |
| P0-24 precheck progress/cancel | FIXED | actual Python stage events, Tauri forwarding, progress UI and cancellation test. |

### P1

| Item | Status | Evidence / remaining condition |
|---|---|---|
| P1-1 inspect/load reuse | FIXED | retained `DatasetHandle`; source-delete reuse test. |
| P1-2 session metadata | FIXED | SQLite `session_metadata`. |
| P1-3 resume avoids profile scan | FIXED | resume uses persisted metadata; source-delete test. |
| P1-4 report without source | FIXED | History opens report directly; bundled workflow generates/reads report. |
| P1-5 experiment without rematerialization | PARTIAL | UI avoids resume for report/history; full experiment navigation E2E pending. |
| P1-6 >100k unified capability | PARTIAL | inspect supports million rows; experiment materialization intentionally bounded at 100k. |
| P1-7 repeated DatasetHandle open | FIXED | persistent runtime retains up to two session-scoped DuckDB handles; direct regression proves confirmed Session work performs zero source reopen calls. |
| P1-8 persistent SQLite connection | FIXED | real sidecar reuses one runtime; black-box health diagnostics prove runtime count stays at 1 across load/health and shutdown closes it. |
| P1-9 SQLite busy timeout | FIXED | every DatabaseManager configures 5000 ms timeout and WAL; a two-connection competing-writer regression proves the waiting writer recovers after the owned lock is released without `database is locked`. |
| P1-10 progress refresh storm | FIXED | 250ms coalescing, max-one in-flight refresh, and 1000-event direct regression test. |
| P1-11 coalescing | FIXED | `ResearchWorkbench` queue/timer logic verified with 1000 progress events → one scheduled refresh. |
| P1-12 bounded LLM experiment payload | FIXED | `run_experiment` returns only compact researcher-visible summary plus artifact reference; full rounds stay local; direct regression rejects observations/selected IDs in RPC result. |
| P1-13 event accumulation | FIXED | Rust emits Scientist events immediately; task stores status only. |
| P1-14 chart response bound | FIXED | chart trajectory is deterministically capped at 2,000 points; run/hypothesis timelines are bounded, with total/downsample metadata and artifact-backed source detail. |
| P1-15 Recharts downsample | FIXED | frontend independently caps trajectory rendering at 2,000 points and displays an explicit sampled-data notice; regression covers oversized backend data. |
| P1-16 empty catches | FIXED | production-source audit across desktop/agent/backend excludes historical `.bak` snapshots and found no `.catch(() => undefined)` or empty `catch`; failures use explicit state/log/retry paths. |
| P1-17 ErrorBoundary | FIXED | global `DesktopErrorBoundary`. |
| P1-18 HealthCard error state | FIXED | HealthCard catches rejected health RPCs, exits busy state, renders `后端不可用` with a retry action; direct UI regression covers rejection. |
| P1-19 stderr handling | FIXED | backend, Scientist and Provider probe stderr are drained to rotating local diagnostics instead of being discarded. |
| P1-20 secret-safe logs | FIXED | diagnostics redact Authorization, Bearer tokens and all supported provider API-key environment names before any local write; direct regression covers credential removal. |
| P1-21 request IDs | FIXED | all sidecar RPC requests use request IDs. |
| P1-22 TaskManager | PARTIAL | Scientist task manager implemented; dataset/provider tasks are not unified TaskManager tasks. |
| P1-23 process-tree cleanup | PARTIAL | Windows taskkill `/T` on cancel/timeout; process-level precheck cancellation proves file release and fresh sidecar recovery. App-exit soak with active backend/Scientist children remains pending. |
| P1-24 navigation duplicates | PARTIAL | active Scientist task guard exists; all long task/page-transition E2E pending. |

### P2 / build reproducibility

| Item | Status | Evidence / remaining condition |
|---|---|---|
| P2-1 production WDIO removal | FIXED | WDIO/WebDriver removed from release Cargo dependencies and lockfile, production capability, Rust startup and frontend entrypoint; `verify-production-bundle.ps1` is enforced in Windows CI. |
| Pi commit pin | FIXED | CI pins `2a9b4ebc680053c64e31f635b0b22d5e22564001`. |
| Windows non-health CI gate | PARTIAL | CI now runs bundled backend non-health workflow; native Tauri GUI E2E is still pending. |

## C. Executed evidence

| Name | Command | Result |
|---|---|---|
| Python full regression | `python -m unittest discover -s tests_agent -p "test_*.py" -v` | PASS (39 tests, 1 external-reference skip; 83.342 s). |
| SQLite competing writer recovery | `python -m unittest tests_agent.test_sqlite_busy_timeout -v` | PASS: two tests; a second SQLite connection waits during a short `BEGIN IMMEDIATE` lock then commits successfully after release. |
| Persistent sidecar runtime | `python -m unittest tests_agent.test_desktop_sidecar` | PASS (runtime count 0 → 1 across load/health; clean shutdown). |
| Node regression | `node --test tests_node/*.test.mjs` | PASS (13 tests). |
| Frontend full regression | `npm --prefix desktop run test -- --run` | PASS (10 files, 27 tests). |
| Progress storm regression | `npm --prefix desktop run test -- --run src/ResearchWorkbench.test.tsx` | PASS (1000 events → one scheduled refresh). |
| Runtime response/chart bounds | `python -m unittest tests_agent.test_runtime_stability_bounds` | PASS: compact experiment result has no observations; 2,505 artifact points return as ≤2,000 chart points with downsample marker; session cache prevents source reopen. |
| Ingestion scan budget | `python -m unittest tests_agent.test_ingestion_scan_budget` | PASS: 100k-row and 200-column datasets; one `read_csv_auto` source parse per dataset, later profile queries use materialized DuckDB table. |
| Sidecar queued burst | `python -m unittest tests_agent.test_desktop_sidecar` | PASS: 100 mixed health/list/get/chart requests drain without deadlock. |
| Precheck cancellation/recovery | `python -m unittest tests_agent.test_desktop_sidecar` | PASS: after a 250k-row precheck emits first progress, termination releases the file for rename and a fresh sidecar health check succeeds. |
| Backend restart soak | `python -m unittest tests_agent.test_desktop_sidecar.DesktopSidecarTests.test_twenty_sidecar_restart_cycles_recover_without_orphans -v` | PASS: 20 forced sidecar exits, each followed by a fresh health response; completed in 49.451 s with no reused terminated PID. |
| Desktop cleanup and diagnostic redaction | `cargo test --release --manifest-path desktop/src-tauri/Cargo.toml process_cleanup_tests -- --nocapture` | PASS: 2 tests: Windows task-tree cleanup terminated owned Scientist parent/descendants, and diagnostics removed Authorization/Bearer/provider credential values. This command is enforced in Windows CI. |
| Production empty-catch audit | `rg -n -U --glob '!*.bak' ... desktop/src agent agent_backend` | PASS: no empty `catch` or `.catch(() => undefined)` in current production sources; historical snapshots are excluded from builds. |
| HealthCard rejected RPC | `npm --prefix desktop run test -- --run src/bridge-ui.test.tsx` | PASS: 2 tests, including rejected health RPC rendered as a recoverable `后端不可用` state and retry button. |
| Frontend production build | `npm --prefix desktop run build` | PASS. |
| Rust release check | `cargo check --release` | PASS. |
| Production WDIO exclusion | `scripts/verify-production-bundle.ps1` | PASS: no WDIO/WebDriver reference in release Cargo/lock, capability, Rust startup or frontend entrypoint; also wired into Windows CI. |
| Bundled backend workflow | `powershell -File scripts/verify-backend-exe.ps1` | PASS: inspect/load/list/get/chart/DomainSpec/run/generate/read report; `python_on_path=false`. |
| Release EXE start/exit | direct release executable process check | PASS: 12-second startup alive, GPU-safe flags present, WebView children cleaned after exit. |
| Final Windows installer build | `npm --prefix desktop run tauri:build` | PASS: final package includes the HealthCard rejected-RPC recovery, secure diagnostics and current bundled runtime. NSIS installer: `desktop/src-tauri/target/release/bundle/nsis/ECOMIC Desktop_0.3.0_x64-setup.exe` (247,779,779 bytes; SHA-256 `6A2FD4E250AA2C39D23327C60F4DF01D5F07A1E82ABFAFADD2AD495F461EF363`). |
| Final isolated installer acceptance | NSIS silent install into `build/installer-final-healthcard-20260812` | PASS: installer exit code 0; installed `ecomic-agent/ecomic-backend.exe` SHA-256 matches current rebuilt `release/runtime/ecomic-backend.exe` (`FFEFE0A27AEFC9334B923A0900CD77ECF2246ABD5D09AF3C89E4AB5621BE9E11`). |
| Final installed desktop startup/normal exit | launch final installed `ecomic-desktop.exe`, observe 12 s, then request normal window close | PASS: main process remained alive; normal close request accepted; after 10 seconds zero desktop/WebView/Node/backend processes with executable path or command line under the isolated installation directory remained. |

## D. Performance evidence

No machine-independent benchmark numbers are claimed yet. The following structural evidence exists:

- CSV validation and SHA-256 share one streaming pass.
- `read_csv_auto` source materialization occurs once per inspect, then profile queries target a DuckDB temp table.
- Missing/cardinality uses one aggregate query; top values use at most 10,000 sampled rows.
- Agent typed tool calls reuse a worker rather than spawning a Python onefile executable for every tool.

Still required: recorded timings for cold start, 100k/1M inspect, 200-column dataset, create/resume, scientist tool latency, and onefile comparison.

## E. Process cleanup evidence

- Implemented: sidecar invalidation/restart; Scientist timeout/cancel; Windows process-tree termination; release EXE startup and WebView child cleanup check.
- Verified at unit/process level: 20 forced sidecar restart cycles each regained health; Windows `shutdown_desktop_tasks` terminated a live owned Scientist process tree (parent plus descendants) and the regression is now a Windows CI gate.
- Verified with the final installer SHA `6A2FD4E250AA2C39D23327C60F4DF01D5F07A1E82ABFAFADD2AD495F461EF363`: its isolated installation stayed alive for 12 seconds, accepted a normal Windows close request, and after 10 seconds left zero processes with executable path or command line under its installation directory.
- A pre-existing source-runtime Python/backend process tree was observed during the earlier installer check; it was not terminated because it does not belong to either isolated acceptance installation. Still required: 50-cycle start/cancel soak, the equivalent 20-cycle automatic restart soak through the live Rust/Tauri bridge, and application-exit inventory with an actively running backend/Scientist child.

## F. Known limitations / not verified

- Clean Windows VM EXE install workflow is **NOT VERIFIED**.
- The NSIS installer was verified locally in an isolated directory, but native Tauri GUI E2E remains **NOT VERIFIED**.
- SQLite concurrency/busy-timeout, full chart downsample limit, persistent SQLite runtime, app-exit cleanup and soak tests remain open.
- Consequently, this report does **not** claim “Desktop ready”.