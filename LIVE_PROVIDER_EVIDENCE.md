# ECOMIC Live Provider Evidence Checklist

This checklist is the final manual integration gate. It deliberately does not
contain an API key, a provider-specific secret, or a claim that a paid request
has already occurred.

## Preconditions

- Start from the repository root with `npm run ecomic`.
- Use a provider/model that supports Tool Calling.
- Prepare a small non-sensitive CSV/Parquet file. `examples/fraud_like.csv` is
  suitable for a smoke test but is not cross-domain benchmark evidence.

## TUI procedure

1. Run `/ecomic-settings`; select Provider, enter Model ID and API Key. Choose
   memory-only storage unless you explicitly want the local private credential
   file at `~/.ecomic/credentials.env`.
2. Run `/ecomic-test-connection`; approve its clearly disclosed minimal paid
   request. Record only the resulting provider/model, timestamp, and whether
   Tool Calling was verified — never the key or raw authorization header.
3. Run `/ecomic-new-research`; import the data and explicitly confirm decision,
   observed/hidden values, label, cost, time ordering, and reversible/simulatable
   observation action.
4. Run `/ecomic-scientist`; enter a bounded question such as: “Compare
   LRBE-Uncertainty and CountOnly-MinCost under a low budget. If visible evidence
   is insufficient, create a follow-up hypothesis rather than overclaiming.”
5. Let the Agent call `observe_state`, `audit_environment`, experiment tools and
   `compare_visible_evidence`. It may create a parent-linked follow-up hypothesis.
   Do not instruct it to reveal labels or invent final metrics.
6. Export `/ecomic-report` after completion. If the Agent decides the plan is
   ready, it may lock the run plan and request one evaluator-owned finalization.

## Evidence to retain

- Redacted terminal/TUI transcript proving a real provider connection and at
  least one ECOMIC typed tool call selected by the model.
- The resulting `agent_runs/<session_id>/final_report.md`, `manifest.json`, and
  `exported_actions.jsonl` after checking that none contains the API key.
- Provider name, model ID, UTC timestamp, session ID, and a statement that the
  request was user-authorized.

## Redaction checks

Before sharing any transcript or artifact, search for `Authorization`, `Bearer`,
`API_KEY`, `token`, and the first/last four characters of the key. Remove the
entire value if any appears. A live transcript proves tool use; it must never
become a credential leak.
