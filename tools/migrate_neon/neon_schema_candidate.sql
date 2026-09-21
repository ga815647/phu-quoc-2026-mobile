-- Phu Quoc 2026 — Neon (Postgres) schema candidate v1
-- Translated 1:1 from app/data/schema.sql (SQLite). No new business columns.
-- Mapping notes:
--   TEXT -> TEXT, REAL -> DOUBLE PRECISION, AUTOINCREMENT -> GENERATED ALWAYS AS IDENTITY
--   datetime('now') defaults -> now()::text (keeps TEXT timestamp convention of SQLite source)
--   JSON-array TEXT columns stay TEXT (no silent jsonb migration before user confirmation)
--   FK dash-format mismatch (dish_carriers ids without dashes): verified 2026-09-21 that
--     all 7x2 FK values normalize (strip '-') to exactly one master row each, no collisions;
--     loader normalizes dish_id/place_id on the isolated test branch only. Source SQLite untouched.
--   (SQLite PRAGMA journal_mode=WAL has no Postgres equivalent; intentionally omitted.)

CREATE TABLE IF NOT EXISTS dishes (
  notion_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT,
  flavor_note TEXT,
  price_hint TEXT,
  kid_fit DOUBLE PRECISION,
  pq_feature DOUBLE PRECISION,
  time_slots TEXT,
  order_note TEXT,
  evidence_as_of TEXT,
  updated_at TEXT DEFAULT (now()::text)
);

CREATE TABLE IF NOT EXISTS food_places (
  notion_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  region TEXT,
  housing TEXT,
  cluster TEXT,
  time_slots TEXT,
  hours_text TEXT,
  maps_query TEXT,
  price_text TEXT,
  cuisine TEXT,
  worth DOUBLE PRECISION,
  convenience DOUBLE PRECISION,
  local_idx DOUBLE PRECISION,
  pq_feature DOUBLE PRECISION,
  kid_fit DOUBLE PRECISION,
  grade TEXT,
  op_status TEXT,
  op_conf TEXT,
  atlas_state TEXT,
  migration TEXT,
  data_conf TEXT,
  research_date TEXT,
  last_verified TEXT,
  evidence TEXT,
  neg_warn TEXT,
  summary TEXT,
  kid_plan TEXT,
  dish_ids TEXT,
  v2_run TEXT,
  v2_proto TEXT,
  evidence_as_of TEXT,
  updated_at TEXT DEFAULT (now()::text)
);

CREATE TABLE IF NOT EXISTS dish_carriers (
  notion_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  dish_id TEXT REFERENCES dishes(notion_id),
  place_id TEXT REFERENCES food_places(notion_id),
  role TEXT,
  status TEXT,
  scope TEXT,
  food_verdict TEXT,
  food_conf TEXT,
  avail_verdict TEXT,
  risk_exec TEXT,
  txn_risk TEXT,
  rationale TEXT,
  decision_set TEXT,
  worker_run TEXT,
  evidence_as_of TEXT,
  accepted_at TEXT,
  updated_at TEXT DEFAULT (now()::text)
);

CREATE TABLE IF NOT EXISTS points (
  slug TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  area TEXT NOT NULL,
  interest DOUBLE PRECISION,
  mandatory TEXT,
  trip_priority TEXT,
  condition_gate TEXT,
  convenience TEXT,
  returnability TEXT,
  play_mode TEXT,
  condition_note TEXT,
  kid_note TEXT,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  durable_note TEXT,
  source_notion_id TEXT,
  evidence_as_of TEXT DEFAULT '2026-08-29',
  updated_at TEXT DEFAULT (now()::text)
);

CREATE TABLE IF NOT EXISTS cards (
  slug TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  route TEXT,
  gates TEXT,
  transport TEXT,
  notes TEXT,
  summary TEXT,
  key_times TEXT,
  badges TEXT,
  stops TEXT,
  transport_out TEXT,
  transport_back TEXT,
  kid_note TEXT,
  dining TEXT,
  cut_order TEXT,
  callout TEXT,
  evidence_as_of TEXT DEFAULT '2026-09-20',
  updated_at TEXT DEFAULT (now()::text)
);

CREATE TABLE IF NOT EXISTS bookings (
  slug TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT,
  amount TEXT,
  status TEXT NOT NULL DEFAULT 'Confirmed',
  evidence TEXT,
  evidence_as_of TEXT DEFAULT '2026-09-20',
  updated_at TEXT DEFAULT (now()::text)
);

CREATE TABLE IF NOT EXISTS transport_options (
  slug TEXT PRIMARY KEY,
  direction TEXT,
  plan TEXT NOT NULL,
  station TEXT,
  status TEXT,
  priority TEXT,
  note TEXT,
  source_notion_id TEXT,
  evidence_as_of TEXT DEFAULT '2026-08-25',
  updated_at TEXT DEFAULT (now()::text)
);

CREATE TABLE IF NOT EXISTS evidence_log (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ref_type TEXT NOT NULL,
  ref_id TEXT NOT NULL,
  note TEXT NOT NULL,
  created_at TEXT DEFAULT (now()::text)
);

CREATE OR REPLACE VIEW v_executable_foods AS
SELECT p.name AS place, p.region, p.time_slots, p.grade, p.maps_query,
       p.last_verified, p.op_status, p.atlas_state,
       c.title AS carrier, c.role, c.status AS carrier_status, c.evidence_as_of
FROM food_places p LEFT JOIN dish_carriers c
  ON replace(c.place_id,'-','') = replace(p.notion_id,'-','')
WHERE p.op_status = '營業中' AND p.atlas_state = 'ACTIVE' AND c.status = 'ACCEPTED';

CREATE OR REPLACE VIEW v_points_query AS
SELECT name, area, interest, mandatory, status, condition_gate, returnability, kid_note
FROM points WHERE status IN ('ACTIVE','OPTIONAL') ORDER BY interest DESC, name;

CREATE OR REPLACE VIEW v_cards_gates AS
SELECT slug, name, status, route, gates, transport, summary FROM cards ORDER BY slug;

CREATE OR REPLACE VIEW v_order_gaps AS
SELECT kind, title, detail, amount, status FROM bookings ORDER BY kind, title;
