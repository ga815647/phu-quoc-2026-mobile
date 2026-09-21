# 資料查詢手冊（Agent 用，Neon 切換 2026-09-22）

主庫：Neon Postgres（project `phu-quoc-2026`／`holy-fog-65935796`，
branch `production`／`br-silent-haze-b3xw64tm`，`neondb`）。
`data/phuquoc.db`（SQLite）為遷移前封存，不再是默認寫入來源。
Notion 已凍結為封存。快照：`data/foods.json / points.json / cards.json / bookings.json / snapshot.json`（公開投影＋離線備援，GitHub Pages 吃這些）。

## 4 種問法 → SQL

### 1. 當下吃什麼（區域＋時段）
```sql
SELECT name, grade, atlas_state, last_verified, maps_query FROM food_places
WHERE region IN ('Dương Đông','Long Beach') AND time_slots LIKE '%早餐%'
AND op_status='營業中' AND atlas_state IN ('ACTIVE','VERIFY') ORDER BY grade LIMIT 5;
```

### 2. 可執行 Carrier（ACTIVE＋ACCEPTED 才推 Primary）
```sql
SELECT place, carrier, role, evidence_as_of FROM v_executable_foods;
```

### 3. 單點能去嗎
```sql
SELECT name, interest, status, condition_gate, durable_note FROM points WHERE slug='sao-beach';
SELECT name, interest, status FROM v_points_query WHERE area='SOUTH';
```

### 4. 模組＋訂單缺口
```sql
SELECT slug, name, status, gates FROM v_cards_gates;
SELECT kind, title, status FROM bookings WHERE status != 'Confirmed';
```

## 規則
- 5 卡為準：onbird/vinwonders/cable/starfish/safari；anthoi=OPTIONAL satellite；khem=RETIRED。
- 回答必帶 `last_verified / evidence_as_of`；超過 30 天標「出發前重查」。
- 旅行中只 `INSERT INTO evidence_log(ref_type, ref_id, note)`，不改主表。
- 重跑 ETL：`python3 tools/etl_points.py`（points）＋ Notion query（food/carrier）後 `python3 tools/export_json.py`。
