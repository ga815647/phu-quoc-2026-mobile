# 搬遷對照（2026-09-24 核對）

> 方法：筆數＋ID 全量比對。正式庫以 production 分支唯讀查詢為準；
> SQLite 為唯讀封存；JSON 為公開投影。正式庫零寫入。

## 筆數對照

| 表 | SQLite 封存 | Neon 正式 | JSON 備援 | 結論 |
|---|---|---|---|---|
| food_places／foods | 69 | 69 | 69 | 一致 |
| dishes | 18 | 18 | —（內嵌 carriers） | 一致 |
| dish_carriers | 7 | 7 | 7 | 一致 |
| points | 48 | 48 | 48 | 一致 |
| cards | 7 | 7 | 7 | 一致 |
| bookings | 8（全欄） | 8 | 8（公開 6 欄） | 一致（投影差異為設計） |
| transport_options | 7 | 7 | 7 | 一致 |
| food_pool | 無（pre-004） | 18 | 18 | 一致（004 新增，非漂移） |
| evidence_log | 0 | 0 | — | 一致 |
| content_revisions | — | 31（含部署 smoke＋測試分支歷史） | 不匯出（設計） | 正常 |

## ID 對照（全量）

- cards slug：`anthoi/cable/khem/onbird/safari/starfish/vinwonders` ——
  三處一致；`khem=RETIRED`、`anthoi=OPTIONAL` 語義保留。
- bookings slug：`cosy/insurance/island-transport/onbird/sim-viettel-6d2gb/tw-transport/vjl844/vjl845` —— 三處一致。
- food_pool rank 1–18 順序 —— Neon 與 JSON 一致。
- foods notion_id 抽查 2 筆（`bun-ken-ut-luom`、`ganh-dau-market`）——
  SQLite 與 Neon 同 ID 同名。

## 來源處置

| 來源 | 處置 |
|---|---|
| Neon 正式資料＋關聯 | 保留原處（SSOT），本輪零寫入 |
| 私人 Notion 頁（出發準備） | 保留原處；本輪只讀結構＋草稿隔離驗證，未動私人頁 |
| 舊 Notion 研究樹／Trip SSOT／Food Atlas | 封存參考，不搬、不刪、不重啟 ETL |
| 網站獨有文字（暫排下拉、交通分段、空狀態文案） | 留在 `tools/build_site.py` 生成邏輯，無需搬遷 |
| 裝置 localStorage（暫排、吃過） | 使用者已明確放棄保留（2026-09-26）；換裝置手動重設即可 |
| 舊 Function／CI／Pages | 保留，見 `RETIREMENT.md` |
| SQLite／父目錄 .db 備份 | 封存保留 |

## 缺漏與未處置（誠實列出，不計入「無缺漏」）

- 資料庫三源比對：無缺漏（8 表全量集合一致，見上）。
- **未處置、不計入無缺漏**：(1) 網站獨有文字（暫排下拉選項、交通分段說明、空狀態文案）留程式碼，未搬遷——屬生成邏輯，無需搬；(2) 裝置 localStorage（暫排、吃過）使用者已明確放棄保留（2026-09-26），換裝置手動重設；(3) 私人 Notion 頁保留原處（日常來源，不搬進 Neon）；(4) 舊研究樹封存。
- 測試分支既有漂移（`food_pool.ganh-dau-market` 早於本輪即為 `T18` 殘留），
  本輪驗證後已還原為該分支原值；正式庫不受影響。
