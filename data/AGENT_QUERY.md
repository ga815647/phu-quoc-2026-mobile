# 資料查詢手冊（Agent 用，Neon 切換 2026-09-22）

主庫：Neon Postgres（project `phu-quoc-2026`／`holy-fog-65935796`，
branch `production`／`br-silent-haze-b3xw64tm`，`neondb`）。
`data/phuquoc.db`（SQLite）為遷移前封存，不再是默認寫入來源。
既有 Notion 店家庫、Trip SSOT、研究與交接頁維持歷史封存；私人付款、現金、行李改在「富國島 2026｜出發準備（私人）」維護，不進 Neon／公開投影、不雙向同步。只在需要時以已登入的 connector 按標題查該私人頁，不將私人 URL 或金額寫入 repo。
快照：`data/foods.json / points.json / cards.json / bookings.json / snapshot.json`（公開投影＋離線備援，GitHub Pages 吃這些）。

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
- `Confirmed` 是訂單確認，不代表已付款；`bookings.amount` 公開，禁止存私人支出。私人付款／預算查 Notion，不靠此欄推定。
- 旅行中 Neon 只 `INSERT INTO evidence_log(ref_type, ref_id, note)`，不改主表；私人 Notion 清單仍可依使用者要求更新。
- 不重跑封存 Notion ETL 覆寫 Neon。網站資料更新後依授權匯出 Neon 備援；純 UI 修改不需寫 DB 或重匯 JSON。
