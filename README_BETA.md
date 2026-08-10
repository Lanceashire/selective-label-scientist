# Beta upgrade notes

Run `powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1` after cloning. The main interfaces are:

- `agent_backend.environment.protocol`: strict partition contract.
- `agent_backend.environment.dynamic`: label-isolated multi-round environment and internal oracle evaluator.
- `agent_backend.persistence.database`: SQLite source of truth and recovery.
- `agent_backend.agent.scientist`: deterministic mock tool-loop integration test.

The system intentionally rejects unconfirmed decision mappings and treats fully observed labels as `NOT_SELECTIVE_LABEL`; it will not infer a selective-label mechanism from column names.
