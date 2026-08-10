# Running ECOMIC

Start the interactive Pi workbench from the repository root:

```powershell
npm run ecomic
```

The workbench opens with the persisted-session home screen. Use these commands in order for a live model-backed research loop:

1. `/ecomic-settings` — choose the provider and model, then enter the API key. A saved key is kept only in `~/.ecomic/credentials.env`; the repository, SQLite research state, reports, and logs never receive the plaintext key.
2. `/ecomic-test-connection` — explicitly approve one small paid network probe. It verifies both provider connectivity and tool calling before enabling the formal Agent Core path.
3. `/ecomic-new-research` — import CSV/Parquet and confirm the historical decision, observed/hidden outcomes, and reversible/simulatable observation action.
4. `/ecomic-scientist` — run the gated Pi Agent Core scientist. It may use only typed ECOMIC tools; the Oracle and evaluator-owned final metrics stay inaccessible.

`/ecomic-history` restores a session as the active workbench session, so it can immediately continue with `/ecomic-run`, `/ecomic-final`, `/ecomic-report`, or `/ecomic-scientist`.

For deterministic, no-LLM import validation:

```powershell
npm run ecomic -- --headless --data examples\fraud_like.csv --description "historical review determines label visibility"
```

The first Pi installation needs its dependencies and generated model data:

```powershell
cd vendor\pi
npm install --ignore-scripts
npm run build:offline
cd ..\..
```

When your local network requires the VPN proxy supplied for this project, Pi model-data hydration can use an HTTP proxy at `http://127.0.0.1:7897`. The interactive runtime uses the provider connection configured in Pi; it does not send any request until you explicitly approve `/ecomic-test-connection` or start the Scientist Agent.
