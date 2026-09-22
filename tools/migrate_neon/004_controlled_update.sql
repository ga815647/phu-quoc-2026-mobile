-- 004_controlled_update.sql — 內容維護正式可用：受控更新入口＋精選池單一來源
--
-- 性質：僅加法（表／欄／函式／最小欄級授權），冪等可重跑；不刪改現有結構與資料。
-- 正式套用前需使用者明確確認；本檔先在測試分支驗證，驗證通過後原文提案上正式。
-- 回復方式：本檔不刪任何東西；若需回退，DROP FUNCTION content_update /
--   DROP TABLE food_pool / DROP TABLE content_revisions 之前必須先匯出三者內容備份，
--   且 version 欄保留（已寫入的版本號不可倒退）。
--
-- 重要聲明：content_update() 的管制是「程序性」的（白名單＋同交易＋真實前值＋
-- 版本檢查，全部在函式內原子執行），不是 DB 權限隔離。MCP 以具寫入能力身分
-- 執行；instruction 約束 ≠ GRANT/REVOKE。不得把本函式宣稱為強制權限隔離。

-- ============ A. 003 內含（冪等；正式庫目前缺 content_revisions 與 version） ============

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

ALTER TABLE food_places ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE dishes ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE dish_carriers ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE points ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE transport_options ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

-- evidence_log 維持 append-only（旅途中規則），不加 version。
-- content_revisions 不給 phq_web_ro 任何授權；公開 API 無端點。

-- ============ B. food_pool：美食精選池單一來源（取代 build_site.py 硬編碼 POOL） ============
-- pool_key：沿用既有池 ID（URL data-food-id 相容，不必改前端錨點）。
-- notion_id：穩定 ID；NULL 表示純靜態條目（目前僅 vinwonders-inside），只吃靜態文案，
--   不參與 API 回填。名稱變更不影響關聯；改名後回填仍命中。
-- 排序／推薦文案／角色 badge 唯一來源在此表；快照與 API 都由此表出，不再留多份互不一致的文案。
-- 全 69 家不自動進池；池成員只增不自動擴（新增需明確 INSERT 並經內容決策）。

CREATE TABLE IF NOT EXISTS food_pool (
  pool_key TEXT PRIMARY KEY,
  notion_id TEXT NULL REFERENCES food_places(notion_id),
  pool_rank INTEGER NOT NULL,
  pool_role TEXT NOT NULL
    CHECK (pool_role IN ('carrier','conditional','fallback','market','verify')),
  order_copy TEXT NOT NULL DEFAULT '',
  desc_copy TEXT NOT NULL DEFAULT '',
  divider TEXT,
  version INTEGER NOT NULL DEFAULT 1
);

-- 種子資料：逐字搬運自 build_site.py POOL（2026-09-22 版），notion_id 已用正式庫
-- lower(name) LIKE 比對逐一驗證唯一命中。ON CONFLICT DO NOTHING 保冪等。
INSERT INTO food_pool (pool_key, notion_id, pool_rank, pool_role, order_copy, desc_copy, divider) VALUES
('bun-ken-ut-luom', '3c839f3f-a67c-81fe-b212-e428ab484fe8', 1, 'carrier', 'Bún kèn', '富國島地方味優先完成；椰奶魚風味米線。Út Lượm 沒吃到再看 bún kèn 87 backup。', '主池｜這趟優先完成'),
('banh-mi-anh-thu', '3ce39f3f-a67c-81fb-b323-f1e9fb315a83', 2, 'carrier', 'Bánh mì', '高優先、低摩擦；很適合塞進行程空檔或晚一點快速吃。', NULL),
('banh-canh-phung', '3c839f3f-a67c-8102-8c02-fff2b82e0462', 3, 'carrier', 'Bánh canh cá', '魚湯粗粉類；早段機會比較珍貴，時間對就值得先完成。', NULL),
('bun-mam-dung-ha', '3c839f3f-a67c-81a9-8811-f9648d6c005c', 4, 'conditional', 'Bún mắm', '偏南部、發酵魚醬風味；想吃重一點的在地味時優先，營業窗再現場確認。', NULL),
('nhum-8k', '3ce39f3f-a67c-81cd-af26-cbd4749bcf5d', 5, 'conditional', 'Nhum nướng mỡ hành', '烤海膽＋蔥油；只在尚未完成 Nhum 時追，先確認有貨、做法與當日價。', NULL),
('banh-kheo-co-dung', '3c839f3f-a67c-819c-950a-e2629534cec7', 6, 'fallback', 'Bánh khéo 綜合幾種口味', '小顆、多口味，適合分食；不用硬塞在「下午茶」時段。', NULL),
('duong-dong-market', '3c839f3f-a67c-8142-a701-ef2552cbe841', 7, 'market', 'Bánh tét mật cật → kẹo chỉ / bánh bò thốt nốt → dừa sáp dầm thốt nốt；水果看 bòn bon / 榴槤', '熟食與小吃優先，不追固定攤；看到現做、熱賣的再買。', NULL),
('nha-xua-68', '3cc39f3f-a67c-81f7-b554-f062aa79b55d', 8, 'fallback', '沒有鎖定單一必點；看當日家常菜＋白飯', '孩子累、想舒服坐下、正餐時間亂掉時很好用。', NULL),
('com-tam-nhi', '3c839f3f-a67c-8117-badf-cfaac7584afc', 9, 'fallback', 'Cơm tấm', '想快速坐下吃一份飯時用；是實用 fallback，不是必追名店。', NULL),
('bup-seafood', '3cd39f3f-a67c-814f-b700-f0c5d339537d', 10, 'conditional', 'Nhum nướng mỡ hành（只有前面還沒吃到 Nhum）', 'Cable 回島後才有意義；stock / preparation / price gate 都過才用。', '區域備案｜人在那裡才看'),
('vinwonders-inside', NULL, 11, 'fallback', '園內就近、孩子能吃的熱食', '沒有鎖定必吃店；正常或孩子累時，園內解決比為吃飯硬接 Grand World 更合理。', NULL),
('wow-que-toi', '3c839f3f-a67c-81b4-ad7e-e4fc9cf00bef', 12, 'fallback', '沒有鎖定必點；選當下現做熱食正餐', '南島低摩擦 fallback，不升 Dish Carrier。', NULL),
('quoc-thien', '3d139f3f-a67c-81a8-a914-c8d697fbbe85', 13, 'verify', '熟食海鮮；先問秤重單價＋加工費', 'Safari → Gành Dầu daylight tail 的目前第一現場備案；不是 protocol-certified winner。', NULL),
('phuc-ngan', '3d139f3f-a67c-810c-8fd1-dfdb91857682', 14, 'verify', '熟海鮮；若有熟 Nhum / còi biên mai 可優先問', 'Gành Dầu 第二備案；目前證據不足以升 Carrier。', NULL),
('bep-nha-grandworld', '3d139f3f-a67c-815f-9387-c05d91356008', 15, 'verify', '目前沒有足夠證據指定必點；當越式正餐 fallback', '人在 Grand World 才用；不因為它存在就把 Grand World 接進行程。', NULL),
('com-nha-grandworld', '3d139f3f-a67c-8100-9e93-f61f460791e9', 16, 'verify', '家常飯菜；目前沒有 protocol-valid 必點', 'family-style 第二備案；review-integrity 仍有疑慮。', NULL),
('an-thoi-market', '3c839f3f-a67c-813b-b2a8-fef95d30e500', 17, 'market', '當下現做熟食／小吃，水果其次', '不是為市場硬排時間；剛好在 An Thới 才逛。', NULL),
('ganh-dau-market', '3c839f3f-a67c-8136-b9da-e6d87c8da6a5', 18, 'market', '現做、熱賣的熟食', '只在 Safari daylight tail 已經到 Gành Dầu 時順手看。', NULL)
ON CONFLICT (pool_key) DO NOTHING;

-- ============ C. content_update()：受控更新入口（唯一建議的主表寫入路徑） ============
-- 語義：
-- 1. 白名單表／欄位＋穩定 ID；不在名單 → 報錯，零副作用。
-- 2. JSON 型文字欄先驗證（非法 JSON → 報錯，零副作用）。
-- 3. 鎖列讀真實前值（FOR UPDATE）；目標不存在 → 報錯，零副作用。
-- 4. WHERE version=base 更新恰好一列，否則報錯回滾（版本衝突或目標消失）。
-- 5. 同交易寫 content_revisions（真實前值，不是模型記憶），回傳新版本。
-- 6. 還原＝用目前版本呼叫本函式、新值填目標舊值（新紀錄，不刪歷史）。
-- 7. p_actor 未知傳 NULL；輸入名稱只是來源聲明，不代表已驗證身分。
-- 8. 單一函式呼叫即單一交易；任何報錯整筆回滾，不會有「改了資料沒稽核」
--    或「寫了稽核沒改資料」的半完成狀態。
--
-- 實作注意（2026-09-22 實測）：Neon MCP 執行路徑下，動態 EXECUTE...INTO 之後
-- 的 FOUND 旗標恆為假（取值本身正確，靜態 SQL 的 FOUND 正常）。因此存在性與
-- 影響列數一律用「多選一常數欄＋IS NULL」判斷（v_hit 模式），不用 FOUND 或
-- GET DIAGNOSTICS ROW_COUNT。此寫法在標準 PostgreSQL 語義下同樣正確。

CREATE OR REPLACE FUNCTION content_update(
  p_table TEXT,
  p_id TEXT,
  p_field TEXT,
  p_new_value TEXT,
  p_base_version INTEGER,
  p_actor TEXT,
  p_source TEXT,
  p_reason TEXT
) RETURNS INTEGER
LANGUAGE plpgsql
AS $func$
DECLARE
  v_idcol TEXT;
  v_allowed TEXT[];
  v_json_fields TEXT[] := '{}';
  v_old TEXT;
  v_hit INTEGER;
  v_new_ver INTEGER;
BEGIN
  CASE p_table
    WHEN 'food_places' THEN
      v_idcol := 'notion_id';
      v_allowed := ARRAY['region','housing','cluster','time_slots','hours_text',
        'maps_query','price_text','cuisine','grade','op_status','op_conf',
        'atlas_state','data_conf','research_date','last_verified','evidence',
        'neg_warn','summary','kid_plan','dish_ids','evidence_as_of'];
      v_json_fields := ARRAY['time_slots','cuisine','dish_ids'];
    WHEN 'dishes' THEN
      v_idcol := 'notion_id';
      v_allowed := ARRAY['type','flavor_note','price_hint','time_slots',
        'order_note','evidence_as_of'];
      v_json_fields := ARRAY['time_slots'];
    WHEN 'dish_carriers' THEN
      v_idcol := 'notion_id';
      v_allowed := ARRAY['role','status','scope','food_verdict','food_conf',
        'avail_verdict','risk_exec','txn_risk','rationale','decision_set',
        'evidence_as_of','accepted_at'];
    WHEN 'points' THEN
      v_idcol := 'slug';
      v_allowed := ARRAY['area','interest','mandatory','trip_priority',
        'condition_gate','convenience','returnability','play_mode',
        'condition_note','kid_note','status','durable_note','evidence_as_of'];
    WHEN 'cards' THEN
      v_idcol := 'slug';
      v_allowed := ARRAY['route','gates','transport','notes','summary',
        'key_times','badges','stops','transport_out','transport_back',
        'kid_note','dining','cut_order','callout','evidence_as_of'];
      v_json_fields := ARRAY['gates','key_times','badges','stops',
        'transport_out','transport_back','dining','cut_order','callout'];
    WHEN 'bookings' THEN
      v_idcol := 'slug';
      v_allowed := ARRAY['kind','title','detail','amount','status',
        'evidence','evidence_as_of'];
    WHEN 'transport_options' THEN
      v_idcol := 'slug';
      v_allowed := ARRAY['direction','plan','station','status','priority',
        'note','evidence_as_of'];
    WHEN 'food_pool' THEN
      v_idcol := 'pool_key';
      v_allowed := ARRAY['pool_role','order_copy','desc_copy','divider','pool_rank'];
    ELSE
      RAISE EXCEPTION 'content_update: table not allowed (%)', p_table;
  END CASE;

  IF NOT (p_field = ANY (v_allowed)) THEN
    RAISE EXCEPTION 'content_update: field not allowed (%.%)', p_table, p_field;
  END IF;

  -- pool_rank 是整數欄：先驗整數格式，讀前值→轉型更新→同交易稽核。
  -- 存在／影響判斷用 v_hit（見 §C 前言），不用 FOUND／ROW_COUNT。
  IF p_table = 'food_pool' AND p_field = 'pool_rank' THEN
    IF p_new_value IS NULL OR p_new_value !~ '^-?[0-9]+$' THEN
      RAISE EXCEPTION 'content_update: pool_rank must be an integer (%)', p_new_value;
    END IF;
    EXECUTE 'SELECT pool_rank::text, 1 FROM public.food_pool WHERE pool_key = $1 FOR UPDATE'
      INTO v_old, v_hit USING p_id;
    IF v_hit IS NULL THEN
      RAISE EXCEPTION 'content_update: target not found (food_pool:%)', p_id;
    END IF;
    EXECUTE 'UPDATE public.food_pool SET pool_rank = $1::int, version = version + 1
             WHERE pool_key = $2 AND version = $3 RETURNING version, 1'
      INTO v_new_ver, v_hit USING p_new_value, p_id, p_base_version;
    IF v_hit IS NULL THEN
      RAISE EXCEPTION 'content_update: version conflict or missing (food_pool:% base=%)',
        p_id, p_base_version;
    END IF;
    INSERT INTO content_revisions
      (target_table, target_id, field_name, old_value, new_value,
       actor, source, reason, base_version, resulting_version)
    VALUES
      ('food_pool', p_id, 'pool_rank', v_old, p_new_value,
       p_actor, p_source, p_reason, p_base_version, v_new_ver);
    RETURN v_new_ver;
  END IF;

  IF p_field = ANY (v_json_fields) THEN
    PERFORM p_new_value::jsonb;
  END IF;

  EXECUTE format('SELECT %I, 1 FROM public.%I WHERE %I = $1 FOR UPDATE',
                 p_field, p_table, v_idcol)
    INTO v_old, v_hit USING p_id;
  IF v_hit IS NULL THEN
    RAISE EXCEPTION 'content_update: target not found (%:%)', p_table, p_id;
  END IF;

  EXECUTE format('UPDATE public.%I SET %I = $1, version = version + 1 WHERE %I = $2 AND version = $3 RETURNING version, 1',
                 p_table, p_field, v_idcol)
    INTO v_new_ver, v_hit USING p_new_value, p_id, p_base_version;
  IF v_hit IS NULL THEN
    RAISE EXCEPTION 'content_update: version conflict or missing (%:% base=%)',
      p_table, p_id, p_base_version;
  END IF;

  INSERT INTO content_revisions
    (target_table, target_id, field_name, old_value, new_value,
     actor, source, reason, base_version, resulting_version)
  VALUES
    (p_table, p_id, p_field, v_old, p_new_value,
     p_actor, p_source, p_reason, p_base_version, v_new_ver);

  RETURN v_new_ver;
END;
$func$;

-- ============ D. 最小欄級授權（只加 food_pool 公開 7 欄；其餘不動） ============
-- 現有 phq_web_ro 欄級 SELECT 經查正確（欄集合＝公開端點實際查詢欄），予以保留，
-- 不擴大成整表 SELECT。content_revisions 與所有 version 欄不授權。

GRANT SELECT (pool_key, notion_id, pool_rank, pool_role, order_copy, desc_copy, divider)
  ON food_pool TO phq_web_ro;
