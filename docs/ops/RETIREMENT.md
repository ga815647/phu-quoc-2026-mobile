# 舊站退役與資料回復（2026-09-24 現況）

> 原則：新入口及資料驗收通過前，保留舊站作回復入口。
> 本輪新入口驗收未全過（Chat 實測待驗），故**不退役**，只記錄處置。

## 各入口處置

| 項目 | 現況 | 處置 |
|---|---|---|
| GitHub Pages 正式站 | 200 正常（74,015B） | 保留，仍為日常主要入口＋回復入口 |
| Neon Function `phqreadonly` deployment 5 | 200；POST→405、`content_revisions`→404 | 保留，Chat 日常讀取仍可用；不刪除 |
| CI（data-smoke 等） | push 路徑觸發＋手動，無排程 | 保留，不新增 secret／排程 |
| `v2.html` | 未接受候選（2026-09-20 起未動） | 保留原處，不推廣、不刪除 |
| `MIGRATION_MANIFEST.json`／`SITE_SYNC_MANIFEST.json`／`PARITY_CHECK.md` | 帶日期證據 | 保留為歷史證據，不作現況依據 |
| 裝置 localStorage（`phq-v3-*`＋`phq-v2-*`備份） | 裝置端，伺服器拿不到 | 一次性匯出：使用者在舊裝置開啟正式站→行程暫排與吃過紀錄可見即已保留；換裝置需手動重設。**不宣稱已搬遷**；使用者確認不需要保留可記為明確放棄（目前未放棄） |
| SQLite `data/phuquoc.db` | 遷移凍結封存 | 保留；備份另見下 |
| 測試分支 `verify-migrate-20260921` | 驗證用，有既有漂移（`ganh-dau-market.desc_copy='T18'`） | 保留作隔離驗證環境，不合併回正式 |

## 備份位置

- `data/phuquoc.db`（repo 內封存）＋ repo 父目錄
  `phuquoc-backup-20260921.db`、`phuquoc-preprod-20260921.db`
- Neon 正式庫可由擁有者經 Console／分支快照回復（本輪未操作，如需快照另行授權）

## 回復方式

1. 網站異常 → 靜態 `data/*.json` 備援自動承接（頁面內建降級＋標示）。
2. Neon 誤寫 → `content_revisions` 查真實前值，用目前版本再呼叫
   `content_update()` 還原（新紀錄，不刪歷史），見契約 §4。
3. 整庫回復 → 以備份 DB 或 Neon 快照重建（需使用者授權操作）。
4. 私人 Notion 誤改 → Notion 頁面歷史版本回復（使用者在 UI 操作）。

## 退役條件（未達成前不執行）

- Chat 三項實測全過（入口定位、搜尋＋詳情、授權更新讀回）。
- 搬遷對照無缺漏（見 `docs/ops/MIGRATION_MAP.md`）。
- 使用者明確授權退役設定。以最小可逆方式標記退役；公開頁不導向私人 Notion URL；
  不刪 repo、舊歷史或 Chat 使用中的 Function。
