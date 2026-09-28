# Task 1 — A 海岸路線簿 reader 接線報告

狀態：**本地工程候選完成；未發布、未初始化正式六日內容、未做 Chat 真實讀回。** 實作 commit `42bd589`。

## 交付

- 現有公開 envelope 原樣驗證、讀取及備援；六個 day panel 各有連續 `coastal-route` 主線，活動／餐飲／交通以節點和底色區分，備案維持折疊。時間、來源、核實、條件及導航連結仍取自 envelope；未知時間顯示「時間待定／時間未核實／待估」，不推算時刻。
- 來源和匯出日期可見，版本與最後讀取時間可展開；`data-content-revision`、`data-source`、`data-schema-version` 及 day/segment/transfer hooks 保留。選定日期在重新整理資料及同頁重新載入後保留於 sessionStorage，不動既有 slots/eaten localStorage。
- `tools/build_site.py` 只調整候選 reader 的無資料載入狀態與 aria 名稱；legacy 預設及舊手機操作保留。樣式 selector 全以 `[data-itinerary]` 起頭，不改舊版全域 `.step`。
- 瀏覽測試先證實缺少 coastal route 造成 `0 !== 6` 的預期失敗；並修正原測試在未傳 `--site` 時錯選 `process.argv[0]` 的路徑錯誤。其後測試涵蓋動態 API 更換店名／備註／今日主卡、未知時刻、證據展開、刷新／日期選取、備案、地圖、備援、失敗、legacy 狀態及觸控寬度。

## 驗證（本地合成 API／本地 PG18）

| 命令 | 結果 |
|---|---|
| `node --test tools/verify/test_itinerary_reader.mjs tools/verify/test_site_check_browser.mjs` | 26/26 PASS |
| `node --test tools/verify/test_*.mjs` | 40/40 PASS |
| `node tools/verify/itinerary_reader_browser.mjs` | PASS；320／390／430px 無水平溢出、地圖與日期目標 ≥44px |
| `node tools/verify/itinerary_e2e_candidate.mjs` | LOCAL FIXTURE PASS（PG18 rollback→public view/export→candidate→Chromium→fake GitHub） |
| `python3 tools/verify/journey_collapse_verify.py` | TOTAL FAIL 0 |
| `python3 tools/verify/transport_grouping_verify.py` | TOTAL FAIL 0 |
| `git diff --check` | PASS |

候選輸出：`/tmp/opencode/phq-itinerary-candidate/data-candidate.html`（`--api-base http://localhost:8000/mock-api --out-dir /tmp/opencode/phq-itinerary-candidate --itinerary-mode candidate`）。截圖：`/tmp/opencode/phq-coastal-reader-320.png`、`phq-coastal-reader-390.png`、`phq-coastal-reader-430.png`；截圖測試才使用 `/tmp/opencode/NotoSansCJKtc-Regular.otf`，字體缺失時跳過截圖，不影響 browser 斷言。正式站字體仍是系統堆疊。

## 未完成／交接關切

- 當前圖像採合成 fixture（含英文占位標籤）；真實六日內容、OnBird 已核定窗口與未核實餐廳／交通研究留給 Chat 和正式資料初始化流程，不以 preview JSON 代入。正式 006／ACL／Function、fallback publication、preview／正式部署、Chat 新鏈讀回與手機實機驗收各自待授權及驗證。
- sessionStorage 僅保存瀏覽分頁的閱讀日期；它不是旅遊行程編輯，也不改舊 `phq-v3-slots`／吃過資料。日期切換仍是閱讀切換，不會將時間先後推為已完成。
- 報告與 commit 均只限本任務允許路徑；工作區原有 `docs/ops/REDESIGN_SCOPE.md` 等其他變更未觸碰。
