# ECOMIC Selective-Label Scientist — Final Gate Report

## Result

`competition_ready: false`

The core research path is implemented and locally tested. Pi itself now hydrates, builds, and loads the ECOMIC extensions locally. Readiness remains false until a real provider-driven Pi Scientist transcript is recorded and a non-credit historical dataset can pass its semantic/time and oracle-evaluation gates without inventing missing labels.

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
| WDBC non-credit benchmark | PASS — simulation only | 5 × 3 × 3 matrix, trajectories and CIs; explicitly `REPLAY_MODE_SIMULATION` |
| San Diego historical non-credit audit | PASS WITH LIMITATIONS | 34,333 public vehicle-stop rows; source hash recorded; genuine search decision and strong decision-dependent label availability; time and administrative-value anomalies are retained as gates |
| Chinese workbench / API-key safety | PASS (local static/RPC validation) | Pi extensions plus Node secret tests |
| Pi runtime / extension load | PASS locally | official model catalog hydrated, `build:offline` passed, and actual Pi CLI loaded all ECOMIC extensions |
| Pi Live Agent | BLOCKED | no user-owned provider key or redacted live Pi tool-use transcript was supplied; no paid provider call is claimed |
| Custom provider | BLOCKED | intentionally not promoted without Pi extension validation |
| GitHub Actions remote regular result | PASS | `validation` run `31432429985`: Ubuntu/Windows × Python 3.10/3.12/3.13 plus Node all passed; Pi remains a manual external integration gate |

## Non-negotiable limitations

- A fully labelled or synthetic replay dataset does not prove a selective-label mechanism or a cross-domain causal claim.
- The WDBC benchmark must be called `REPLAY_MODE_SIMULATION`.
- The San Diego audit must not impute missing contraband labels or treat its incomplete outcomes as an evaluation oracle.
- Oracle metrics remain unavailable during research and cannot be supplied by any agent tool.
- A proxy observation cost must not be represented as real-world harm/cost.

See `FINAL_ENGINEERING_REPORT.md` for the implementation and evidence ledger.
