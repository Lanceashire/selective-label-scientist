-- Bootstrap schema is retained in database.py for backward compatibility.
-- New installations record this migration before subsequent migrations.
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
