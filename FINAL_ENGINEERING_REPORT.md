# ECOMIC · Selective-Label Scientist — Final Engineering Report

## Current verdict

`competition_ready: false`

ECOMIC now has one SQLite-backed formal research path: typed Pi tools and the real Pi Agent Core call RPC, RPC calls only `ResearchRuntime`, and the runtime owns semantic confirmation, dynamic experiments, evaluator-only final assessment, claim lineage and export. The remaining false gate is intentional: no user-owned paid provider has supplied a redacted real tool-use transcript, and the real historical non-credit release is not a valid oracle benchmark.

## Evidence matrix

| Requirement | Current evidence |
| --- | --- |
| Unified runtime | PASS — `agent_backend.rpc` imports `agent_backend.runtime.ResearchRuntime`; old backend paths remain outside the public runtime surface. |
| Final-evaluation safety | PASS — final tool schema has only `session_id`/`run_id`; RPC rejects injected `metrics`; evaluator database guard requires a locked plan and allows one final evaluation. |
| Oracle isolation | PASS — research tools receive no oracle labels/final metrics; evaluator alone calls the final environment method. |
| DomainSpec and semantic audit | PASS — decision/action confirmations are distinct and versioned; audit reports availability rates and parsed time ordering. |
| Follow-up Agent loop | PASS in no-key structural/integration validation — Agent Core starts with `observe_state` and `audit_environment`, can persist a parent-linked revised hypothesis and compare researcher-visible evidence before follow-up. |
| Chinese TUI | PASS for the implemented workflow — Chinese home, data/semantic/time/action confirmation, experiment, final evaluation, report and history recovery; all mutations use RPC. |
| API configuration | PASS for secure configuration/runtime implementation — session-memory or private `~/.ecomic/credentials.env`, no key in SQLite/report/JSONL, custom OpenAI-compatible Pi provider registration and bounded Tool Calling probe. No paid provider invocation is claimed. |
| Session recovery | PASS — SQLite metadata plus deterministic replay recipe/environment snapshot restores subsequent state. |
| Claim lineage | PASS — database `claim_evidence` FK enforces same-session run lineage. |
| Real policies | PASS — Random, CountOnly-MinCost and LRBE-Uncertainty execute in `DynamicSelectiveLabelEnvironment`. |
| Non-credit evidence | PASS with limitations — WDBC is explicitly simulation; San Diego is a real 34,333-row historical selection audit, not an oracle benchmark. |
| CI / Pi integration | PASS — GitHub Actions `31438184612` passed Ubuntu/Windows Python 3.10/3.12/3.13, Node checks, official Pi hydration, offline build, CLI and loading all five ECOMIC extensions. |

## Remaining external gates

1. Enter a user-owned tool-capable API key in `/ecomic-settings`, approve `/ecomic-test-connection`, and retain a redacted real Scientist Agent tool-use transcript.
2. Obtain a non-credit historical dataset with confirmed decision/outcome time ordering and a defensible oracle label set; do not impute San Diego's missing contraband outcomes.

## Reproduction

```powershell
python -m unittest discover -s tests_agent -p "test_*.py" -v
node --test tests_node/*.test.mjs
npm run ecomic
```

Use `/ecomic-settings`, `/ecomic-test-connection`, `/ecomic-new-research`, then `/ecomic-scientist`. The paid connection/tool probe is explicitly user-approved.
