# 候選版 UI 驗收結果（headless Chromium，390px viewport）

- 時間：2026-09-21 UTC；環境：VPS 本機 Playwright＋Chromium headless，
  候選站經 `python3 -m http.server`（127.0.0.1）提供，API 指向測試 branch Function。
- 腳本：`tools/verify/candidate_ui_accept.py`（路由 abort 模擬單區失敗、
  response fixture 覆寫驗 foods 刷新；未寫入任何 Neon 業務資料）。
- 驗收名稱為「headless Chromium，390px viewport」；
  未宣稱手機真機通過，既有 CI（data-smoke.yml）本輪未跑。

| # | 項目 | 結果 |
|---|------|------|
| 1 | 三區 API 成功（三條 api 條＋時間） | PASS（5 卡） |
| 2 | 單區失敗：只擋 bookings | PASS（訂單備援＋快照留用，卡／食保持 api） |
| 3 | 單區失敗：只擋 cards | PASS（卡片備援＋5 卡，訂／食保持 api） |
| 4 | 單區失敗：只擋 foods | PASS（美食 fallback＋SSR，卡／訂保持 api） |
| 5 | 全部備援（site-fail） | PASS（三區備援條，卡 5 張、訂單 8 筆、美食 SSR） |
| 6 | foods 動態刷新（fixture 覆寫） | PASS（region＋徽章跟著變） |
| 7 | 五卡詳情＋返回 | PASS（5 slug＋返回連結不出站） |
| 8 | 八筆訂單 CONFIRMED／OPEN | PASS |
| 9 | localStorage 重整持久 | PASS（吃過＋暫排，驗後已清） |
| 10 | 390px 無橫向溢出 | PASS（overflow 0px） |

驗收中修復的 2 個真 bug（均已重驗通過）：
1. cards 備援引用了主 then 區塊內的 `renderCard`（ReferenceError，
   備援 JSON 可讀卻顯示雙失敗）→ 提為 IIFE 頂層共用函式。
2. foods 刷新误删 region span（選擇器太貪，還會誤寫驗證日期）→
   SSR region span 加 `food-place` class 精確區分；正式 SSR 保持原樣零洩漏。

未驗證：手機真機手感、整站離線（無 service worker，不宣稱關網重開可用）。
