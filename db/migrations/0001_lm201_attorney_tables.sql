PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS lm_attorneys (
  id TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  full_name TEXT NOT NULL,
  bar_number TEXT,
  city TEXT,
  status TEXT NOT NULL CHECK (status IN ('active', 'inactive', 'suspended')),
  admission_year INTEGER CHECK (admission_year IS NULL OR admission_year >= 1900),
  years_in_practice INTEGER CHECK (years_in_practice IS NULL OR years_in_practice >= 0),
  practice_areas_json TEXT NOT NULL,
  firm_name TEXT,
  firm_url TEXT,
  office_address TEXT,
  counties_served_json TEXT,
  languages_json TEXT,
  free_consultation INTEGER,
  contingency_fee_noted INTEGER,
  peer_recognitions_json TEXT,
  source_profile_url TEXT,
  trauma_accessibility_json TEXT,
  intake_friction_json TEXT,
  risk_flags_json TEXT,
  last_verified_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (state, bar_number)
);

CREATE TABLE IF NOT EXISTS lm_attorney_sources (
  id TEXT PRIMARY KEY,
  attorney_id TEXT NOT NULL,
  source_type TEXT NOT NULL CHECK (
    source_type IN (
      'iowa_opr',
      'iowa_bar_find_a_lawyer',
      'iowa_courts_online',
      'discipline_decision',
      'firm_site',
      'directory'
    )
  ),
  source_url TEXT NOT NULL,
  captured_at TEXT NOT NULL,
  excerpt TEXT,
  confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  evidence_json TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (attorney_id) REFERENCES lm_attorneys(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lm_attorney_sources_attorney_id
  ON lm_attorney_sources(attorney_id);

CREATE TABLE IF NOT EXISTS lm_attorney_discipline (
  id TEXT PRIMARY KEY,
  attorney_id TEXT NOT NULL,
  has_public_action INTEGER NOT NULL CHECK (has_public_action IN (0, 1)),
  sanction_type TEXT CHECK (
    sanction_type IS NULL OR sanction_type IN (
      'none',
      'public_reprimand',
      'administrative_suspension',
      'disciplinary_suspension',
      'revocation',
      'other'
    )
  ),
  decision_date TEXT,
  citation TEXT,
  summary TEXT,
  source_url TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (attorney_id) REFERENCES lm_attorneys(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lm_attorney_discipline_attorney_id
  ON lm_attorney_discipline(attorney_id);
