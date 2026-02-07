PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS lm_review_tasks (
  id TEXT PRIMARY KEY,
  draft_id TEXT NOT NULL UNIQUE,
  assignee_id TEXT,
  checklist_json TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_review', 'approved', 'changes_requested', 'rejected')),
  decided_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (draft_id) REFERENCES lm_outreach_drafts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lm_review_tasks_status
  ON lm_review_tasks(status);
