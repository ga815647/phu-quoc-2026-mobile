-- Additive schema only; no trip content seeded by this migration.
ALTER TABLE public.content_revisions ADD COLUMN IF NOT EXISTS request_id uuid;
CREATE INDEX IF NOT EXISTS content_revisions_request_id_idx
  ON public.content_revisions(request_id) WHERE request_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.itineraries (
 id text PRIMARY KEY, start_date date NOT NULL, end_date date NOT NULL,
 timezone text NOT NULL, version integer NOT NULL DEFAULT 1 CHECK(version > 0),
 updated_at timestamptz NOT NULL DEFAULT now(),
 locked_constraints jsonb NOT NULL DEFAULT '{}'::jsonb,
 CONSTRAINT itineraries_fixed_trip_check CHECK (
   id = 'phuquoc-2026' AND start_date = DATE '2026-10-10'
   AND end_date = DATE '2026-10-15' AND timezone = 'Asia/Ho_Chi_Minh')
);
CREATE TABLE IF NOT EXISTS public.itinerary_days (
 id text PRIMARY KEY, itinerary_id text NOT NULL REFERENCES public.itineraries(id),
 date date NOT NULL, day_kind text NOT NULL CHECK(day_kind IN ('arrival','activity','light','departure')),
 main_card_slug text REFERENCES public.cards(slug), plan jsonb NOT NULL,
 version integer NOT NULL DEFAULT 1 CHECK(version > 0),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (itinerary_id,date), CHECK (id = itinerary_id || ':' || date::text),
 CHECK (day_kind <> 'activity' OR main_card_slug IS NOT NULL),
 CONSTRAINT itinerary_days_fixed_trip_check CHECK (
   itinerary_id = 'phuquoc-2026' AND date BETWEEN DATE '2026-10-10' AND DATE '2026-10-15')
);
-- CREATE TABLE IF NOT EXISTS does not add constraints to already-created tables.
-- Keep the migration rerunnable on the isolated test database and fail if
-- existing rows violate the approved trip boundaries.
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint
     WHERE conrelid='public.itineraries'::regclass AND conname='itineraries_fixed_trip_check') THEN
  ALTER TABLE public.itineraries ADD CONSTRAINT itineraries_fixed_trip_check CHECK (
    id = 'phuquoc-2026' AND start_date = DATE '2026-10-10'
    AND end_date = DATE '2026-10-15' AND timezone = 'Asia/Ho_Chi_Minh');
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint
     WHERE conrelid='public.itinerary_days'::regclass AND conname='itinerary_days_fixed_trip_check') THEN
  ALTER TABLE public.itinerary_days ADD CONSTRAINT itinerary_days_fixed_trip_check CHECK (
    itinerary_id = 'phuquoc-2026' AND date BETWEEN DATE '2026-10-10' AND DATE '2026-10-15');
 END IF;
END $$;
CREATE TABLE IF NOT EXISTS public.itinerary_requests (
 itinerary_id text NOT NULL REFERENCES public.itineraries(id), request_id uuid NOT NULL,
 canonical_request_hash text NOT NULL, base_version integer NOT NULL,
 resulting_version integer NOT NULL, changed_day_ids jsonb NOT NULL,
 result_content_revision text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (itinerary_id,request_id)
);

-- All helpers operate as invoker except the public, fixed projection which
-- needs its owner to read raw source tables (the read-only role cannot).
CREATE OR REPLACE FUNCTION public.itinerary_keys(v jsonb, allowed text[], required text[])
RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
 SELECT jsonb_typeof(v)='object'
    AND NOT EXISTS (SELECT 1 FROM jsonb_object_keys(CASE WHEN jsonb_typeof(v)='object' THEN v ELSE '{}'::jsonb END) k WHERE NOT k=ANY(allowed))
    AND NOT EXISTS (SELECT 1 FROM unnest(required) k WHERE NOT v ? k)
$$;

CREATE OR REPLACE FUNCTION public.itinerary_interval(v jsonb, is_clock boolean)
RETURNS boolean LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE lo text; hi text;
BEGIN
 IF v IS NULL OR v='null'::jsonb THEN RETURN true; END IF;
 IF NOT public.itinerary_keys(v, ARRAY['min','max'], ARRAY['min','max']) THEN RETURN false; END IF;
 IF is_clock THEN
  IF jsonb_typeof(v->'min')<>'string' OR jsonb_typeof(v->'max')<>'string' THEN RETURN false; END IF;
  lo := v->>'min'; hi := v->>'max';
  RETURN lo ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$' AND hi ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$' AND lo <= hi;
 END IF;
 IF jsonb_typeof(v->'min')<>'number' OR jsonb_typeof(v->'max')<>'number' THEN RETURN false; END IF;
 RETURN (v->>'min') ~ '^[0-9]+$' AND (v->>'max') ~ '^[0-9]+$'
   AND (v->>'min')::numeric <= (v->>'max')::numeric;
END $$;

CREATE OR REPLACE FUNCTION public.itinerary_ref_ok(r jsonb, constraints jsonb)
RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE kind text; ident text; base jsonb;
BEGIN
 IF r IS NULL OR r='null'::jsonb THEN RETURN true; END IF;
 IF NOT public.itinerary_keys(r, ARRAY['type','id'],ARRAY['type','id'])
    OR jsonb_typeof(r->'type')<>'string' OR jsonb_typeof(r->'id')<>'string'
    OR r->>'id'='' THEN RETURN false; END IF;
 kind := r->>'type'; ident := r->>'id';
 CASE kind
 WHEN 'card' THEN RETURN EXISTS (SELECT 1 FROM public.cards WHERE slug=ident);
 WHEN 'food' THEN RETURN EXISTS (SELECT 1 FROM public.food_places WHERE notion_id=ident);
 WHEN 'pool' THEN RETURN EXISTS (SELECT 1 FROM public.food_pool p WHERE p.pool_key=ident
     AND (p.notion_id IS NULL OR EXISTS(SELECT 1 FROM public.food_places f WHERE f.notion_id=p.notion_id)));
 WHEN 'point' THEN RETURN EXISTS (SELECT 1 FROM public.points WHERE slug=ident);
 WHEN 'base' THEN
  base := constraints->'bases'->ident;
  RETURN base IS NOT NULL AND base->>'type' IN ('booking','point')
    AND CASE base->>'type' WHEN 'booking' THEN EXISTS(SELECT 1 FROM public.bookings WHERE slug=base->>'id' AND status='Confirmed')
      ELSE EXISTS(SELECT 1 FROM public.points WHERE slug=base->>'id') END;
 ELSE RETURN false;
 END CASE;
END $$;

CREATE OR REPLACE FUNCTION public.itinerary_validate_day(p_day jsonb) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE p jsonb; s jsonb; a jsonb; t jsonb; tr jsonb; r jsonb; c jsonb; condition_segment record;
        ids text[] := '{}'; alt_ids text[] := '{}'; target text; cond text;
        constraints jsonb; itinerary_tz text; main_slug text; segment_card_slugs text[];
BEGIN
 IF p_day IS NULL OR octet_length(p_day::text)>131072 THEN RAISE EXCEPTION 'invalid'; END IF;
 IF NOT public.itinerary_keys(p_day, ARRAY['id','date','day_kind','main_card_slug','plan'],
     ARRAY['day_kind','main_card_slug','plan']) THEN RAISE EXCEPTION 'invalid'; END IF;
 IF p_day->>'day_kind' NOT IN ('arrival','activity','light','departure')
    OR jsonb_typeof(p_day->'day_kind') <> 'string' THEN RAISE EXCEPTION 'invalid'; END IF;
  main_slug := p_day->>'main_card_slug';
 IF p_day->'main_card_slug' IS NULL OR jsonb_typeof(p_day->'main_card_slug') NOT IN ('null','string')
    OR (p_day->>'day_kind'='activity' AND main_slug IS NULL)
     OR (main_slug IS NOT NULL AND (main_slug NOT IN ('onbird','vinwonders','cable','starfish','safari')
       OR NOT EXISTS (SELECT 1 FROM public.cards WHERE slug=main_slug AND status='ACTIVE')))
    THEN RAISE EXCEPTION 'invalid'; END IF;
 IF p_day ? 'id' AND (jsonb_typeof(p_day->'id')<>'string' OR p_day->>'id' !~ '^phuquoc-2026:2026-10-(1[0-5])$') THEN RAISE EXCEPTION 'invalid'; END IF;
 IF p_day ? 'date' AND (jsonb_typeof(p_day->'date')<>'string' OR p_day->>'date' !~ '^2026-10-1[0-5]$') THEN RAISE EXCEPTION 'invalid'; END IF;
 IF p_day ? 'id' AND p_day ? 'date' AND (p_day->>'id') <> ('phuquoc-2026:' || (p_day->>'date')) THEN RAISE EXCEPTION 'invalid'; END IF;
 SELECT locked_constraints,timezone INTO constraints,itinerary_tz FROM public.itineraries WHERE id='phuquoc-2026';
 IF itinerary_tz IS NULL THEN RAISE EXCEPTION 'invalid'; END IF;
 p := p_day->'plan';
 IF NOT public.itinerary_keys(p,ARRAY['schema_version','segments','alternatives','public_note'],
       ARRAY['schema_version','segments','alternatives']) OR p->'schema_version'<>'1'::jsonb
    OR jsonb_typeof(p->'segments')<>'array' OR jsonb_typeof(p->'alternatives')<>'array'
    OR jsonb_array_length(p->'segments')>32 OR jsonb_array_length(p->'alternatives')>8
    OR (p ? 'public_note' AND jsonb_typeof(p->'public_note')<>'string') THEN RAISE EXCEPTION 'invalid'; END IF;
 IF main_slug IS NOT NULL AND p_day->>'day_kind'='activity' AND NOT EXISTS (
   SELECT 1 FROM jsonb_array_elements(p->'segments') v
   WHERE v->>'kind'='activity' AND v->'ref'=jsonb_build_object('type','card','id',main_slug))
   THEN RAISE EXCEPTION 'invalid'; END IF;
 FOR a IN SELECT value FROM jsonb_array_elements(p->'alternatives') LOOP
  IF NOT public.itinerary_keys(a,ARRAY['id','trigger_kind','trigger_text','action','target_segment_ids','replacement_segments'],
       ARRAY['id','trigger_kind','trigger_text','action','target_segment_ids','replacement_segments'])
     OR jsonb_typeof(a->'id')<>'string' OR a->>'id' !~ '^[a-z0-9][a-z0-9-]{0,39}$'
     OR a->>'id'=ANY(alt_ids) OR a->>'trigger_kind' NOT IN ('weather','fatigue','late','unavailable','manual')
     OR jsonb_typeof(a->'trigger_text')<>'string' OR a->>'action' NOT IN ('skip_optional','use_alternative','return_or_rest')
     OR jsonb_typeof(a->'target_segment_ids')<>'array' OR jsonb_typeof(a->'replacement_segments')<>'array'
     OR jsonb_array_length(a->'replacement_segments')>32
     OR EXISTS(SELECT 1 FROM jsonb_array_elements(a->'target_segment_ids') v WHERE jsonb_typeof(v)<>'string')
     OR (a->>'action'='use_alternative') <> (jsonb_array_length(a->'replacement_segments')>0)
     THEN RAISE EXCEPTION 'invalid'; END IF;
  alt_ids := array_append(alt_ids,a->>'id');
 END LOOP;
 FOR s IN SELECT value FROM jsonb_array_elements(p->'segments')
     UNION ALL SELECT s2.value FROM jsonb_array_elements(p->'alternatives') a2,
       LATERAL jsonb_array_elements(a2->'replacement_segments') s2 LOOP
  IF NOT public.itinerary_keys(s,ARRAY['id','kind','label','time','ref','selection','transfer','condition_refs','note'],
      ARRAY['id','kind','label','time','ref','condition_refs'])
      OR jsonb_typeof(s->'id')<>'string' OR s->>'id' !~ '^[a-z0-9][a-z0-9-]{0,39}$'
      OR s->>'id'=ANY(ids) OR s->>'kind' NOT IN ('activity','meal','transfer','rest','optional')
      OR jsonb_typeof(s->'label')<>'string'
      OR (s ? 'note' AND jsonb_typeof(s->'note')<>'string')
      OR (s ? 'selection' AND s->>'selection' NOT IN ('derived','explicit'))
       OR (s->>'kind'='meal' AND (NOT s ? 'selection' OR s->'ref'->>'type' NOT IN ('food','pool')
         OR s->'ref'->>'type' IS NULL))
      OR jsonb_typeof(s->'condition_refs')<>'array' THEN RAISE EXCEPTION 'invalid'; END IF;
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(s->'condition_refs') v WHERE jsonb_typeof(v)<>'string') THEN RAISE EXCEPTION 'invalid'; END IF;
  ids := array_append(ids,s->>'id');
  t := s->'time';
  IF NOT public.itinerary_keys(t,ARRAY['start_window','day_offset','timezone','duration_minutes','kind','source_refs','evidence_as_of'],
      ARRAY['start_window','day_offset','timezone','duration_minutes','kind','source_refs','evidence_as_of'])
      OR NOT public.itinerary_interval(t->'start_window',true)
      OR NOT public.itinerary_interval(t->'duration_minutes',false)
      OR t->'day_offset' NOT IN ('0'::jsonb,'1'::jsonb)
      OR jsonb_typeof(t->'timezone')<>'string'
      OR NOT EXISTS(SELECT 1 FROM pg_timezone_names WHERE name=t->>'timezone')
      OR t->>'kind' NOT IN ('scheduled','estimated','planned','unknown')
      OR (t->>'kind'='unknown' AND t->'duration_minutes'<>'null'::jsonb)
      OR jsonb_typeof(t->'source_refs')<>'array'
      OR (t->'evidence_as_of'<>'null'::jsonb AND (jsonb_typeof(t->'evidence_as_of')<>'string' OR t->>'evidence_as_of' !~ '^\d{4}-\d{2}-\d{2}$'))
      OR EXISTS(SELECT 1 FROM jsonb_array_elements(t->'source_refs') v WHERE jsonb_typeof(v)<>'string')
      THEN RAISE EXCEPTION 'invalid'; END IF;
  IF NOT public.itinerary_ref_ok(s->'ref',constraints) THEN RAISE EXCEPTION 'invalid'; END IF;
  IF s->>'kind'='transfer' THEN
   tr := s->'transfer';
   IF NOT public.itinerary_keys(tr,ARRAY['from_ref','to_ref','mode','wait_minutes','buffer_minutes','condition_refs'],
       ARRAY['from_ref','to_ref','mode','wait_minutes','buffer_minutes','condition_refs'])
     OR tr->>'mode' NOT IN ('operator_pickup','grab','taxi','bus','charter','walk','cable')
     OR tr->'from_ref'='null'::jsonb OR tr->'to_ref'='null'::jsonb
     OR NOT public.itinerary_ref_ok(tr->'from_ref',constraints)
     OR NOT public.itinerary_ref_ok(tr->'to_ref',constraints)
     OR NOT public.itinerary_interval(tr->'wait_minutes',false)
     OR jsonb_typeof(tr->'buffer_minutes')<>'number' OR tr->>'buffer_minutes' !~ '^[0-9]+$'
     OR jsonb_typeof(tr->'condition_refs')<>'array' THEN RAISE EXCEPTION 'invalid'; END IF;
   IF EXISTS(SELECT 1 FROM jsonb_array_elements(tr->'condition_refs') v WHERE jsonb_typeof(v)<>'string') THEN RAISE EXCEPTION 'invalid'; END IF;
  ELSIF s ? 'transfer' THEN RAISE EXCEPTION 'invalid'; END IF;
 END LOOP;
 FOR a IN SELECT value FROM jsonb_array_elements(p->'alternatives') LOOP
  FOR r IN SELECT value FROM jsonb_array_elements(a->'target_segment_ids') LOOP
   IF jsonb_typeof(r)<>'string' OR NOT ((r #>> '{}') = ANY(ARRAY(SELECT value->>'id' FROM jsonb_array_elements(p->'segments'))))
    THEN RAISE EXCEPTION 'invalid'; END IF;
  END LOOP;
 END LOOP;
  FOR condition_segment IN SELECT value AS segment, false AS replacement FROM jsonb_array_elements(p->'segments')
      UNION ALL SELECT s2.value, true FROM jsonb_array_elements(p->'alternatives') a2,
        LATERAL jsonb_array_elements(a2->'replacement_segments') s2 LOOP
   SELECT coalesce(array_agg(local_refs.card_ref->>'id'),'{}') INTO segment_card_slugs FROM (
     SELECT condition_segment.segment->'ref' AS card_ref
     UNION ALL SELECT condition_segment.segment->'transfer'->'from_ref'
     UNION ALL SELECT condition_segment.segment->'transfer'->'to_ref') local_refs
     WHERE local_refs.card_ref->>'type'='card';
   FOR cond IN SELECT v #>> '{}' FROM jsonb_array_elements(condition_segment.segment->'condition_refs') v
       UNION ALL SELECT v #>> '{}' FROM jsonb_array_elements(COALESCE(condition_segment.segment->'transfer'->'condition_refs','[]'::jsonb)) v LOOP
    IF (condition_segment.replacement AND cond=ANY(alt_ids)) OR
       (NOT cond=ANY(alt_ids) AND NOT EXISTS (SELECT 1 FROM public.cards
        WHERE slug=ANY(segment_card_slugs) AND gates IS NOT NULL AND CASE WHEN gates ~ '^\s*\[' THEN
         jsonb_typeof(gates::jsonb)='array' AND (gates::jsonb) ? cond ELSE false END)
        AND NOT ('starfish'=ANY(segment_card_slugs)
          AND jsonb_typeof(constraints->'starfish'->'conditions')='object'
          AND constraints->'starfish'->'conditions' ? cond
          AND EXISTS (SELECT 1 FROM public.cards c WHERE c.slug='starfish' AND c.gates IS NOT NULL
            AND CASE WHEN c.gates ~ '^\s*\[' THEN jsonb_typeof(c.gates::jsonb)='array'
              AND (c.gates::jsonb) ? (constraints->'starfish'->'conditions'->>cond) ELSE false END)))
       THEN RAISE EXCEPTION 'invalid'; END IF;
  END LOOP;
 END LOOP;
EXCEPTION WHEN OTHERS THEN
 RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='itinerary: invalid day';
END $$;

CREATE OR REPLACE FUNCTION public.itinerary_payload(p_id text) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE trip record; d record; s jsonb; r jsonb; alt jsonb; result_days jsonb := '[]';
        card_ids text[] := '{}'; food_ids text[] := '{}'; pool_ids text[] := '{}'; point_ids text[] := '{}';
        booking_ids text[] := '{}'; transport_ids text[] := '{}'; base_ids text[] := '{}'; base jsonb;
        k text; ids text[]; out_refs jsonb := '{}'::jsonb; vals jsonb; n integer;
BEGIN
 SELECT * INTO trip FROM public.itineraries WHERE id=p_id;
 IF NOT FOUND THEN RETURN NULL; END IF;
 IF p_id<>'phuquoc-2026' OR trip.start_date<>'2026-10-10'::date OR trip.end_date<>'2026-10-15'::date
   OR trip.timezone<>'Asia/Ho_Chi_Minh' THEN RAISE EXCEPTION 'invalid'; END IF;
 FOR d IN SELECT * FROM public.itinerary_days WHERE itinerary_id=p_id ORDER BY date LOOP
  IF d.date<trip.start_date OR d.date>trip.end_date OR d.id<>p_id||':'||d.date::text THEN RAISE EXCEPTION 'invalid'; END IF;
  PERFORM public.itinerary_validate_day(jsonb_build_object('id',d.id,'date',d.date,
     'day_kind',d.day_kind,'main_card_slug',d.main_card_slug,'plan',d.plan));
  result_days := result_days || jsonb_build_array(jsonb_build_object('id',d.id,'date',d.date,
    'day_kind',d.day_kind,'main_card_slug',d.main_card_slug,'plan',d.plan));
  IF d.main_card_slug IS NOT NULL THEN card_ids := array_append(card_ids,d.main_card_slug); END IF;
  FOR s IN SELECT value FROM jsonb_array_elements(d.plan->'segments')
     UNION ALL SELECT x.value FROM jsonb_array_elements(d.plan->'alternatives') a,
       LATERAL jsonb_array_elements(a->'replacement_segments') x LOOP
   FOR r IN SELECT s->'ref' UNION ALL SELECT s->'transfer'->'from_ref'
     UNION ALL SELECT s->'transfer'->'to_ref' LOOP
    CASE r->>'type'
    WHEN 'card' THEN card_ids := array_append(card_ids,r->>'id');
    WHEN 'food' THEN food_ids := array_append(food_ids,r->>'id');
    WHEN 'pool' THEN pool_ids := array_append(pool_ids,r->>'id');
    WHEN 'point' THEN point_ids := array_append(point_ids,r->>'id');
    WHEN 'base' THEN base_ids := array_append(base_ids,r->>'id');
    ELSE NULL;
    END CASE;
   END LOOP;
  END LOOP;
 END LOOP;
 IF jsonb_array_length(result_days)<>6 THEN RAISE EXCEPTION 'invalid'; END IF;
  FOR k IN SELECT DISTINCT unnest(base_ids) LOOP
   base := trip.locked_constraints->'bases'->k;
   IF base->>'type'='booking' THEN booking_ids:=array_append(booking_ids,base->>'id');
   ELSIF base->>'type'='point' THEN point_ids:=array_append(point_ids,base->>'id');
   ELSE RAISE EXCEPTION 'invalid'; END IF;
  END LOOP;
  -- Publish only reachable base mappings; never expose all locked constraints.
  SELECT coalesce(jsonb_agg(jsonb_build_object('id',b.id,'ref',trip.locked_constraints->'bases'->b.id)
      ORDER BY b.id),'[]'::jsonb) INTO vals
    FROM (SELECT DISTINCT unnest(base_ids) AS id) b;
  out_refs := jsonb_build_object('bases',vals);
 FOR k IN SELECT value #>> '{}' FROM jsonb_array_elements(COALESCE(trip.locked_constraints->'bookings','[]'::jsonb)) LOOP
  booking_ids:=array_append(booking_ids,k);
 END LOOP;
 FOR k IN SELECT value #>> '{}' FROM jsonb_array_elements(COALESCE(trip.locked_constraints->'transport','[]'::jsonb)) LOOP
  transport_ids:=array_append(transport_ids,k);
 END LOOP;
 -- Include indirect pool food IDs as well as the direct IDs collected above.
 FOR k IN SELECT DISTINCT p.notion_id FROM public.food_pool p
    WHERE p.pool_key=ANY(pool_ids) AND p.notion_id IS NOT NULL LOOP
  food_ids := array_append(food_ids,k);
 END LOOP;
 -- Generic stable-ID source lists; never SELECT * from underlying tables.
 FOR k IN SELECT unnest(ARRAY['cards','foods','pool','points','bookings','transport']) LOOP
  CASE k WHEN 'cards' THEN ids:=card_ids; WHEN 'foods' THEN ids:=food_ids;
   WHEN 'pool' THEN ids:=pool_ids; WHEN 'points' THEN ids:=point_ids;
   WHEN 'bookings' THEN ids:=booking_ids; ELSE ids:=transport_ids; END CASE;
  SELECT count(*) INTO n FROM (SELECT DISTINCT unnest(ids) AS id) i;
  CASE k
    WHEN 'cards' THEN SELECT coalesce(jsonb_agg(to_jsonb(x) || jsonb_build_object('condition_labels',
       CASE WHEN x.slug='starfish' THEN coalesce(trip.locked_constraints->'starfish'->'conditions','{}'::jsonb)
       ELSE '{}'::jsonb END) ORDER BY x.slug),'[]'::jsonb) INTO vals FROM
    (SELECT slug,name,status,route,gates,transport,notes,summary,key_times,badges,stops,transport_out,transport_back,kid_note,dining,cut_order,callout,evidence_as_of FROM public.cards WHERE slug=ANY(ids)) x;
   WHEN 'foods' THEN SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY x.notion_id),'[]'::jsonb) INTO vals FROM
    (SELECT notion_id,name,region,housing,cluster,time_slots,hours_text,maps_query,price_text,cuisine,worth,convenience,local_idx,pq_feature,kid_fit,grade,op_status,op_conf,atlas_state,data_conf,research_date,last_verified,evidence,neg_warn,summary,dish_ids,evidence_as_of FROM public.food_places WHERE notion_id=ANY(ids)) x;
   WHEN 'pool' THEN SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY x.pool_key),'[]'::jsonb) INTO vals FROM
    (SELECT pool_key,notion_id,pool_rank,pool_role,order_copy,desc_copy,divider FROM public.food_pool WHERE pool_key=ANY(ids)) x;
   WHEN 'points' THEN SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY x.slug),'[]'::jsonb) INTO vals FROM
    (SELECT slug,name,area,interest,mandatory,trip_priority,condition_gate,returnability,play_mode,durable_note,status,evidence_as_of FROM public.points WHERE slug=ANY(ids)) x;
   WHEN 'bookings' THEN SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY x.slug),'[]'::jsonb) INTO vals FROM
    (SELECT slug,kind,title,amount,status,evidence_as_of FROM public.bookings WHERE slug=ANY(ids)) x;
   WHEN 'transport' THEN SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY x.slug),'[]'::jsonb) INTO vals FROM
    (SELECT slug,direction,plan,station,status,priority,note,evidence_as_of FROM public.transport_options WHERE slug=ANY(ids)) x;
  END CASE;
  IF jsonb_array_length(vals)<>n THEN RAISE EXCEPTION 'invalid'; END IF;
  out_refs := out_refs || jsonb_build_object(k,vals);
 END LOOP;
  RETURN jsonb_build_object('schema_version',1,
    'itinerary',jsonb_build_object('id',p_id,'start_date',trip.start_date,
      'end_date',trip.end_date,'timezone',trip.timezone),
    'days',result_days,'refs',out_refs);
EXCEPTION WHEN OTHERS THEN
 RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='itinerary: invalid projection';
END $$;

-- MATERIALIZED prevents planner inlining from evaluating the payload function
-- separately for payload and hash; both values share one statement snapshot.
CREATE OR REPLACE VIEW public.itinerary_public AS
WITH p AS MATERIALIZED (
 SELECT id, public.itinerary_payload(id) AS payload FROM public.itineraries
)
SELECT id AS itinerary_id, payload,
 'phq1:' || encode(sha256(convert_to(payload::text,'UTF8')),'hex') AS content_revision
FROM p;

CREATE OR REPLACE FUNCTION public.itinerary_read_for_edit(p_id text) RETURNS jsonb
LANGUAGE sql STABLE SECURITY INVOKER AS $$
 SELECT jsonb_build_object('version',i.version,'content_revision',v.content_revision,
   'days',coalesce((SELECT jsonb_agg(jsonb_build_object('id',d.id,'date',d.date,
       'day_kind',d.day_kind,'main_card_slug',d.main_card_slug,'plan',d.plan,
       'version',d.version) ORDER BY d.date) FROM public.itinerary_days d
       WHERE d.itinerary_id=i.id),'[]'::jsonb))
 FROM public.itineraries i JOIN public.itinerary_public v ON v.itinerary_id=i.id WHERE i.id=p_id
 $$;

-- Only IDs used by the existing itinerary, its approved bases and the proposed
-- days are locked. pool -> food is expanded before locking and compared again
-- after the pool locks: a changed edge must restart from a fresh source read.
CREATE OR REPLACE FUNCTION public.itinerary_dependency_ids(p_id text, p_changes jsonb)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY INVOKER
SET search_path=pg_catalog,public AS $$
DECLARE d jsonb; s jsonb; r jsonb; base jsonb; constraints jsonb;
        deps jsonb := '{"cards":[],"pool":[],"foods":[],"points":[],"bookings":[],"transport":[]}'::jsonb;
        kind text; ident text; category text; k text;
BEGIN
 SELECT locked_constraints INTO constraints FROM public.itineraries WHERE id=p_id;
 FOR d IN SELECT jsonb_build_object('main_card_slug',main_card_slug,'plan',plan)
     FROM public.itinerary_days WHERE itinerary_id=p_id
     UNION ALL SELECT value FROM jsonb_array_elements(p_changes) LOOP
  IF d->>'main_card_slug' IS NOT NULL THEN
   deps := jsonb_set(deps,'{cards}',deps->'cards'||to_jsonb(d->>'main_card_slug'));
  END IF;
  FOR s IN SELECT value FROM jsonb_array_elements(d->'plan'->'segments')
      UNION ALL SELECT x.value FROM jsonb_array_elements(d->'plan'->'alternatives') a,
        LATERAL jsonb_array_elements(a->'replacement_segments') x LOOP
   FOR r IN SELECT s->'ref' UNION ALL SELECT s->'transfer'->'from_ref'
       UNION ALL SELECT s->'transfer'->'to_ref' LOOP
    kind := r->>'type'; ident := r->>'id';
    IF kind='base' THEN
     base := constraints->'bases'->ident;
     kind := base->>'type'; ident := base->>'id';
    END IF;
    category := CASE kind WHEN 'card' THEN 'cards' WHEN 'food' THEN 'foods'
      WHEN 'pool' THEN 'pool' WHEN 'point' THEN 'points'
      WHEN 'booking' THEN 'bookings' ELSE NULL END;
    IF category IS NOT NULL AND ident IS NOT NULL THEN
     deps := jsonb_set(deps,ARRAY[category],deps->category||to_jsonb(ident));
    END IF;
   END LOOP;
  END LOOP;
 END LOOP;
 FOR k IN SELECT value #>> '{}' FROM jsonb_array_elements(COALESCE(constraints->'bookings','[]'::jsonb)) LOOP
  deps := jsonb_set(deps,'{bookings}',deps->'bookings'||to_jsonb(k));
 END LOOP;
 FOR k IN SELECT value #>> '{}' FROM jsonb_array_elements(COALESCE(constraints->'transport','[]'::jsonb)) LOOP
  deps := jsonb_set(deps,'{transport}',deps->'transport'||to_jsonb(k));
 END LOOP;
 FOR k IN SELECT DISTINCT notion_id FROM public.food_pool
     WHERE pool_key IN (SELECT value #>> '{}' FROM jsonb_array_elements(deps->'pool'))
       AND notion_id IS NOT NULL LOOP
  deps := jsonb_set(deps,'{foods}',deps->'foods'||to_jsonb(k));
 END LOOP;
 FOR category IN SELECT unnest(ARRAY['cards','pool','foods','points','bookings','transport']) LOOP
  SELECT coalesce(jsonb_agg(id ORDER BY id),'[]'::jsonb) INTO r FROM
    (SELECT DISTINCT value #>> '{}' AS id FROM jsonb_array_elements(deps->category)) x;
  deps := jsonb_set(deps,ARRAY[category],r);
 END LOOP;
 RETURN deps;
END $$;

-- A stable ID/ref is not enough to preserve an explicit choice: a meal moved
-- from the main route to an alternative (or converted to rest) is no longer
-- the ordinary selected meal. Keep this classification shared by the required
-- decision check and the supplied-decision consistency check.
CREATE OR REPLACE FUNCTION public.itinerary_explicit_decision(
 p_old_plan jsonb, p_new_plan jsonb, p_segment_id text) RETURNS text
LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE old_segment jsonb; new_segment jsonb; old_location text; new_location text;
BEGIN
 SELECT segment,location INTO old_segment,old_location FROM (
   SELECT s.value AS segment,'main'::text AS location FROM jsonb_array_elements(p_old_plan->'segments') s
   UNION ALL SELECT s.value,'alternative:' || (a->>'id')
      FROM jsonb_array_elements(p_old_plan->'alternatives') a,
        LATERAL jsonb_array_elements(a->'replacement_segments') s) old
   WHERE segment->>'id'=p_segment_id;
 IF old_segment->>'selection' IS DISTINCT FROM 'explicit' THEN RETURN NULL; END IF;
 SELECT segment,location INTO new_segment,new_location FROM (
   SELECT s.value AS segment,'main'::text AS location FROM jsonb_array_elements(p_new_plan->'segments') s
   UNION ALL SELECT s.value,'alternative:' || (a->>'id')
      FROM jsonb_array_elements(p_new_plan->'alternatives') a,
        LATERAL jsonb_array_elements(a->'replacement_segments') s) candidate
   WHERE segment->>'id'=p_segment_id;
 IF new_segment IS NULL OR new_location IS DISTINCT FROM old_location
   OR new_segment->>'kind' IS DISTINCT FROM old_segment->>'kind' THEN RETURN 'remove'; END IF;
 IF new_segment->>'selection'='explicit' AND new_segment->'ref'=old_segment->'ref' THEN
  RETURN 'keep';
 END IF;
 IF new_segment->'ref' IS NULL OR new_segment->'ref'='null'::jsonb THEN RETURN 'remove'; END IF;
 RETURN 'replace';
 END $$;

-- A Starfish route is executable whether it is the main route or a selected
-- use_alternative replacement. Validate each flat route independently; a
-- transfer/condition in another alternative cannot complete this route.
CREATE OR REPLACE FUNCTION public.itinerary_starfish_route_ok(p_segments jsonb, p_constraints jsonb)
RETURNS boolean LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE config jsonb; activity jsonb; activity_order bigint; first_return jsonb; first_order bigint;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM jsonb_array_elements(p_segments) s WHERE
      s->'ref'='{"type":"card","id":"starfish"}'::jsonb
      OR s->'transfer'->'from_ref'='{"type":"card","id":"starfish"}'::jsonb
      OR s->'transfer'->'to_ref'='{"type":"card","id":"starfish"}'::jsonb) THEN
    RETURN true;
  END IF;
  config:=p_constraints->'starfish';
  IF NOT public.itinerary_keys(config,ARRAY['conditions','return_base'],ARRAY['conditions','return_base'])
    OR jsonb_typeof(config->'conditions')<>'object'
    OR NOT (config->'conditions' ? 'return')
    OR (SELECT count(*) FROM jsonb_object_keys(CASE WHEN jsonb_typeof(config->'conditions')='object'
      THEN config->'conditions' ELSE '{}'::jsonb END))<2
    OR EXISTS(SELECT 1 FROM jsonb_each(CASE WHEN jsonb_typeof(config->'conditions')='object'
      THEN config->'conditions' ELSE '{}'::jsonb END) gate WHERE jsonb_typeof(gate.value)<>'string')
    OR jsonb_typeof(config->'return_base')<>'string'
    OR NOT public.itinerary_ref_ok(jsonb_build_object('type','base','id',config->>'return_base'),p_constraints)
    OR EXISTS(SELECT 1 FROM jsonb_each_text(CASE WHEN jsonb_typeof(config->'conditions')='object'
      THEN config->'conditions' ELSE '{}'::jsonb END) gate
      WHERE gate.key !~ '^[a-z0-9][a-z0-9-]{0,39}$' OR gate.value=''
        OR NOT EXISTS (SELECT 1 FROM public.cards c WHERE c.slug='starfish' AND c.gates IS NOT NULL
          AND CASE WHEN c.gates ~ '^\s*\[' THEN jsonb_typeof(c.gates::jsonb)='array'
            AND (c.gates::jsonb) ? gate.value ELSE false END)) THEN
    RETURN false;
  END IF;
  SELECT s.value,s.ordinality INTO activity,activity_order
    FROM jsonb_array_elements(p_segments) WITH ORDINALITY s(value,ordinality)
    WHERE s.value->>'kind'='activity' AND s.value->'ref'='{"type":"card","id":"starfish"}'::jsonb
    ORDER BY s.ordinality LIMIT 1;
  IF activity IS NULL OR EXISTS (SELECT 1 FROM jsonb_object_keys(config->'conditions') gate
      WHERE NOT (activity->'condition_refs' ? gate)) THEN RETURN false; END IF;
  SELECT s.value,s.ordinality INTO first_return,first_order
    FROM jsonb_array_elements(p_segments) WITH ORDINALITY s(value,ordinality)
    WHERE s.value->>'kind'='transfer' AND s.value->'transfer'->'from_ref'='{"type":"card","id":"starfish"}'::jsonb
    ORDER BY s.ordinality LIMIT 1;
  RETURN first_return IS NOT NULL AND first_order>activity_order
    AND first_return->'transfer'->'to_ref'=jsonb_build_object('type','base','id',config->>'return_base')
    AND first_return->'transfer'->>'mode' IN ('charter','operator_pickup')
    AND first_return->'transfer'->'condition_refs' ? 'return';
END $$;

CREATE OR REPLACE FUNCTION public.itinerary_update(
 p_itinerary_id text, p_base_version integer, p_expected_content_revision text,
 p_request_id uuid, p_changes jsonb, p_explicit_selection_decisions jsonb,
 p_actor text, p_source text, p_reason text) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE v_version integer; v_constraints jsonb; v_hash text; v_receipt jsonb;
 v_request jsonb; v_deps jsonb; v_after_deps jsonb; v_revision text;
 v_table text; v_column text; v_category text; v_id text; v_row_id text;
 v_day jsonb; v_old record; v_new_version integer; v_changed jsonb := '[]'::jsonb;
 v_old_segment jsonb; v_decision jsonb; v_required text;
  v_protected jsonb; v_base text; v_locked integer; v_booking_ref jsonb;
  v_core jsonb; v_alternative jsonb;
BEGIN
 IF p_itinerary_id IS DISTINCT FROM 'phuquoc-2026' OR p_request_id IS NULL
    OR p_base_version IS NULL OR p_expected_content_revision IS NULL
    OR p_source IS NULL OR btrim(p_source)='' OR p_reason IS NULL OR btrim(p_reason)=''
    OR jsonb_typeof(p_changes) IS DISTINCT FROM 'array'
    OR jsonb_typeof(p_explicit_selection_decisions) IS DISTINCT FROM 'array' THEN
  RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='INVALID_PLAN';
 END IF;
 IF jsonb_array_length(p_changes) NOT BETWEEN 1 AND 6 THEN
  RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='INVALID_PLAN';
 END IF;
 v_request := jsonb_build_object('itinerary_id',p_itinerary_id,'base_version',p_base_version,
  'expected_content_revision',p_expected_content_revision,'changes',p_changes,
  'explicit_selection_decisions',p_explicit_selection_decisions,'actor',p_actor,
  'source',p_source,'reason',p_reason);
 IF octet_length(convert_to(v_request::text,'UTF8'))>131072 THEN
  RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='INVALID_PLAN';
 END IF;
 v_hash := encode(sha256(convert_to(v_request::text,'UTF8')),'hex');
 -- The itinerary lock serializes both the first submission and retries.
 SELECT version,locked_constraints INTO v_version,v_constraints
  FROM public.itineraries WHERE id=p_itinerary_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='INVALID_PLAN'; END IF;
 SELECT canonical_request_hash,
   jsonb_build_object('request_id',request_id,'resulting_version',resulting_version,
    'changed_day_ids',changed_day_ids,'content_revision',result_content_revision)
   INTO v_row_id,v_receipt FROM public.itinerary_requests
   WHERE itinerary_id=p_itinerary_id AND request_id=p_request_id;
 IF FOUND THEN
  IF v_row_id<>v_hash THEN RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='REQUEST_ID_REUSED'; END IF;
  RETURN v_receipt;
 END IF;
  IF v_version<>p_base_version THEN RAISE EXCEPTION USING ERRCODE='40001', MESSAGE='VERSION_CONFLICT'; END IF;

  -- Initialized by a separately reviewed insert, never inferred from the day
  -- being edited. Missing/malformed core blocks ALL edits, not just 10/11.
  v_core:=v_constraints->'onbird_core';
  IF NOT public.itinerary_keys(v_core,
       ARRAY['date','segment_id','kind','ref','time_kind','start_window','day_offset','timezone','duration_minutes'],
       ARRAY['date','segment_id','kind','ref','time_kind','start_window','day_offset','timezone','duration_minutes'])
    OR v_core->>'date'<>'2026-10-11' OR v_core->>'kind'<>'activity'
    OR v_core->'ref'<>'{"type":"card","id":"onbird"}'::jsonb
    OR v_core->>'segment_id' !~ '^[a-z0-9][a-z0-9-]{0,39}$'
    OR v_core->>'time_kind'<>'scheduled'
    OR v_core->>'timezone'<>'Asia/Ho_Chi_Minh'
    OR v_core->'day_offset'<>'0'::jsonb
    OR v_core->'start_window'='null'::jsonb
    OR NOT public.itinerary_interval(v_core->'start_window',true)
    OR NOT public.itinerary_interval(v_core->'duration_minutes',false)
    OR NOT EXISTS (SELECT 1 FROM public.itinerary_days d,
         LATERAL jsonb_array_elements(d.plan->'segments') s
       WHERE d.date=DATE '2026-10-11' AND d.main_card_slug='onbird'
         AND d.day_kind='activity' AND s->>'id'=v_core->>'segment_id'
         AND s->>'kind'=v_core->>'kind' AND s->'ref'=v_core->'ref'
         AND s->'time'->>'kind'=v_core->>'time_kind'
         AND s->'time'->'start_window'=v_core->'start_window'
         AND s->'time'->'day_offset'=v_core->'day_offset'
         AND s->'time'->>'timezone'=v_core->>'timezone'
         AND s->'time'->'duration_minutes'=v_core->'duration_minutes') THEN
   RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='LOCKED_ARRANGEMENT';
  END IF;

 -- Reject duplicate/missing dates and malformed candidates before touching rows.
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_changes) d WHERE
    NOT public.itinerary_keys(d,ARRAY['id','date','day_kind','main_card_slug','plan'],
      ARRAY['id','date','day_kind','main_card_slug','plan'])
    OR jsonb_typeof(d->'id')<>'string' OR jsonb_typeof(d->'date')<>'string'
    OR NOT EXISTS (SELECT 1 FROM public.itinerary_days old
     WHERE old.itinerary_id=p_itinerary_id AND old.id=d->>'id' AND old.date::text=d->>'date'))
  OR (SELECT count(DISTINCT d->>'id') FROM jsonb_array_elements(p_changes) d)<>jsonb_array_length(p_changes)
  OR EXISTS (SELECT 1 FROM jsonb_array_elements(p_explicit_selection_decisions) d WHERE
      NOT public.itinerary_keys(d,ARRAY['day_id','segment_id','previous_ref','decision'],
       ARRAY['day_id','segment_id','previous_ref','decision'])
      OR jsonb_typeof(d->'day_id')<>'string' OR jsonb_typeof(d->'segment_id')<>'string'
      OR d->>'decision' NOT IN ('keep','remove','replace'))
  OR (SELECT count(DISTINCT (d->>'day_id',d->>'segment_id'))
      FROM jsonb_array_elements(p_explicit_selection_decisions) d)
     <>jsonb_array_length(p_explicit_selection_decisions) THEN
  RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='INVALID_PLAN';
 END IF;
 -- Preflight shape/ref validation gives malformed candidate IDs INVALID_PLAN;
 -- run it again under source locks below to close the concurrent-change gap.
 FOR v_day IN SELECT value FROM jsonb_array_elements(p_changes) LOOP
  BEGIN
   PERFORM public.itinerary_validate_day(v_day);
  EXCEPTION WHEN OTHERS THEN
   RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='INVALID_PLAN';
  END;
 END LOOP;
 -- Collect pre-lock closure, then lock each source row FOR SHARE in a fixed
 -- category and stable-ID order. No candidate facts are assumed covered by the
 -- old public fingerprint: their current rows must be present and validated.
 BEGIN
  v_deps := public.itinerary_dependency_ids(p_itinerary_id,p_changes);
 EXCEPTION WHEN OTHERS THEN
  RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='INVALID_PLAN';
 END;
 FOR v_category IN SELECT unnest(ARRAY['cards','pool','foods','points','bookings','transport']) LOOP
  v_table := CASE v_category WHEN 'foods' THEN 'food_places' WHEN 'pool' THEN 'food_pool'
    WHEN 'transport' THEN 'transport_options' ELSE v_category END;
  v_column := CASE v_category WHEN 'foods' THEN 'notion_id' WHEN 'pool' THEN 'pool_key' ELSE 'slug' END;
  FOR v_id IN SELECT value #>> '{}' FROM jsonb_array_elements(v_deps->v_category) ORDER BY value #>> '{}' LOOP
   EXECUTE format('SELECT %I FROM public.%I WHERE %I=$1 FOR SHARE',v_column,v_table,v_column)
    INTO v_row_id USING v_id;
   GET DIAGNOSTICS v_locked = ROW_COUNT;
   IF v_locked<>1 THEN RAISE EXCEPTION USING ERRCODE='40001', MESSAGE='SOURCE_CHANGED'; END IF;
  END LOOP;
 END LOOP;
 v_after_deps := public.itinerary_dependency_ids(p_itinerary_id,p_changes);
 IF v_after_deps<>v_deps THEN RAISE EXCEPTION USING ERRCODE='40001', MESSAGE='SOURCE_CHANGED'; END IF;
 BEGIN
  SELECT content_revision INTO v_revision FROM public.itinerary_public WHERE itinerary_id=p_itinerary_id;
 EXCEPTION WHEN OTHERS THEN
  RAISE EXCEPTION USING ERRCODE='40001', MESSAGE='SOURCE_CHANGED';
 END;
 IF v_revision IS DISTINCT FROM p_expected_content_revision THEN
  RAISE EXCEPTION USING ERRCODE='40001', MESSAGE='SOURCE_CHANGED';
 END IF;

 -- Validate every candidate and every protected/explicit choice first; only
 -- after the entire request passes do we write a single day or audit row.
 FOR v_day IN SELECT value FROM jsonb_array_elements(p_changes) ORDER BY value->>'id' LOOP
  SELECT * INTO v_old FROM public.itinerary_days
    WHERE itinerary_id=p_itinerary_id AND id=v_day->>'id';
  BEGIN
   PERFORM public.itinerary_validate_day(v_day);
  EXCEPTION WHEN OTHERS THEN
   RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='INVALID_PLAN';
  END;
  IF v_day->>'date'<>v_old.date::text THEN RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='INVALID_PLAN'; END IF;
  v_protected := v_constraints->'days'->v_old.date::text;
   IF (v_day->>'main_card_slug'='onbird' AND v_old.date<>DATE '2026-10-11')
    OR (v_old.date=DATE '2026-10-11' AND v_old.main_card_slug='onbird'
      AND (v_day->>'main_card_slug'<>'onbird' OR v_day->>'day_kind'<>'activity'))
    OR (v_protected ? 'main_card_slug' AND v_day->'main_card_slug'<>v_protected->'main_card_slug')
    OR (v_protected ? 'day_kind' AND v_day->>'day_kind'<>v_protected->>'day_kind') THEN
    RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='LOCKED_ARRANGEMENT';
   END IF;
   IF v_old.date=DATE '2026-10-11' THEN
    IF NOT EXISTS (SELECT 1 FROM jsonb_array_elements(v_day->'plan'->'segments') s
      WHERE s->>'id'=v_core->>'segment_id' AND s->>'kind'=v_core->>'kind'
        AND s->'ref'=v_core->'ref' AND s->'time'->>'kind'=v_core->>'time_kind'
        AND s->'time'->'start_window'=v_core->'start_window'
        AND s->'time'->'day_offset'=v_core->'day_offset'
        AND s->'time'->>'timezone'=v_core->>'timezone'
        AND s->'time'->'duration_minutes'=v_core->'duration_minutes') THEN
     RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='LOCKED_ARRANGEMENT';
    END IF;
   END IF;
   IF NOT public.itinerary_starfish_route_ok(v_day->'plan'->'segments',v_constraints) THEN
     RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='LOCKED_ARRANGEMENT';
   END IF;
   FOR v_alternative IN SELECT value FROM jsonb_array_elements(v_day->'plan'->'alternatives')
       WHERE value->>'action'='use_alternative' LOOP
     IF NOT public.itinerary_starfish_route_ok(v_alternative->'replacement_segments',v_constraints) THEN
       RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='LOCKED_ARRANGEMENT';
     END IF;
   END LOOP;
  -- If a protected booking/base appeared on this date, it must still occur
  -- somewhere on this same date (not necessarily in the original transfer).
  FOR v_base IN SELECT key FROM jsonb_each(COALESCE(v_constraints->'bases','{}'::jsonb))
     WHERE value->>'type'='booking' AND value->>'id' IN
      (SELECT value #>> '{}' FROM jsonb_array_elements(COALESCE(v_constraints->'bookings','[]'::jsonb))) LOOP
   v_booking_ref := jsonb_build_object('type','base','id',v_base);
   -- Preserve the operative main-route role and transfer direction. A booking
   -- moved to a conditional replacement or an unrelated rest is not protected.
   FOR v_old_segment IN SELECT value FROM jsonb_array_elements(v_old.plan->'segments') LOOP
    IF v_old_segment->'ref'=v_booking_ref AND NOT EXISTS (
       SELECT 1 FROM jsonb_array_elements(v_day->'plan'->'segments') s
       WHERE s->>'kind'=v_old_segment->>'kind' AND s->'ref'=v_booking_ref) THEN
     RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='LOCKED_ARRANGEMENT';
    END IF;
    IF v_old_segment->'transfer'->'from_ref'=v_booking_ref AND NOT EXISTS (
       SELECT 1 FROM jsonb_array_elements(v_day->'plan'->'segments') s
       WHERE s->>'kind'='transfer' AND s->'transfer'->'from_ref'=v_booking_ref) THEN
     RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='LOCKED_ARRANGEMENT';
    END IF;
    IF v_old_segment->'transfer'->'to_ref'=v_booking_ref AND NOT EXISTS (
       SELECT 1 FROM jsonb_array_elements(v_day->'plan'->'segments') s
       WHERE s->>'kind'='transfer' AND s->'transfer'->'to_ref'=v_booking_ref) THEN
     RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='LOCKED_ARRANGEMENT';
    END IF;
   END LOOP;
  END LOOP;
  FOR v_old_segment IN SELECT value FROM jsonb_array_elements(v_old.plan->'segments')
     UNION ALL SELECT s.value FROM jsonb_array_elements(v_old.plan->'alternatives') a,
       LATERAL jsonb_array_elements(a->'replacement_segments') s LOOP
    IF v_old_segment->>'selection' IS DISTINCT FROM 'explicit' THEN CONTINUE; END IF;
    v_required := public.itinerary_explicit_decision(v_old.plan,v_day->'plan',v_old_segment->>'id');
    IF v_required='keep' THEN CONTINUE; END IF;
   IF NOT EXISTS (SELECT 1 FROM jsonb_array_elements(p_explicit_selection_decisions) d
     WHERE d->>'day_id'=v_old.id AND d->>'segment_id'=v_old_segment->>'id'
      AND d->'previous_ref'=v_old_segment->'ref' AND d->>'decision'=v_required) THEN
    RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='EXPLICIT_DECISION_REQUIRED';
   END IF;
  END LOOP;
  END LOOP;
  -- Decisions must describe an existing explicit segment of a changed day;
  -- stale/mismatched or duplicate declarations never silently authorize edits.
  FOR v_decision IN SELECT value FROM jsonb_array_elements(p_explicit_selection_decisions) LOOP
   SELECT * INTO v_old FROM public.itinerary_days d
     WHERE d.id=v_decision->>'day_id' AND d.itinerary_id=p_itinerary_id;
   SELECT value INTO v_day FROM jsonb_array_elements(p_changes) c
     WHERE c->>'id'=v_decision->>'day_id';
   IF v_old.id IS NULL OR v_day IS NULL OR NOT EXISTS (
     SELECT 1 FROM (SELECT value FROM jsonb_array_elements(v_old.plan->'segments')
       UNION ALL SELECT s.value FROM jsonb_array_elements(v_old.plan->'alternatives') a,
         LATERAL jsonb_array_elements(a->'replacement_segments') s) old
     WHERE old.value->>'id'=v_decision->>'segment_id'
       AND old.value->>'selection'='explicit' AND old.value->'ref'=v_decision->'previous_ref') THEN
    RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='EXPLICIT_DECISION_REQUIRED';
   END IF;
   v_required := public.itinerary_explicit_decision(v_old.plan,v_day->'plan',v_decision->>'segment_id');
  IF v_decision->>'decision'<>v_required THEN
   RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='EXPLICIT_DECISION_REQUIRED';
  END IF;
 END LOOP;

 FOR v_day IN SELECT value FROM jsonb_array_elements(p_changes) ORDER BY value->>'id' LOOP
  SELECT * INTO v_old FROM public.itinerary_days WHERE id=v_day->>'id';
  UPDATE public.itinerary_days SET day_kind=v_day->>'day_kind',
   main_card_slug=v_day->>'main_card_slug',plan=v_day->'plan',
   version=version+1,updated_at=now() WHERE id=v_old.id RETURNING version INTO v_new_version;
  INSERT INTO public.content_revisions(target_table,target_id,field_name,old_value,new_value,
    actor,source,reason,base_version,resulting_version,request_id)
   VALUES ('itinerary_days',v_old.id,'day_plan',
    jsonb_build_object('day_kind',v_old.day_kind,'main_card_slug',v_old.main_card_slug,'plan',v_old.plan)::text,
    jsonb_build_object('day_kind',v_day->'day_kind','main_card_slug',v_day->'main_card_slug','plan',v_day->'plan')::text,
    p_actor,p_source,p_reason,v_old.version,v_new_version,p_request_id);
  v_changed := v_changed || to_jsonb(v_old.id);
 END LOOP;
 UPDATE public.itineraries SET version=version+1,updated_at=now()
   WHERE id=p_itinerary_id RETURNING version INTO v_version;
 SELECT content_revision INTO v_revision FROM public.itinerary_public WHERE itinerary_id=p_itinerary_id;
 v_receipt := jsonb_build_object('request_id',p_request_id,'resulting_version',v_version,
   'changed_day_ids',v_changed,'content_revision',v_revision);
 INSERT INTO public.itinerary_requests(itinerary_id,request_id,canonical_request_hash,base_version,
    resulting_version,changed_day_ids,result_content_revision)
  VALUES(p_itinerary_id,p_request_id,v_hash,p_base_version,v_version,v_changed,v_revision);
 RETURN v_receipt;
END $$;

-- Explicitly remove private grants surviving CREATE OR REPLACE on rerun.
-- PostgreSQL requires caller EXECUTE on the projection helper used by the view;
-- it accepts only the fixed itinerary ID and is read-only.
REVOKE ALL ON public.itineraries,public.itinerary_days,public.itinerary_requests FROM PUBLIC,phq_web_ro;
REVOKE ALL ON public.itinerary_public FROM PUBLIC,phq_web_ro;
REVOKE ALL ON FUNCTION public.itinerary_validate_day(jsonb),public.itinerary_read_for_edit(text),
  public.itinerary_ref_ok(jsonb,jsonb),public.itinerary_interval(jsonb,boolean),
  public.itinerary_keys(jsonb,text[],text[]) FROM PUBLIC,phq_web_ro;
REVOKE ALL ON FUNCTION public.itinerary_payload(text) FROM PUBLIC,phq_web_ro;
 REVOKE ALL ON FUNCTION public.itinerary_dependency_ids(text,jsonb),
   public.itinerary_explicit_decision(jsonb,jsonb,text),
   public.itinerary_starfish_route_ok(jsonb,jsonb),
   public.itinerary_update(text,integer,text,uuid,jsonb,jsonb,text,text,text) FROM PUBLIC,phq_web_ro;
GRANT SELECT (itinerary_id,payload,content_revision) ON public.itinerary_public TO phq_web_ro;
GRANT EXECUTE ON FUNCTION public.itinerary_payload(text) TO phq_web_ro;
