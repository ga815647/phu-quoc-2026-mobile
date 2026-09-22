-- 003_content_revisions.sql — minimal incremental audit + optimistic concurrency
-- Target: test branch first (br-wispy-paper-b3b7t06k), prod only after user approval.
-- Does NOT delete/rebuild tables; additive only.
-- Rationale: spec requires before/after, time, actor/source (truthful if unknown),
-- transactional data+audit, restore-as-new-record, conflict handling (no silent
-- last-write-wins), and no audit leak via public API.

CREATE TABLE IF NOT EXISTS content_revisions (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  target_table TEXT NOT NULL,
  target_id TEXT NOT NULL,
  field_name TEXT NOT NULL,
  old_value TEXT,
  new_value TEXT,
  changed_at TEXT DEFAULT (now()::text),
  actor TEXT,
  source TEXT,
  reason TEXT,
  base_version INTEGER,
  resulting_version INTEGER
);
CREATE INDEX IF NOT EXISTS idx_content_revisions_target
  ON content_revisions (target_table, target_id, id);

-- Optimistic-concurrency version columns (additive, default 1 preserves existing rows).
ALTER TABLE food_places ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE dishes ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE dish_carriers ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE points ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE transport_options ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

-- evidence_log stays append-only (mid-trip rule); no version column by design.
-- Public read API (phqreadonly) intentionally has NO endpoint for content_revisions.
-- Do NOT GRANT SELECT ON content_revisions TO phq_web_ro.
