-- LOCAL TEST ONLY. Prelude executed once against the isolated socket database
-- BEFORE 006; the rest runs inside every test's rollback transaction.
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='phq_web_ro') THEN
  CREATE ROLE phq_web_ro NOLOGIN;
 END IF;
END $$;
CREATE TABLE IF NOT EXISTS food_places (
  notion_id text PRIMARY KEY, name text NOT NULL, region text, housing text, cluster text,
  time_slots text, hours_text text, maps_query text, price_text text, cuisine text,
  worth double precision, convenience double precision, local_idx double precision,
  pq_feature double precision, kid_fit double precision, grade text, op_status text,
  op_conf text, atlas_state text, data_conf text, research_date text, last_verified text,
  evidence text, neg_warn text, summary text, dish_ids text, evidence_as_of text,
  kid_plan text, version integer NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS cards (
  slug text PRIMARY KEY, name text NOT NULL, status text NOT NULL DEFAULT 'ACTIVE',
  route text, gates text, transport text, notes text, summary text, key_times text,
  badges text, stops text, transport_out text, transport_back text, kid_note text,
  dining text, cut_order text, callout text, evidence_as_of text
);
CREATE TABLE IF NOT EXISTS points (
  slug text PRIMARY KEY, name text NOT NULL, area text NOT NULL, interest double precision,
  mandatory text, trip_priority text, condition_gate text, returnability text,
  play_mode text, durable_note text, status text, evidence_as_of text, condition_note text
);
CREATE TABLE IF NOT EXISTS food_pool (
  pool_key text PRIMARY KEY, notion_id text REFERENCES food_places(notion_id),
  pool_rank integer NOT NULL, pool_role text NOT NULL, order_copy text NOT NULL DEFAULT '',
  desc_copy text NOT NULL DEFAULT '', divider text
);
CREATE TABLE IF NOT EXISTS bookings (
  slug text PRIMARY KEY, kind text NOT NULL, title text NOT NULL, detail text,
  amount text, status text NOT NULL DEFAULT 'Confirmed', evidence text, evidence_as_of text
);
CREATE TABLE IF NOT EXISTS transport_options (
  slug text PRIMARY KEY, direction text, plan text NOT NULL, station text, status text,
  priority text, note text, evidence_as_of text
);
CREATE TABLE IF NOT EXISTS content_revisions (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, target_table text NOT NULL,
  target_id text NOT NULL, field_name text NOT NULL, old_value text, new_value text,
  changed_at text DEFAULT (now()::text), actor text, source text, reason text,
  base_version integer, resulting_version integer
);

-- TEST SEED (rollback fixture)
INSERT INTO food_places(notion_id,name,hours_text,kid_plan) VALUES
 ('fixture-food','Fixture food','old hours','PRIVATE'),
 ('fixture-unrelated','Unrelated food','old hours','PRIVATE');
INSERT INTO cards(slug,name) VALUES ('onbird','Fixture card');
INSERT INTO points(slug,name,area,condition_note) VALUES ('fixture-point','Fixture point','Test','PRIVATE');
INSERT INTO food_pool(pool_key,notion_id,pool_rank,pool_role)
 VALUES ('fixture-pool','fixture-food',1,'fallback');
INSERT INTO bookings(slug,kind,title,detail,status,evidence)
 VALUES ('fixture-booking','hotel','Fixture hotel','PRIVATE','Confirmed','PRIVATE');
INSERT INTO transport_options(slug,plan) VALUES ('fixture-transport','Fixture transfer');
INSERT INTO itineraries(id,start_date,end_date,timezone,locked_constraints)
 VALUES ('phuquoc-2026','2026-10-10','2026-10-15','Asia/Ho_Chi_Minh',
 '{"bases":{"hotel":{"type":"booking","id":"fixture-booking"}},"bookings":["fixture-booking"],"transport":["fixture-transport"]}');
INSERT INTO itinerary_days(id,itinerary_id,date,day_kind,main_card_slug,plan)
SELECT 'phuquoc-2026:' || d::date::text,'phuquoc-2026',d::date,
 CASE WHEN d='2026-10-11'::date THEN 'activity' ELSE 'light' END,
 CASE WHEN d='2026-10-11'::date THEN 'onbird' ELSE NULL END,
 CASE WHEN d='2026-10-10'::date THEN
 '{"schema_version":1,"segments":[
  {"id":"start","kind":"activity","label":"Start","time":{"start_window":{"min":"09:00","max":"10:00"},"day_offset":0,"timezone":"Asia/Ho_Chi_Minh","duration_minutes":{"min":10,"max":30},"kind":"estimated","source_refs":[],"evidence_as_of":null},"ref":{"type":"point","id":"fixture-point"},"condition_refs":[]},
  {"id":"meal","kind":"meal","label":"Lunch","time":{"start_window":null,"day_offset":0,"timezone":"Asia/Ho_Chi_Minh","duration_minutes":null,"kind":"unknown","source_refs":[],"evidence_as_of":null},"ref":{"type":"pool","id":"fixture-pool"},"selection":"derived","condition_refs":[]},
  {"id":"go","kind":"transfer","label":"Go","time":{"start_window":null,"day_offset":0,"timezone":"Asia/Ho_Chi_Minh","duration_minutes":null,"kind":"unknown","source_refs":[],"evidence_as_of":null},"ref":null,"transfer":{"from_ref":{"type":"point","id":"fixture-point"},"to_ref":{"type":"base","id":"hotel"},"mode":"grab","wait_minutes":null,"buffer_minutes":5,"condition_refs":[]},"condition_refs":[]}
 ],"alternatives":[{"id":"rain","trigger_kind":"weather","trigger_text":"Rain","action":"use_alternative","target_segment_ids":["start"],"replacement_segments":[{"id":"rain-rest","kind":"rest","label":"Rest","time":{"start_window":null,"day_offset":0,"timezone":"Asia/Ho_Chi_Minh","duration_minutes":null,"kind":"unknown","source_refs":[],"evidence_as_of":null},"ref":null,"condition_refs":[]}]}]}'::jsonb
 WHEN d='2026-10-11'::date THEN
 '{"schema_version":1,"segments":[{"id":"main","kind":"activity","label":"Activity","time":{"start_window":null,"day_offset":0,"timezone":"Asia/Ho_Chi_Minh","duration_minutes":null,"kind":"unknown","source_refs":[],"evidence_as_of":null},"ref":{"type":"card","id":"onbird"},"condition_refs":[]}],"alternatives":[]}'::jsonb
 ELSE '{"schema_version":1,"segments":[],"alternatives":[]}'::jsonb END
FROM generate_series('2026-10-10'::date,'2026-10-15'::date,'1 day'::interval) AS d;
