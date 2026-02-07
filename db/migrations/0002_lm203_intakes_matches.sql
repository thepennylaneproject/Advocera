PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS lm_intakes (
  id TEXT PRIMARY KEY,
  state TEXT NOT NULL CHECK (state IN ('IA')),
  practice_areas_json TEXT NOT NULL,
  zip_code TEXT NOT NULL,
  city TEXT,
  language_pref TEXT,
  urgency TEXT NOT NULL CHECK (urgency IN ('low', 'medium', 'high')),
  budget_max_usd INTEGER,
  summary TEXT NOT NULL,
  contact_json TEXT,
  consent_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new' CHECK (
    status IN ('new', 'matched', 'draft_pending_review', 'in_review', 'ready_for_submit', 'closed')
  ),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lm_matches (
  id TEXT PRIMARY KEY,
  intake_id TEXT NOT NULL,
  attorney_id TEXT NOT NULL,
  score REAL NOT NULL,
  reasons_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (intake_id, attorney_id),
  FOREIGN KEY (intake_id) REFERENCES lm_intakes(id) ON DELETE CASCADE,
  FOREIGN KEY (attorney_id) REFERENCES lm_attorneys(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lm_matches_intake_id
  ON lm_matches(intake_id);
