# ECOMIC · Selective-Label Scientist — Final Engineering Report

## Current verdict

`competition_ready: false`

The repository has one formal, SQLite-backed research path from typed Pi tools/RPC to `ResearchRuntime`, dynamic selective-label experiments, guarded final evaluation, Claim Guard, and report export. Pi now builds and loads ECOMIC extensions both locally and in no-key GitHub CI. Competition readiness remains false because no configured provider has produced a live, redacted Scientist tool-use transcript and the real historical non-credit dataset still lacks a separately confirmed outcome time and a complete oracle label set.

## Acceptance matrix

| Requirement | Status | Concrete evidence |
| --- | --- | --- |
| One formal runtime; no official path through `ResearchSession` | PASS | `agent_backend.rpc` imports `agent_backend.runtime.ResearchRuntime`; old session entry points are under `agent_backend/legacy/`. |
| Final metrics injection removed | PASS | Typed final tool accepts only `session_id`, `run_id`; RPC rejects a `metrics` key; regression test passes. |
| Oracle isolation | PASS | Research-facing dynamic observations exclude hidden/oracle labels; only the internal evaluator calls `finalize()`. |
| Strict DomainSpec | PASS | Initial spec has unconfirmed decision/action fields; decision mapping and observation action are separate confirmations and versions. |
| Semantic auditor | PASS | Per-decision availability counts/rates, maximum difference, descriptive odds-ratio CI, and parsed time-order validation are returned. |
| Chinese TUI workflows | PASS (static + RPC tested) | `/ecomic-new-research`, `/ecomic-run`, `/ecomic-final`, `/ecomic-history`, `/ecomic-report`, `/ecomic-settings`. |
| API-key isolation | PASS | Keys use process memory or `~/.ecomic/credentials.env`; config excludes keys; redaction tests pass; `credentials.env` is ignored. |
| Pi Agent Core / runtime loading | PASS locally and in no-key CI; live provider evidence absent | Official Pi model hydration, `build:offline`, Pi CLI startup, and all three ECOMIC extensions passed locally and in GitHub Actions run `31434225882`. No provider key, paid request, or live LLM transcript is claimed. |
| Providers | CONFIGURATION UI IMPLEMENTED | OpenAI, Anthropic, DeepSeek, Gemini, OpenRouter, Moonshot, Qwen and MiniMax identifiers are mapped to Pi provider IDs. No paid provider was invoked in this audit. |
| Custom OpenAI-compatible provider | NOT VERIFIED | UI validates Base URL but deliberately refuses formal Scientist startup until a Pi provider extension is registered and validated. |
| Session / environment restore | PASS for deterministic recipe replay | SQLite snapshots plus run recipe recreate a deterministic next-round state; integration test covers restore call. |
| Database source of truth | PASS | Session, DomainSpec versions, confirmations, plans, runs, final evaluation, events and claims are SQLite-backed. |
| Claim lineage | PASS | `claim_evidence` FK links claims to runs with same-session enforcement; migration regression test passes. |
| Dynamic environment and actual policies | PASS | `run_experiment` instantiates `DynamicSelectiveLabelEnvironment`; Random, CountOnly-MinCost and LRBE-Uncertainty run through the policy registry. |
| Reproducible feature fallback | PASS | No Python built-in `hash()` is used for nonnumeric values; SHA-256 supplies stable conversion. |
| Non-credit evidence | PASS for WDBC replay plus real historical audit; not a completed oracle benchmark | WDBC retains its explicit 5-seed × 3-budget × 3-policy simulation label. San Diego vehicle stops supply a real, non-credit historical-selection audit with source hash `2203feed…c30c`; no missing contraband outcome is imputed. |
| Report artifacts | PASS | `agent_runs/<session>/final_report.md`, `manifest.json`, `exported_actions.jsonl`, `plots/`, `artifacts/`. |
| CI | PASS including manual Pi integration | `validation` run `31434188402` passed the six Python OS/version jobs and Node checks; manual run `31434225882` also passed Pi hydration, build, CLI, and ECOMIC extension loading. |

## Verified local commands

```powershell
python -m unittest discover -s tests_agent -p "test_*.py" -v
node --test tests_node/*.test.mjs
python scripts/run_noncredit_benchmark.py
python scripts/run_sandiego_historical_audit.py
cd vendor/pi
npm run build:offline
```

At this checkpoint the Python suite completed 18 tests with one expected skip for the absent, read-only LexiRiskLabel vendor reference; the Node suite completed 3 tests. Pi's generated model-data validator passed as part of `build:offline`, and the ECOMIC extension-load help path exited successfully.

## Pi live-agent boundary

Pi's official public catalog hydration was initially blocked by a direct `models.dev` timeout. The user's temporary VPN proxy reached the catalog, so an in-process proxy dispatcher was used only for the official Pi model-data generator; hydration and the offline build then completed. The same public hydration/build and extension-load path was then verified on GitHub Actions without a proxy or a provider key. This proves runtime availability, not provider authentication or tool-use behavior. A live agent claim still requires a user-configured tool-capable provider and a redacted transcript in which Pi selects ECOMIC typed tools.

## Real historical non-credit evidence

`benchmarks/results/san_diego_historical_selection_audit.json` and its metadata companion are generated from the City of San Diego October 2017–June 2018 vehicle-stops release. The CSV has 34,333 rows and a recorded SHA-256. Search status is a real historical decision, and label availability differs strongly by that decision. However, the file has no separate contraband observation time; 586 `searched=N` records also carry an administrative contraband value. ECOMIC retains these anomalies, requires semantic reconciliation, and blocks dynamic oracle evaluation rather than silently treating absent or inconsistent outcomes as ground truth.

## Required next evidence before readiness can change

1. Configure a user-owned tool-capable provider, run the real Pi Scientist Agent, and retain a redacted tool-use transcript without disclosing its key.
2. Obtain or document a non-credit historical release with confirmed decision/outcome time ordering and reconcile the San Diego administrative outcome anomalies before attempting oracle-backed evaluation.
3. Implement and verify a registered Pi custom OpenAI-compatible provider if that option is required for the competition deployment.
