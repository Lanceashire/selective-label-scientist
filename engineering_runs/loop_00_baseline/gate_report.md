# Loop 0 baseline

Status: PASS WITH KNOWN LIMITATIONS

- Existing suite: 7 passed, 1 expected skip (frozen LexiRiskLabel reference was intentionally not cloned into the publish tree).
- Confirmed Alpha placeholders: full-file CSV loading, candidate/visible overlap, heuristic rather than two-stage LRBE, externally supplied final metrics, single Pi dispatcher, no SQLite source of truth.
- These findings were converted into blocking regression tests before implementation.
