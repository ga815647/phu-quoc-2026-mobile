# Six-day Itinerary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 Chat 原子修改六天安排，網站讀取一致的公开內容，CI 將當次驗站結果回傳 GitHub。

**Architecture:** 三個依序交付、可獨立測試的子計畫共用已核准規格。A 提供資料交易與公開投影；B 消費投影並產生穩定 DOM；C 以 GitHub 請求核對 API／DOM。正式內容、視覺與部署入口各有明確前置條件。

**Tech Stack:** PostgreSQL 18／PLpgSQL、Python 3／psycopg2、Neon Functions Node.js 24／pg、原生 ES modules、Playwright 1.55.0、GitHub Actions。

**Spec:** `../specs/2026-09-27-itinerary-chat-ci-design.md`（2026-09-27 使用者核准）。

## Global Constraints

- 根目錄是 `app/`；本計畫所有相對路徑均由此起算。
- `2026-10-10` 至 `2026-10-15`；timezone=`Asia/Ho_Chi_Minh`；固定 itinerary ID=`phuquoc-2026`。
- 旅遊內容唯一來源為 Neon；私人準備留 Notion；JSON 為公開備援。
- 五卡 `onbird/vinwonders/cable/starfish/safari` 保留；An Thoi 可選、Khem 不作卡片。
- 已確認航班／住宿／10/11 OnBird 不被普通更新更動。
- 約 21:00 結束活動、回住宿另列；一般餐廳隨路線，explicit 衝突先問。
- API GET/OPTIONS only；private version／audit／requests 不公開。
- 每日上限 32 段、8 個 alternatives；每備案最多 32 段；請求最多 128 KiB。
- API 8 秒超時，整包備援；CI 最多 6 分鐘、20 秒最多一次觀察。
- `index.html/data.html/card.html` 均生成，不手改。
- 不修改 003–005 歷史 migration；新的 006 先隔離驗證。
- 替代鏈路驗收前保留現有手機編輯與 localStorage；測試不寫正式資料。
- 使用者已選 Subagent-driven；書面計畫審閱完成後才開始實作。

## Review Focus

1. 兩個並行 Chat 修改／同 request 重送：只允許一次提交；A2 雙連線測試。
2. pool 的 notion_id 在驗證途中改變：追蹤完整依賴閉包，不能混讀；A1/A2 測試。
3. 快速連按刷新，新回應先到：舊回應不能覆蓋新畫面；B2 測試。
4. 跨午夜、未知車程、手機儲存被禁：顯示仍可讀且不偽造總耗時；B2 測試。
5. CI 同時發布不同 request，或驗站後網站又更新：結果不互蓋、只聲明觀察當時；C2/C3 測試。

## 子計畫與依賴

| 順序 | 文件 | 可獨立驗收的輸出 |
|---|---|---|
| A | [資料模型與受控更新](2026-09-27-itinerary-data.md) | 隔離 PG 的 schema／交易／ACL／公開指紋 |
| B | [網站讀取與備援](2026-09-27-itinerary-reader.md) | 新 API、匯出與本地手機候選頁；保留原操作 |
| C | [CI 驗站與交付](2026-09-27-itinerary-ci.md) | 純請求驗證、瀏覽器檢查、結果分支發布與操作文件 |

B 的 schema／fixtures 依 A1；B1 API 依 A3；C1 可在 A/B 實作時獨立進行，但 C2 須等 B2 DOM 契約。主代理依序整合；不讓兩個 worker 同時改 shared migration、規則文件或生成器。

## 執行準備與派工規則

- [ ] 使用 `using-git-worktrees` 建隔離工程分支；先檢查現有未提交文件，保留其差異並把必要的核准規格／計畫帶入 worktree。不得 `git reset --hard` 或 `git add .` 收掉不相關變更。
- [ ] 每 task 派新 implementer，附完整 task、核准 spec、AGENTS、scope、確切可改路徑及「production 零寫入」。完成後依 subagent-driven-development 做規格及品質審查。
- [ ] A 的資料測試僅使用明確指定的隔離 PG／Neon 分支 DSN；測試 runner 要求 `ITINERARY_TEST_ALLOW_WRITE=1` 與 `ITINERARY_TEST_DSN`，拒絕含 `br-silent-haze-b3xw64tm` 的 DSN；該 guard 是防呆，不冒稱足以辨識所有正式庫別名。操作者另核對 branch ID。
- [ ] 確認 Node 24、Python 3、psycopg2、pg 與 Playwright 1.55.0。既有 `functions/package-lock.json` 使用 `npm ci --prefix functions`；瀏覽器依賴放候選／測試環境，不在 repo 根目錄留下未追蹤 package 檔。
- [ ] 初始測試與每 task 測試只跑受影響範圍；最後整合再跑既有 UI／五卡／狀態持久化回歸。

## 共用線上契約（A/B/C 不得各自命名）

```json
{
  "data": {
    "schema_version": 1,
    "itinerary": {"id":"phuquoc-2026","start_date":"2026-10-10","end_date":"2026-10-15","timezone":"Asia/Ho_Chi_Minh"},
    "days": [],
    "refs": {"cards":[],"foods":[],"pool":[],"points":[],"bases":[],"bookings":[],"transport":[]}
  },
  "meta": {"schema_version":1,"content_revision":"phq1:<64 lowercase hex>","source":"neon-prod","environment":"production","fetched_at":"ISO8601"}
}
```

上面 `days:[]` 是形狀示意；有效 payload 必須有六日，不當作可用 fixture。day=`{id,date,day_kind,main_card_slug,plan}`；plan 完全依規格 §5。備援另有 `meta.exported_at`，載入器自身將來源標成 fallback，不冒用匯出時的 live source。

DOM：容器 `[data-itinerary]` 帶 `data-content-revision/data-source/data-schema-version`；日 `[data-itinerary-day="phuquoc-2026:YYYY-MM-DD"]` 帶 `data-main-card`；段 `[data-segment-id]` 帶 `data-ref-type/data-ref-id`；交通另帶 `data-from-ref/data-to-ref/data-mode`（ref 序列化為 `type:id`）。`html[data-site-build]` 是 build ID。

## 發布前置與終點

程式可使用**明示測試用** fixtures 完成 A/B/C；正式六日內容不可從 fixtures 推定。正式初始化／首頁升版之前必須具備：

1. 彈性日順序、實際每日時間線、餐廳／估時來源的內容決策。
2. 視覺稿與可遠端瀏覽預覽的發布範圍確認。
3. 隔離環境 migration／ACL／交易測試證據及具體 production 套用範圍確認。
4. Chat 專用入口的真實授權修改→CI→手機驗收；這是新功能驗收，不重跑既有完整 connector 能力盤點。

C3 交付明確操作 runbook；缺上述輸入時完成工程候選與測試，標記發布等待哪一項，不用假內容填入正式庫。

## 計畫自查

- [x] 規格 §1–6 → A1/A2；§7 → A1/A3；§8 → B1/B2；§9–10 → C1/C2/C3。
- [x] 規格 §11 → A3/C3；§12 → 各 task 測試＋C3 端到端；§13 → C3；§14 → 上述內容／視覺發布前置。
- [x] 共用函式、payload、DOM、request/result 命名固定；每個子計畫列明輸入／輸出。
- [x] 使用者於 2026-09-27 回覆「可以」，核准三份子計畫；保留既定 Subagent-driven 執行方法。
