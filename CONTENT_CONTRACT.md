# 內容維護契約（Chat 資料操作契約 v2）

> 操作契約，不是新的協作模式或 project instructions。
> 不修改 `AGENTS.md`、`chatgpt-instructions.md`、部署或權限規則。
> v1 的「UPDATE 後無條件 INSERT 稽核」範例已作廢，改用 §4 `content_update()`。
> 正式可用狀態見 §7「授權 ≠ 部署」；測試分支驗證通過不等於正式可用。

SSOT：Neon Postgres `holy-fog-65935796` / `production (br-silent-haze-b3xw64tm)` / `neondb`。
SQLite `data/phuquoc.db` 為遷移封存，Notion 為歷史封存，不作為現況依據。

## 1. 穩定 ID（不用模糊店名作主要關聯）

- `food_places.notion_id`（TEXT PK）、`dishes.notion_id`、`dish_carriers.notion_id`
- `points.slug`、`cards.slug`、`bookings.slug`、`transport_options.slug`
- `evidence_log.id`（append-only）、`content_revisions.id`（稽核，公開 API 不暴露）

所有更新必須帶穩定 ID；店名僅作顯示與輔助搜尋。

## 2. Chat 可維護欄位（白名單）

型別均為 TEXT，除註明外；`version: INTEGER` 用於樂觀併發。

**food_places**：`region, housing, cluster, time_slots(JSON array TEXT), hours_text,
maps_query, price_text, cuisine(JSON array TEXT), grade(S/A/B/C/D/NULL),
op_status, op_conf, atlas_state(ACTIVE/VERIFY/DEACTIVATED), data_conf,
research_date, last_verified, evidence, neg_warn, summary, kid_plan,
dish_ids(JSON array TEXT), evidence_as_of, version`

**dishes**：`type, flavor_note, price_hint, time_slots, order_note, evidence_as_of, version`

**dish_carriers**：`role(PRIMARY/BACKUP), status, scope, food_verdict, food_conf,
avail_verdict, risk_exec, txn_risk, rationale, decision_set, evidence_as_of,
accepted_at, version`（`dish_id/place_id` 關聯變更需附決策集，不單改一名）

**points**：`area, interest, mandatory, trip_priority, condition_gate,
convenience, returnability, play_mode, kid_note, status(ACTIVE/OPTIONAL/RETIRED),
durable_note, evidence_as_of, version`（`condition_note` 不公開，寫入仍需保留語義）

**cards**（五卡 `onbird/vinwonders/cable/starfish/safari`；`anthoi=OPTIONAL`，
`khem=RETIRED` 不渲染為卡）：`route, gates(JSON array TEXT), transport,
notes, summary, key_times(JSON array TEXT), badges(JSON array),
stops(JSON array), transport_out(JSON array), transport_back(JSON array),
kid_note, dining(JSON array), cut_order(JSON array), callout(JSON/null),
evidence_as_of, version`

**bookings**（`Confirmed=已確認`，`Open=追蹤清單非已訂妥`）：`kind, title,
amount(保留原始幣別字串，不做跨幣別加總), status, evidence_as_of, version`
（`detail/evidence` 可能含訂單碼／聯絡方式，**不得**寫入公開投影，
公開讀取僅 `slug,kind,title,amount,status,evidence_as_of`）

**transport_options**：`direction, plan, station, status, priority, note,
evidence_as_of, version`

**evidence_log**（旅途中唯一建議的追加路徑）：只 `INSERT (ref_type, ref_id, note)`，
不改主表。`ref_type ∈ {food,point,card,booking}`。

**不可維護**：`content_revisions`（系統寫入，公開 API 無端點）、任何
`detail/evidence` 含私人資訊欄位的公開暴露、跨幣別金額加總、
`phq_web_ro` 權限、Function 環境與 secrets、前端硬編碼金鑰。

限制：
- 五卡語義、`Confirmed/Open` 語義、已確認 OnBird 與重要安排不得因 UI 改版更動。
- `khem` 不重新渲染為第六張卡；`free/recovery` 是狀態不是卡。
- 超過 30 天或缺 `last_verified/evidence_as_of` 者，保留「出發前重查」語義。
- 不重跑封存 Notion ETL 覆寫 Neon。

## 3. 語義（硬限制）

- 更改暫排 ≠ 更改或取消訂單。
- 「今天沒開」先記當日觀察（`evidence_log`），不直接標永久停業
 （`op_status/atlas_state` 需另行核實）。
- 修改時間 ≠ 核實時間；不用今天冒充 `last_verified`。
- 研究結果不得自動覆蓋已確認預訂或旅行硬限制（回程、住宿、孩子限制）。

## 4. 受控更新入口：`content_update()`（唯一建議的主表寫入路徑）

> 舊版「UPDATE 後無條件 INSERT 稽核」範例已作廢（它允許半完成狀態）。
> 主表寫入一律呼叫本函式；直接 UPDATE 主表僅限 OpenCode 測試支架，
> 不得作為 Chat 操作範例。

函式（`tools/migrate_neon/004_controlled_update.sql` §C）語義，原子執行：
1. 白名單表／欄位＋穩定 ID；不在名單 → 報錯，零副作用。
   ID 欄：`food_places/dishes/dish_carriers→notion_id`；
   `points/cards/bookings/transport_options→slug`；`food_pool→pool_key`。
2. JSON 型文字欄先驗格式（非法 → 報錯，零副作用）。
3. 鎖列讀**真實前值**（`FOR UPDATE`），目標不存在 → 報錯，零副作用。
4. `WHERE version=base` 更新；影響不是恰好一列 → 報錯回滾
   （版本衝突或目標消失），**不產生成功稽核**。
5. 同交易寫 `content_revisions`（真實前值，非模型記憶），回傳新版本。
6. 還原＝用**目前版本**再呼叫一次、新值填目標舊值（新紀錄，不刪歷史）。
7. `p_actor` 未知傳 NULL；輸入名稱只是來源聲明，不代表已驗證身分。
8. 管制是**程序性**的（函式內原子保證），不是 DB 權限隔離；
   MCP 以具寫入能力身分執行，`instruction 禁止 ≠ GRANT/REVOKE`。

可執行範例（測試分支實測通過，見 §7）：

```sql
-- 讀取（含版本）
SELECT notion_id, desc_copy, version FROM food_pool WHERE pool_key='ganh-dau-market';
-- 成功：回傳新版本（此例 2），恰好一筆＋一稽核
SELECT content_update('food_pool','ganh-dau-market','desc_copy','新文案',
  1, NULL, 'chat-mcp', '現場核實後更新推薦') AS new_version;
-- 讀回＋稽核（old_value 必須是 DB 真實前值）
SELECT desc_copy, version FROM food_pool WHERE pool_key='ganh-dau-market';
SELECT target_table,target_id,field_name,old_value,new_value,
  base_version,resulting_version,actor,source,changed_at
  FROM content_revisions WHERE target_id='ganh-dau-market' ORDER BY id;
-- 過期版本：報錯 version conflict，不改資料、不寫稽核；必須重讀＋詢問，不重試覆寫
SELECT content_update('food_pool','ganh-dau-market','desc_copy','舊值重送',
  1, NULL, 'chat-mcp', 'stale-retry');
-- 還原（用目前版本 2，把值寫回舊文案 → 產生版本 3 新紀錄）
SELECT content_update('food_pool','ganh-dau-market','desc_copy','<舊文案>',
  2, NULL, 'chat-mcp', '還原');
```

非法輸入一律報錯且零副作用（實測）：不存在 ID、非白名單表
（`evidence_log` 等）、非白名單欄（`version`、關聯鍵等）、非法 JSON、
`pool_rank` 非整數。`bookings.detail/evidence` 可維護但**永不進公開投影**。

`evidence_log` 追加（獨立路徑，不要求主表 version，不冒充主表稽核）：
```sql
INSERT INTO evidence_log (ref_type, ref_id, note)
VALUES ('food','<notion_id>','2026-10-12 現場觀察：...（僅當日觀察，非永久結論）');
```

## 5. 修改紀錄與還原

- 每次資料變更必須同交易寫入 `content_revisions`（對象、穩定 ID、
  修改前後值、時間、來源／操作者）。操作者無法辨識就記 NULL，不捏造。
- 還原必須產生**新**紀錄（`old=現值, new=目標舊值, version+1`），不能 UPDATE 回舊值
  而不記錄，更不能 DELETE 稽核列。
- 過期版本覆寫必須用 `WHERE version=base` 擋掉，衝突時回報並保留雙方版本。
- 稽核表不得經公開 API 暴露（`phqreadonly` 無 `/api/content_revisions`，
  `GET` 以外 405，未知路徑 404；已實測）。

## 6. 欄位對照：內容項目 → DB／穩定 ID → API → 畫面 → 備援

圖例：●動態（改 DB → API → 畫面，不必重建） ○靜態（備援快照，需匯出＋部署）
△寫死（程式／文案固定） ✕未支援。

| 內容項目 | DB 欄位／穩定 ID | API | 畫面 | 備援 | 狀態 |
|---|---|---|---|---|---|
| 五卡時間線／交通／餐飲／取捨／成行條件 | `cards.*`／`slug` | `/api/cards[?slug=]` | 行程卡片＋`card.html?slug=` | `data/cards.json` | ● |
| 卡片摘要／badge／核實日期 | `cards.summary,evidence_as_of` 等 | 同上 | 同上 | 同上 | ● |
| 美食地區／狀態／驗證／地圖 | `food_places.region,atlas_state,last_verified,maps_query...`／`notion_id` | `/api/foods` | 美食卡 badge＋篩選屬性 | `snapshot.foods` | ●（回填鍵＝`notion_id`，改名不斷鏈；`name` 僅遺產 fallback） |
| 精選池排序／角色／點餐／推薦文案 | `food_pool.pool_rank,pool_role,order_copy,desc_copy,divider`／`pool_key`（關聯 `notion_id`） | `/api/foods`（JOIN） | 美食池渲染＋即時改文＋按 rank 重排 | `snapshot.pool`＋`data/pool.json` | ●（單一來源；69 家不自動進池；`notion_id` NULL 者純靜態） |
| 預訂（已確認／待辦） | `bookings.kind,title,amount,status,evidence_as_of`／`slug` | `/api/bookings` | 旅程訂單區＋**今天預訂即時行** | `data/bookings.json` | ●（`detail/evidence` 可維護、永不公開） |
| 交通備案 | `transport_options.*`／`slug` | `/api/transport` | 旅程交通區 | `snapshot.transport` | ● |
| 暫排（10/12–14） | 無專用結構（見 §8） | — | 行程暫排下拉（本機） | — | △本機（`phq-v3-slots`） |
| 偏好 | 無專用結構 | — | — | — | ✕（不得塞別欄冒充） |
| 吃過／去過 | 無專用結構 | — | 美食吃過按鈕（本機） | — | △本機（`phq-v3-food-eaten`） |
| 私人筆記 | 無專用結構 | — | 公開站空狀態（不顯示） | — | ✕（`evidence_log` 僅收當日觀察，非私人筆記庫） |
| 實際費用 | `bookings.amount`（公開欄！） | `/api/bookings` | 旅程金額（保留幣別） | 同左 | ●但注意：寫進去即公開；私人實際支出尚無私有結構（見 §8） |
| 稽核 `content_revisions` | 系統寫入 | 無端點（404） | 不顯示 | 不匯出 | 系統專用 |
| 版本欄 `version` | 各主表＋`food_pool` | 不暴露 | 不顯示 | 不匯出 | 併發控制專用 |

生效鏈路（兩條，分開回報）：
- **API 即時鏈**：`content_update() → Function（5 分鐘快取）→ 畫面回填`
  （池文案／排序、狀態、預訂皆此鏈；頁面 `cache:no-store`＋8s 超時，
  失敗／超時／無效 JSON／缺欄位降級備援並明示）。
- **備援發布鏈**：`export_json.py（預設 neon）→ data/*.json（含 pool）→
  commit/push → Pages`。MCP 改 DB **不會**自動觸發；備援缺 `pool` 時
  池區顯示空狀態，不編造。
- 卡片／池靜態 HTML 是 build 期快照；API 成功時以即時覆蓋並重排，
  失敗時保留快照＋備援標示。

## 7. 權限現狀與驗證（不要假裝有做到）

已查證（2026-09-22，正式庫唯讀查詢＋行為測試）：
- `content_revisions` 正式庫**不存在**；7 主表皆無 `version`；
  `food_pool` 不存在（以上皆為本輪 004 待部署項目）。
- `phq_web_ro` 是**欄級 SELECT**（`role_column_grants` 71 欄，
  `role_table_grants` 0 列）：`bookings` 6 欄（無 `detail/evidence`）、
  `cards` 18 欄、`food_places` 27 欄（無 `kid_plan/migration/updated_at`）、
  `points` 12 欄、`transport` 8 欄。舊「information_schema 查無表級 GRANT，
  推斷 Function DSN 是 owner」結論**作廢**——欄級授權本來就查不到表級，
  證據不足，不得據此換 DSN／重設密碼／補整表 SELECT。
- Function 行為與上述授權一致：`/api/foods` 欄集合＝授權集合
  （無 `version/kid_plan`）；`POST → 405`；未知路徑與
  `/api/content_revisions → 404`；錯誤固定字串不洩 SQL／DSN。
  這是**行為一致性證據**，不是身分證明：`current_user/session_user`
  屬服務端環境，未經授權不得輸出 secret，也未新增診斷端點，
  故身分僅標「與 `phq_web_ro` 一致」，不宣稱已確認。
- 測試分支 `content_update()` 全電池通過：成功恰好一筆＋真實前值、
  過期版本／不存在 ID／非法表欄／非法 JSON／非整數 rank 零副作用、
  還原新紀錄、`bookings` 跨表可用（見 §4）。
  實作注意：此 MCP 路徑下動態 `EXECUTE...INTO` 後 `FOUND` 恆假，
  函式改用 `RETURNING version, 1`＋`IS NULL` 判斷（標準語義同樣正確）。
- **授權 ≠ 部署**：「使用者已授權內容維護」是流程授權；
  正式庫缺表／缺欄、Function 未重部署前，功能即「尚待部署」。
  Chat 寫入前必須先讀本契約確認正式支援確實存在（測試分支驗證不算）。

現行規則仍禁止：`chatgpt-instructions.md` 的旅途中主表凍結
（只追加 `evidence_log`）、私人欄位不公開、批量覆寫／硬刪除／改動已確認
安排先請使用者確認——新規與舊規則衝突處以**較嚴**者為準，不自行放寬。

需要另行授權：任何 production 寫入（含 004 上正式庫＋Function 重部署）、
跨裝置同步（需登入；匿名公開寫入、硬編碼密鑰、藏網址代替授權一律不可）、
自動匯出＋部署的新 secret／外部權限。
Neon MCP 連線為流程限制，非真正的 DB 權限隔離；
不得擅改 MCP 設定或削減其他工具權限來「完成」隔離。

localStorage（v3，已實作安全遷移）：
Chat 寫入 Neon 後，網站重整經 Function／備援讀到（備援需再匯出＋部署）。
舊 `phq-v2-*` 不默默覆蓋新版，不直接清除；無時間／版本依據時不猜新舊；
新版 `phq-v3-*` 缺失才從舊版複製，舊鍵保留為備份並顯示保留訊息。
網站按鈕目前只寫本地，無 Neon 寫回；無私有身分驗證前不做雙向同步，
不宣稱本機狀態等於跨裝置同步。

## 8. 個人紀錄現狀（先釐清，不假裝已完成）

| 項目 | DB 結構 | Chat 可操作 | 網站可讀 | 按鈕可寫回 | 是否公開 |
|---|---|---|---|---|---|
| 暫排 slots | 無 | 否 | 本機是 | 本機是 | 否 |
| 偏好 | 無 | 否 | 否 | 否 | —（不得塞別欄冒充） |
| 吃過／去過 | 無 | 否 | 本機是 | 本機是 | 否 |
| 私人筆記 | 無（`evidence_log` 只收當日觀察） | 僅觀察追加 | 空狀態 | 否 | 否 |
| 實際費用 | 僅 `bookings.amount`（**公開欄**） | §4 函式 | 是 | 經 Chat | **是**（寫入即公開，私人支出勿放） |

結論：未登入前保留本機功能並明示「只存這支手機」。
個人狀態不為省登入而公開，不塞進 `bookings/evidence_log` 冒充完整功能。

最小同步方案（推薦，需核准；不阻塞本輪內容維護）：
`user_state(user_id PK, slots JSON, eaten JSON, notes_private TEXT, updated_at)`
＋既有身分提供者登入（每裝置一次 OAuth 點擊）＋登入後才出現的讀寫端點；
資料僅本人可見，不做多使用者管理、不做完整後台、不進公開投影。
自動化（匯出／部署／Function 重部署）若需新增 credentials／排程／外部授權，
先列最小需求，不自行建立、不聲稱已自動化。
