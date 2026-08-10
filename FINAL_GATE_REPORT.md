# ECOMIC Selective-Label Scientist — Final Gate Report

## Result

`competition_ready: false`

The repository is a tested, auditable Beta implementation rather than a claim of completed competition validation.

| Gate | Status | Evidence |
| --- | --- | --- |
| Strict data partition / no historical backlog | PASS | 100 seeded invariant tests |
| SQLite state, migration and recovery | PASS | `DatabaseManager` and mock end-to-end test |
| DuckDB streaming ingestion | PASS | bounded sample/batch interface and streamed SHA-256 |
| Dynamic multi-round environment | PASS | dynamic regression test |
| LRBE two-stage optimizer | PASS | 50 brute-force equivalence cases |
| Mock scientist closed loop | PASS | two hypotheses, plan/run/lock/finalize persisted |
| Pi live provider loop | BLOCKED | extension is implemented but provider not exercised |
| Real cross-domain empirical benchmark | BLOCKED | no semantically confirmed non-credit historical dataset run |
| Clean GitHub CI run | PENDING | workflow committed; remote run must be observed |

## Non-negotiable limitations

- A fully labeled dataset does **not** establish selective-label causality. The semantic auditor reports `NOT_SELECTIVE_LABEL` unless label availability/selection semantics are supplied or explicitly simulated.
- Simulation supports protocol validation only; it cannot support a cross-domain effectiveness claim.
- Final oracle metrics are intentionally unavailable during research and cannot be injected by an agent action.

## Next evidence needed

1. Register a public non-credit dataset with human-confirmed decision values, label availability relationship, costs, and time ordering.
2. Run the 5-seed × 3-budget benchmark matrix and retain its raw run database/artifacts.
3. Configure a live models.dev-compatible provider and record a real Pi transcript using the independent tools.
