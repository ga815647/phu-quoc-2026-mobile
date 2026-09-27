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
        constraints jsonb; itinerary_tz text; main_slug text; card_condition_slugs text[] := '{}';
BEGIN
 IF p_day IS NULL OR octet_length(p_day::text)>131072 THEN RAISE EXCEPTION 'invalid'; END IF;
 IF NOT public.itinerary_keys(p_day, ARRAY['id','date','day_kind','main_card_slug','plan'],
     ARRAY['day_kind','main_card_slug','plan']) THEN RAISE EXCEPTION 'invalid'; END IF;
 IF p_day->>'day_kind' NOT IN ('arrival','activity','light','departure')
    OR jsonb_typeof(p_day->'day_kind') <> 'string' THEN RAISE EXCEPTION 'invalid'; END IF;
 main_slug := p_day->>'main_card_slug';
 IF main_slug IS NOT NULL THEN card_condition_slugs := array_append(card_condition_slugs,main_slug); END IF;
 IF p_day->'main_card_slug' IS NULL OR jsonb_typeof(p_day->'main_card_slug') NOT IN ('null','string')
    OR (p_day->>'day_kind'='activity' AND main_slug IS NULL)
    OR (main_slug IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.cards WHERE slug=main_slug))
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
      OR (s->>'kind'='meal' AND (NOT s ? 'selection' OR s->'ref'='null'::jsonb))
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
  IF s->'ref'->>'type'='card' THEN card_condition_slugs:=array_append(card_condition_slugs,s->'ref'->>'id'); END IF;
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
   IF tr->'from_ref'->>'type'='card' THEN card_condition_slugs:=array_append(card_condition_slugs,tr->'from_ref'->>'id'); END IF;
   IF tr->'to_ref'->>'type'='card' THEN card_condition_slugs:=array_append(card_condition_slugs,tr->'to_ref'->>'id'); END IF;
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
  FOR cond IN SELECT v #>> '{}' FROM jsonb_array_elements(condition_segment.segment->'condition_refs') v
      UNION ALL SELECT v #>> '{}' FROM jsonb_array_elements(COALESCE(condition_segment.segment->'transfer'->'condition_refs','[]'::jsonb)) v LOOP
   IF (condition_segment.replacement AND cond=ANY(alt_ids)) OR
      (NOT cond=ANY(alt_ids) AND NOT EXISTS (SELECT 1 FROM public.cards
       WHERE slug=ANY(card_condition_slugs) AND gates IS NOT NULL AND CASE WHEN gates ~ '^\s*\[' THEN
        (gates::jsonb) ? cond ELSE false END)) THEN RAISE EXCEPTION 'invalid'; END IF;
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
   WHEN 'cards' THEN SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY x.slug),'[]'::jsonb) INTO vals FROM
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
 RETURN jsonb_build_object('schema_version',1,'itinerary_id',p_id,'start_date',trip.start_date,
   'end_date',trip.end_date,'timezone',trip.timezone,'days',result_days,'refs',out_refs);
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

REVOKE ALL ON public.itineraries,public.itinerary_days,public.itinerary_requests FROM PUBLIC;
REVOKE ALL ON public.itinerary_public FROM PUBLIC;
REVOKE ALL ON FUNCTION public.itinerary_validate_day(jsonb),public.itinerary_read_for_edit(text),
 public.itinerary_ref_ok(jsonb,jsonb),public.itinerary_interval(jsonb,boolean),
 public.itinerary_keys(jsonb,text[],text[]) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.itinerary_payload(text) FROM PUBLIC;
GRANT SELECT (itinerary_id,payload,content_revision) ON public.itinerary_public TO phq_web_ro;
GRANT EXECUTE ON FUNCTION public.itinerary_payload(text) TO phq_web_ro;
