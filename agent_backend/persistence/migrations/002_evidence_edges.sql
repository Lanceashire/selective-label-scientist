CREATE TABLE IF NOT EXISTS claim_evidence (
  claim_id TEXT NOT NULL REFERENCES claims(claim_id),
  run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
  metric_name TEXT NOT NULL,
  metric_value REAL,
  effect_size REAL,
  ci_low REAL,
  ci_high REAL,
  PRIMARY KEY (claim_id, run_id, metric_name)
);
