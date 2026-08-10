# ECOMIC Selective-Label Scientist — Final Gate Report

## Result

`competition_ready: false`

The core research path is implemented and locally tested. Readiness remains
false until the live Pi runtime/provider gate, a real historical non-credit
dataset gate, and a remote CI observation are completed.

| Gate | Status | Evidence |
| --- | --- | --- |
| Unified RPC → ResearchRuntime path | PASS | `agent_backend.rpc` and runtime integration tests |
| Final evaluation cannot accept injected metrics | PASS | RPC schema regression test |
| Oracle boundary / one final evaluation | PASS | dynamic protocol tests and evaluator guard |
| Confirmed, versioned DomainSpec | PASS | separate decision/action confirmation test |
| SQLite migrations, lineage and report export | PASS | migration, claim and report integration tests |
| Deterministic replay restoration | PASS | persisted recipe/snapshot restore test |
| Semantic availability and time audit | PASS | typed audit output with per-value statistics |
| Real policies in dynamic environment | PASS | Random, CountOnly-MinCost, LRBE-Uncertainty |
| Non-credit benchmark | PASS — simulation only | WDBC matrix + trajectories + CIs, explicitly replay mode |
| Chinese workbench / API-key safety | PASS (local static/RPC validation) | Pi extensions plus Node secret tests |
| Pi Live Agent | BLOCKED | Pi model catalog hydration timed out; no live provider claimed |
| Custom provider | BLOCKED | intentionally not promoted without Pi extension validation |
| GitHub Actions remote result | PENDING | workflow authored, remote run not observed |

## Non-negotiable limitations

- A fully labelled or synthetic replay dataset does not prove a selective-label
  mechanism or a cross-domain performance claim.
- The benchmark must be called `REPLAY_MODE_SIMULATION`.
- Oracle metrics remain unavailable during research and cannot be supplied by
  any agent tool.
- A proxy observation cost must not be represented as real-world harm/cost.

See `FINAL_ENGINEERING_REPORT.md` for the implementation and evidence ledger.
