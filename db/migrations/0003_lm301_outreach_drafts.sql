PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS lm_outreach_drafts (
  id TEXT PRIMARY KEY,
  intake_id TEXT NOT NULL,
  attorney_id TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('email', 'form')),
  subject TEXT,
  body TEXT,
  payload_json TEXT,
  status TEXT NOT NULL DEFAULT 'pending_review' CHECK (status IN ('pending_review', 'approved', 'submitted', 'failed')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (intake_id, attorney_id, channel),
  FOREIGN KEY (intake_id) REFERENCES lm_intakes(id) ON DELETE CASCADE,
  FOREIGN KEY (attorney_id) REFERENCES lm_attorneys(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lm_outreach_drafts_intake_id
  ON lm_outreach_drafts(intake_id);
