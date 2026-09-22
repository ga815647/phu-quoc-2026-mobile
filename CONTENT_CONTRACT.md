# 內容維護契約（Chat 資料操作契約 v1）

> 操作契約，不是新的協作模式或 project instructions。
> 不修改 `AGENTS.md`、`chatgpt-instructions.md`、部署或權限規則。
> 現行 `chatgpt-instructions.md` 仍要求 Chat 只讀；本文件描述**技術上可維護的範圍與方式**，
> 實際寫入需另行授權（見 §7）。未授權前，Chat 不得要求繞過指示，也不得宣稱寫入已啟用。

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

## 4. 更新與讀回（範例，測試 branch 驗證過）

```sql
-- 讀取（含版本）
SELECT notion_id, summary, version FROM food_places WHERE notion_id='...';
-- 交易一致性：資料＋稽核同一交易
BEGIN;
UPDATE food_places SET summary='...', version=version+1
 WHERE notion_id='...' AND version=1;
INSERT INTO content_revisions
 (target_table,target_id,field_name,old_value,new_value,
  actor,source,reason,base_version,resulting_version)
VALUES
 ('food_places','...','summary','舊','新',
  'chat:<operator or NULL>','chat-mcp','<reason>',1,2);
COMMIT;
-- 讀回確認
SELECT notion_id, summary, version FROM food_places WHERE notion_id='...';
SELECT target_table,target_id,field_name,old_value,new_value,
       base_version,resulting_version,actor,source,changed_at
  FROM content_revisions WHERE target_id='...' ORDER BY id;
```

版本衝突（不可靜默 last-write-wins）：
`UPDATE ... WHERE id='...' AND version=<base>` 影響 0 列即為衝突。
必須重新讀取、比對、由人決策合併，不得重試覆寫。

`evidence_log` 追加：
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

## 6. 哪些會出現在公開站

公開讀取（`phqreadonly`，欄位白名單）＋靜態 JSON 備援（`data/*.json`，`public-v1`）：

- `cards`：公開全欄（不含 `version`）；`khem/anthoi` 不作主卡。
- `foods`：公開研究欄；`bookings` 僅 6 欄（無 `detail/evidence`）。
- `points` 無 `condition_note`；`transport` 公開 8 欄。
- 每筆保留 `last_verified/evidence_as_of`；頁面區分**核實日期／資料取得時間／備援快照日期**。
- 公開站不新增聯絡方式、訂單碼、付款資訊、私人筆記原文。
  費用保留幣別，不跨幣別加總。

網站生效鏈路（既有授權機制）：
`Neon 寫入 → tools/export_json.py（預設 neon）→ data/*.json →
tools/build_site.py --prod → index.html+data.html+card.html → commit/push →
GitHub Pages`。MCP 改 DB **不會**自動觸發 GitHub；備援 JSON 需手動匯出＋部署。
自動化若需新增 secret／外部權限，列為阻礙，不虛構已設定。

快取：Function `Cache-Control: public, max-age=300`；頁面每次載入重新取得
（`cache: no-store`＋8s timeout），失敗／超時／無效 JSON／缺欄位時降級為靜態備援
並明確標示，不假裝即時。靜態降級 ≠ 完全離線可用；不新增完整 PWA。

## 7. 權限現狀（不要假裝有做到）

- 技術上已支援：公開 `GET` 唯讀（固定端點表、顯式欄位、錯誤固定字串、
  CORS allowlist、5 分鐘快取）；`content_revisions` 增量表＋`version` 樂觀併發
  已在測試 branch 驗證；`evidence_log` 追加語義已定義。
- 現行規則仍禁止：`chatgpt-instructions.md` 明文要求 Chat 只讀、
  旅途中僅追加 `evidence_log`；未經授權不得寫入主表。
- 需要另行授權：任何 production 寫入（含 `003_content_revisions.sql` 上正式庫）、
  跨裝置同步（需登入；匿名公開寫入、硬編碼密鑰、藏網址代替授權一律不可）、
  自動匯出＋部署的新 secret／外部權限。
- Neon MCP 連線為流程限制，非真正的 DB 權限隔離：MCP 使用具寫入能力的連線，
  `instruction 禁止 ≠ GRANT/REVOKE`；`phq_web_ro` 在正式庫尚無表級 GRANT
 （`information_schema` 查無授權，但 Function 可讀，推斷其 DSN 實為 owner，
  已列為待修——不得在前端放 DSN／密碼／token，CORS 不是身分驗證）。
  不得擅改 MCP 設定或削減其他工具權限來「完成」隔離。

localStorage（v3，已實作安全遷移）：
Chat 寫入 Neon 後，網站重整經 Function／備援讀到（需再匯出＋部署才更新備援）。
舊 `phq-v2-*` 不默默覆蓋新版，不直接清除；無時間／版本依據時不猜新舊；
新版 `phq-v3-*` 缺失才從舊版複製，舊鍵保留為備份並顯示保留訊息。
網站按鈕目前只寫本地，無 Neon 寫回；無私有身分驗證前不做雙向同步，
不宣稱本機狀態等於跨裝置同步。
