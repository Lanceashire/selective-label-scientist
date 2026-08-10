# ECOMIC · Selective-Label Scientist — Final Engineering Report

## Current verdict

`competition_ready: false`

This repository has one formal, SQLite-backed research path from typed Pi tools/RPC to `ResearchRuntime`, dynamic selective-label experiments, guarded final evaluation, Claim Guard, and report export. It is not competition-ready because a live Pi build/provider transcript and a real historical non-credit selection-mechanism dataset have not been verified.

## Acceptance matrix

| Requirement | Status | Concrete evidence |
| --- | --- | --- |
| One formal runtime; no official path through `ResearchSession` | PASS | `agent_backend.rpc` imports `agent_backend.runtime.ResearchRuntime`; old session entry points are under `agent_backend/legacy/`. |
| Final metrics injection removed | PASS | Typed final tool accepts only `session_id`, `run_id`; RPC rejects a `metrics` key; regression test passes. |
| Oracle isolation | PASS | Research-facing dynamic observations exclude hidden/oracle labels; only internal evaluator calls `finalize()`. |
| Strict DomainSpec | PASS | Initial spec has unconfirmed decision/action fields; decision mapping and observation action are separate confirmations and versions. |
| Semantic auditor | PASS | Per-decision availability counts/rates, maximum difference, descriptive odds-ratio CI, and parsed time-order validation are returned. |
| Chinese TUI workflows | PASS (static + RPC tested) | `/ecomic-new-research`, `/ecomic-run`, `/ecomic-final`, `/ecomic-history`, `/ecomic-report`, `/ecomic-settings`. |
| API-key isolation | PASS | Keys use process memory or `~/.ecomic/credentials.env`; config excludes keys; redaction tests pass; `credentials.env` is ignored. |
| Pi Agent Core implementation | IMPLEMENTED, LIVE GATE BLOCKED | `agent/src/scientist-agent.ts` uses Pi `Agent`, `streamSimple`, sequential typed tools and pre-tool Oracle/metric guard. |
| Providers | CONFIGURATION UI IMPLEMENTED | OpenAI, Anthropic, DeepSeek, Gemini, OpenRouter, Moonshot, Qwen and MiniMax identifiers are mapped to Pi provider IDs. No paid provider was invoked in this audit. |
| Custom OpenAI-compatible provider | NOT VERIFIED | UI validates Base URL but deliberately refuses formal Scientist startup until a Pi provider extension is registered and validated. |
| Session / environment restore | PASS for deterministic recipe replay | SQLite snapshots plus run recipe recreate a deterministic next-round state; integration test covers restore call. |
| Database source of truth | PASS | Session, DomainSpec versions, confirmations, plans, runs, final evaluation, events and claims are SQLite-backed. |
| Claim lineage | PASS | `claim_evidence` FK links claims to runs with same-session enforcement; migration regression test passes. |
| Dynamic environment and actual policies | PASS | `run_experiment` instantiates `DynamicSelectiveLabelEnvironment`; Random, CountOnly-MinCost and LRBE-Uncertainty run through the policy registry. |
| Reproducible feature fallback | PASS | No Python built-in `hash()` is used for nonnumeric values; SHA-256 supplies stable conversion. |
| Non-credit benchmark | PASS as REPLAY simulation only | WDBC 5 seeds × 3 budgets × 3 policies; matrix, trajectories, effect sizes and normal 95% CIs are retained. |
| Report artifacts | PASS | `agent_runs/<session>/final_report.md`, `manifest.json`, `exported_actions.jsonl`, `plots/`, `artifacts/`. |
| CI definition | PASS (regular matrix) | GitHub Actions `validation` run `31432429985` passed all six Python OS/version jobs and the Node schema/security job. The Pi build remains an explicit manual external gate. |

## Verified local commands

```powershell
python -m unittest discover -s tests_agent -p "test_*.py" -v
node --test tests_node/*.test.mjs
python scripts/run_noncredit_benchmark.py
```

At this checkpoint the Python suite completed 17 tests with one expected skip for the absent, read-only LexiRiskLabel vendor reference; the Node suite completed 3 tests.

## Pi live-runtime gate

The Pi repository was cloned and dependencies installed locally. Its offline build cannot currently complete because the shallow clone lacks generated model catalog data and the hydration request to `models.dev` timed out. Consequently no provider API key was used, no paid API request was made, no live Pi agent transcript is claimed, and the workflow keeps Pi build/load as an explicit manual integration gate.

When network access to Pi model hydration is available, run its manual workflow with `run_pi=true` or locally run `npm run hydrate:model-data; npm run build:offline` in `vendor/pi`, then start ECOMIC with the documented Pi extension command.

## Benchmark interpretation

The benchmark is deliberately tagged `REPLAY_MODE_SIMULATION`. WDBC is a real public non-credit dataset, but its decision field, cost and timing are synthetic for protocol testing. It does not support a clinical or cross-domain causal claim. The effect-size output can be negative; ECOMIC preserves that result rather than forcing a policy-win narrative.

## Required next evidence before readiness can change

1. Complete the Pi model-data hydration/build and record a live, redacted provider transcript with a tool-capable model.
2. Register a real non-credit dataset with human-confirmed historical decision, actual label-visibility mechanism, observation semantics, costs and time ordering.
3. Implement and verify a registered Pi custom OpenAI-compatible provider if that option is required for the competition deployment.
