# Coastal Reader Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把使用者已選A海岸路線簿整合到資料驅動reader；旅遊查核由Chat接手。

**Architecture:** 延用既有validateEnvelope→loadItinerary→renderItinerary／mountItinerary。A預覽只提供視覺參考，所有旅行內容来自既有公開envelope，不引入第二份旅行資料。未知值可顯示，不能讓缺少研究阻塞版型工程。

**Tech Stack:** Python生成器、原生JS modules、CSS、Node24／Playwright。

**Spec:** `../../ops/ITINERARY_CONTENT_PREVIEW_BRIEF.md`（A已接受）；`../specs/2026-09-27-itinerary-chat-ci-design.md`；`../../ops/CHAT_RESEARCH_HANDOFF.md`。

## Global Constraints

- 只改tools/itinerary-reader.mjs、tools/site.css、tools/build_site.py及相關tools/verify測試；不手改根三頁。
- 保持data-content-revision／source／schema-version、day／segment／transfer hooks及公開envelope格式。
- legacy預設與舊手機編輯暫留，不清localStorage。
- 不改006／生產資料／ACL；不將preview/redesign/content.json用作正式fallback。
- 生產部署與初始化按既有runbook獨立處理。

## Review Focus

1. 未知time window/duration不得變NaN或虛構時刻；Task1瀏覽測試。
2. 同payload改餐廳文字後畫面及Today跟隨，不殘留預覽硬碼；Task1。
3. 320px長段落／來源／地址不溢出，日期及地圖>=44px；Task1。
4. source/revision仍存在、備援明示非最新、刷新失敗保留過期提示；既有reader/browser案例與Task1。
5. legacy界面不被A樣式污染，舊eaten／slots保留；既有browser與journey/transport回歸。

## Task 1: A視覺接入現有renderer

**Files:** Modify `tools/itinerary-reader.mjs`, `tools/site.css`, `tools/build_site.py`; tests `tools/verify/itinerary_reader_browser.mjs`, `tools/verify/test_itinerary_reader.mjs`。

**Interfaces:** 消費`renderItinerary(root,loaded)`的既有envelope；保持`mountItinerary({root,todayRoot,refreshButton,apiUrl,fallbackUrl,fetchImpl,now})`。輸出原有hooks的連續時間線，活動／餐飲／交通視覺有別；條件與核實依據保留可讀，備案維持details。

- [ ] 先在現有browser fixture case新增A特徵與未知值斷言（延用原腳本已開啟page）：
  ```js
  assert.equal(await page.locator('[data-itinerary] .coastal-route').count(), 6);
  assert.equal(await page.locator('[data-itinerary]').innerText().then(t=>t.includes('NaN')), false);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth), false);
  ```
- [ ] 跑`node tools/verify/itinerary_reader_browser.mjs`，確認新增coastal-route斷言因尚無A class失敗，而非環境缺依賴。
- [ ] renderer的主線容器使用`el('div','timeline coastal-route')`，segment添加局部kind class；依A已核准配色與連續線實作CSS，所有selector以`[data-itinerary]`起頭。時間label與段落不由preview文字產生；必要generator class僅包裹候選reader，legacy DOM不重構。
- [ ] 同一個六日有效fixture更換具名餐廳／note並重新route API回應，斷言新值可見、舊值消失；另一份未知time保持顯示未核實。既有payload驗證不可放寬。
- [ ] 320／390／430px確認日期切換、地圖、備案、刷新／備援、Today、本機狀態；保留截圖供A視覺比對。
- [ ] 跑`node --test tools/verify/test_itinerary_reader.mjs tools/verify/test_site_check_browser.mjs`、`node tools/verify/itinerary_reader_browser.mjs`、`node tools/verify/itinerary_e2e_candidate.mjs`及兩個既有journey/transport Python scripts；限本機／合成API。
- [ ] 提交明列上述source/tests路徑，獨立review規格／品質；記錄候選輸出，不宣稱正式部署完成。

## 自查與執行界線

上述工作是A視覺落到已核准資料契約的窄幅整合；不需要新的旅遊研究。公開預覽的A選擇已確認；本接線細節計畫提供使用者審閱後沿用既定Subagent-driven方法。OnBird核心初始化的真實窗口仍交接為資料前置，不偷偷改保護規則。
