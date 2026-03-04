PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS lm_audit_logs (
  id TEXT PRIMARY KEY,
  intake_id TEXT,
  actor_id TEXT,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  action TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (intake_id) REFERENCES lm_intakes(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_lm_audit_logs_intake_id
  ON lm_audit_logs(intake_id);

CREATE INDEX IF NOT EXISTS idx_lm_audit_logs_entity
  ON lm_audit_logs(entity_type, entity_id);
