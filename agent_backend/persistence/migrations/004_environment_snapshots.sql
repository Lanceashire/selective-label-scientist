CREATE TABLE IF NOT EXISTS environment_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(session_id),
  run_id TEXT REFERENCES experiment_runs(run_id),
  round_index INTEGER NOT NULL,
  state_json TEXT NOT NULL,
  artifact_path TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_session_round ON environment_snapshots(session_id, round_index);
