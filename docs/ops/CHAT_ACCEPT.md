# ChatGPT 端最短實測（待 ChatGPT 驗證，2026-09-24）

> 開發端無法代跑 ChatGPT 實測。以下 prompt 一次貼給 ChatGPT（含 Project instructions
> 候選全文，見本輪交付 H 節），逐項核對預期結果。

## 前置

1. 使用者將 H 節 instructions 全文手動貼入 ChatGPT Project settings（本地更新不代表已安裝）。
2. 確認 Chat 可用能力：Notion connector（讀寫私人頁）、Neon connector（讀寫身分自查）。

## Prompt（一次性）

```text
你是富國島旅行助手（instructions 已貼入 Project settings）。請依序執行並回報：

1. 找到 Notion 入口「富國島 2026｜出發準備（私人）」：只讀取第 1 節標題結構，
   不修改、不輸出私人金額。回報：找到了／找不到／同名歧義。
2. 在 Neon 正式庫（holy-fog-65935796／production／neondb）搜尋：
   food_places 中 region 含 'Gành Dầu' 且 atlas_state='VERIFY' 的項目，
   回報筆數＋各筆 notion_id＋name（分頁讀取，不要整表）。
3. 讀指定項目詳情：food_pool pool_key='quoc-thien' 的 desc_copy、pool_role、
   version，以及它 JOIN 到的 food_places 名稱與 last_verified。
4. 先以唯讀確認你目前 connector 身分（effective_role／login_role）與
   content_update EXECUTE 權；若不是具寫入能力身分，第 5 步停止並如實回報。
5. 執行一項已授權、可核對的內容更新：food_pool(pool_key='ganh-dau-market')
   的 desc_copy，先讀版本，改為「<原值>（2026-09-24 Chat 驗收讀回測試）」，
   寫後讀回並核對 content_revisions 的 old_value＝原值；隨後用目前版本
   還原為原值，再讀回確認。回報兩次讀回值與版本號。
6. 最後用「做了什麼／證據／未做什麼／下一步」格式總結。
```

## 預期結果

| # | 預期 |
|---|---|
| 1 | 找到 1 頁（無歧義）；結構含待確認／付款期限、私人費用、行李、研究連結；未輸出私人金額 |
| 2 | 命中筆數由 Chat 回報（驗收端核對其 SQL 有分頁、非整表）；每筆有穩定 notion_id |
| 3 | `quoc-thien` desc_copy 以 DB 讀值為準；JOIN 到 Gành Dầu 店家＋last_verified；version 為整數 |
| 4 | 身分自查如實回報；非寫入身分則第 5 步停止（此即正確行為） |
| 5 | 更新讀回值含測試後綴、版本＋1；稽核 old_value＝原值；還原後值與原值一致、版本再＋1；任何衝突走重讀詢問 |
| 6 | 回報格式四段齊全；跨系統階段分清資料／顯示／備援 |

## 注意

- 第 5 步會在正式庫留下兩筆稽核（更新＋還原，值最終一致），屬可接受驗證痕跡。
- 若 Chat 身分已非 owner：第 5 步標「能力不足停止」即為通過，不繞限制。
- 驗收通過才進入舊站退役評估（見 `RETIREMENT.md`）。
