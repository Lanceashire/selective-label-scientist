CREATE INDEX IF NOT EXISTS idx_sessions_dataset ON sessions(dataset_id);
CREATE INDEX IF NOT EXISTS idx_domain_specs_session_version ON domain_specs(session_id, version);
CREATE INDEX IF NOT EXISTS idx_hypotheses_session_version ON hypotheses(session_id, version);
CREATE INDEX IF NOT EXISTS idx_runs_session ON experiment_runs(session_id);
CREATE INDEX IF NOT EXISTS idx_runs_policy ON experiment_runs(policy);
CREATE INDEX IF NOT EXISTS idx_events_session_timestamp ON agent_events(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_claims_session ON claims(session_id);
CREATE INDEX IF NOT EXISTS idx_claim_evidence_claim ON claim_evidence(claim_id);
