# 富國島六日手機比較稿（靜態快照）

設計版本：2026-09-27。`index.html` 僅供比較 **A 海岸路線簿** 的完整連續路線與 **B 下一站旅程牌** 的手動聚焦閱讀；兩者讀取同一份 `content.json`。預設 2026-10-13 纜車日。連結可帶 `?view=a|b&day=2026-10-13`；手動選擇站點只存在當前頁面，不會儲存、定位或改變正式行程。

資料整理依據為公開 `data/cards.json`、`data/pool.json`、`data/foods.json`、`data/bookings.json` 的指定欄位，以及 `docs/ops/ITINERARY_CONTENT_PREVIEW_BRIEF.md` 建議順序。公開卡片／預訂證據日 2026-09-20；餐廳核實日逐站列出（2026-08-26 至 2026-09-04），較舊資訊須出發前重查。草案安排、交通候車與時段均非已驗證車程或正式資料；已確認僅航班與 OnBird Morning／業者往返，實際接車窗口待通知。沒有訂單代碼、費用或私人準備資料。

本目錄自含 HTML/CSS/JS/JSON；不請求正式 API、無後台及登入。Google 地圖搜尋連結依公開地點文字安全編碼；離開此站時才送出搜尋。正式首頁不受影響；本目錄不應被當作 production itinerary、Neon fallback 或 Chat 寫入入口。
