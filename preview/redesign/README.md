# 富國島六日手機比較稿（靜態快照）

設計版本：2026-09-27。`index.html` 僅供比較 **A 海岸路線簿** 的完整連續路線與 **B 下一站旅程牌** 的手動聚焦閱讀；兩者讀取同一份 `content.json`。預設 2026-10-13 纜車日。連結可帶 `?view=a|b&day=2026-10-13`；手動選擇站點只存在當前頁面，不會儲存、定位或改變正式行程。

資料整理依據為公開 `data/cards.json`、`data/pool.json`、`data/foods.json`、`data/bookings.json` 的指定欄位，以及 `docs/ops/ITINERARY_CONTENT_PREVIEW_BRIEF.md` 建議順序。公開卡片／預訂證據日 2026-09-20；餐廳核實日逐站列出（2026-08-26 至 2026-09-04），較舊資訊須出發前重查。草案安排、交通候車與時段均非已驗證車程或正式資料；已確認僅航班與 OnBird Morning／業者往返，實際接車窗口待通知。沒有訂單代碼、費用或私人準備資料。

本目錄自含 HTML/CSS/JS/JSON；不請求正式 API、無後台及登入。Google 地圖搜尋連結依公開地點文字安全編碼；離開此站時才送出搜尋。正式首頁不受影響；本目錄不應被當作 production itinerary、Neon fallback 或 Chat 寫入入口。
# 2026-09-27 內容查核補記

A已被使用者選為視覺方向；六日草案仍非正式Neon安排。新增DeepSea／Giraffe午餐、TheWaterfront第一晚候選與纜車公告時段，皆在畫面標明資訊性質。自由安排09:30–10:00／12:00左右／15:30為建議，不是已訂時刻；Cosy精確路由與叫車等待仍未知。

公開來源（查閱2026-09-27）：
- [Sun World公告入口](https://sunworld.vn/en/hon-thom)：「from July20」官方圖片標Apply from20.07.2026，纜車09–11:30／13:30–17，Aquatopia09:45–16:45；17:00不是保證最後排隊時間。
- [VinWonders園內行程與餐飲](https://vinwonders.com/en/wonderpedia/news/complete-guide-to-the-vinwonders-phu-quoc-itinerary/)
- [園方餐飲優惠](https://vinwonders.com/en/offers/phu-quoc-meal-combos-deep-sea/)
- [Safari主頁](https://vinwonders.com/en/vinpearl-safari-phu-quoc/)：Giraffe10:30–15:30與優惠頁09–16有差異，保留衝突說明。
- [The Waterfront營業與地址](https://thewaterfrontphuquoc.com/reservation)、[菜單](https://thewaterfrontphuquoc.com/menu)：11–22、66G TrầnHưngĐạo；未訂位、未核實Cosy步行距離。
