-- Phu Quoc 2026 — SQLite 主庫 schema v1
-- 5 卡為準：onbird/vinwonders/cable/starfish/safari；anthoi=satellite, khem=retired
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS dishes (
  notion_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT,
  flavor_note TEXT,
  price_hint TEXT,
  kid_fit REAL,
  pq_feature REAL,
  time_slots TEXT,          -- JSON array
  order_note TEXT,
  evidence_as_of TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS food_places (
  notion_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  region TEXT,              -- 區域
  housing TEXT,             -- 住宿圈
  cluster TEXT,             -- 微型 Cluster
  time_slots TEXT,          -- JSON array
  hours_text TEXT,
  maps_query TEXT,
  price_text TEXT,
  cuisine TEXT,             -- JSON array
  worth REAL,
  convenience REAL,
  local_idx REAL,
  pq_feature REAL,
  kid_fit REAL,
  grade TEXT,               -- S/A/B/C/D 專程等級
  op_status TEXT,           -- 營運狀態
  op_conf TEXT,             -- Operational confidence
  atlas_state TEXT,         -- Current Atlas state
  migration TEXT,           -- Migration state
  data_conf TEXT,           -- 資料信心
  research_date TEXT,
  last_verified TEXT,       -- 最後確認營業日
  evidence TEXT,
  neg_warn TEXT,
  summary TEXT,
  kid_plan TEXT,
  dish_ids TEXT,            -- JSON array of dish notion_ids
  v2_run TEXT,
  v2_proto TEXT,
  evidence_as_of TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dish_carriers (
  notion_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  dish_id TEXT REFERENCES dishes(notion_id),
  place_id TEXT REFERENCES food_places(notion_id),
  role TEXT,                -- PRIMARY/BACKUP
  status TEXT,              -- Assignment Status
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
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS points (
  slug TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  area TEXT NOT NULL,        -- DD/海灘/漁村/北島/南島
  interest REAL,             -- 0-3, 條件式存文字於 condition_note
  mandatory TEXT,            -- Yes/Unknown
  trip_priority TEXT,
  condition_gate TEXT,
  convenience TEXT,
  returnability TEXT,
  play_mode TEXT,
  condition_note TEXT,       -- 條件式評分原文
  kid_note TEXT,
  status TEXT NOT NULL DEFAULT 'ACTIVE', -- ACTIVE/OPTIONAL/RETIRED
  durable_note TEXT,
  source_notion_id TEXT,
  evidence_as_of TEXT DEFAULT '2026-08-29',
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cards (
  slug TEXT PRIMARY KEY,     -- onbird/vinwonders/cable/starfish/safari
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACTIVE', -- ACTIVE/RETIRED
  route TEXT,
  gates TEXT,                -- JSON array of admission gates
  transport TEXT,
  notes TEXT,
  evidence_as_of TEXT DEFAULT '2026-09-20',
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bookings (
  slug TEXT PRIMARY KEY,
  kind TEXT NOT NULL,        -- flight/hotel/activity/transport/insurance
  title TEXT NOT NULL,
  detail TEXT,
  amount TEXT,
  status TEXT NOT NULL DEFAULT 'Confirmed',
  evidence TEXT,
  evidence_as_of TEXT DEFAULT '2026-09-20',
  updated_at TEXT DEFAULT (datetime('now'))
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
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS evidence_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ref_type TEXT NOT NULL,    -- food/point/card/booking
  ref_id TEXT NOT NULL,
  note TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);

-- views
CREATE VIEW IF NOT EXISTS v_executable_foods AS
SELECT p.name AS place, p.region, p.time_slots, p.grade, p.maps_query,
       p.last_verified, p.op_status, p.atlas_state,
       c.title AS carrier, c.role, c.status AS carrier_status, c.evidence_as_of
FROM food_places p LEFT JOIN dish_carriers c
  ON replace(c.place_id,'-','') = replace(p.notion_id,'-','')
WHERE p.op_status = '營業中' AND p.atlas_state = 'ACTIVE' AND c.status = 'ACCEPTED';

CREATE VIEW IF NOT EXISTS v_points_query AS
SELECT name, area, interest, mandatory, status, condition_gate, returnability, kid_note
FROM points WHERE status IN ('ACTIVE','OPTIONAL') ORDER BY interest DESC, name;

CREATE VIEW IF NOT EXISTS v_cards_gates AS
SELECT slug, name, status, route, gates, transport FROM cards ORDER BY slug;

CREATE VIEW IF NOT EXISTS v_order_gaps AS
SELECT kind, title, detail, amount, status FROM bookings ORDER BY kind, title;
