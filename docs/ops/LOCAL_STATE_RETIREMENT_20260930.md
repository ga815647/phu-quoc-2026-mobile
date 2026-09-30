# 舊本機暫排退役與吃過乾淨重啟

日期：2026-09-30。需求與具體授權：[舊本機暫排與出發前吃過狀態退役](https://github.com/ga815647/phu-quoc-2026-mobile/issues/13)。基底 `471bf0cda5ba1a06e16e89bd72d2b1d4745b1942`；隔離分支 `fix/issue-13-local-state`。

本文件保存工程及本地驗證證據。正式發布 commit、Pages／Actions 結果與部署後實測，統一記在上述 issue 的 resolution comment；本地通過不能單獨當成已上線，也不代表使用者手機或目標 Chat 已親測。

## 修改與邊界

- 移除整個舊本機暫排區、日期下拉、清除暫排、遷移提示與相關 JavaScript；包括歷史 Today 的舊 slots 讀取。
- 不再讀、寫或遷移 `phq-v2-slots`／`phq-v3-slots`；舊裝置鍵不刪除。
- 吃過按鈕、篩選、進度、收合與手動重設保留，僅讀寫 `phq-v4-food-eaten`。沒有 v4 值時從 0 開始；不匯入任何 v2/v3 值（包括已搬進 v3 的測試殘留）。之後的新值重整後保留，重設只更新 v4，不是依日期／每次載入自動清零。
- 正式建置：`PYTHONUTF8=1 python3 tools/build_site.py --prod --itinerary-mode readonly`。`candidate` 相容模式同樣不保留 slots。
- 六日 Neon itinerary reader、五卡、餐飲、預訂、交通及備援維持原鏈路。沒有 Neon／Function／API／migration 變更、正式資料寫入或 JSON 重匯；既有公开 JSON 及 reader module 沒有差異。
- 同步必要產品契約、規則入口與退役說明，明列本次具體授權取代歷史「先保留舊手機暫排」要求，不擴張 Chat 資料權限或退役整個網站。
- Git 指示更新不自動安装到 ChatGPT Project settings；bootstrap 定位與權限邊界不變，Project 不用因本次修改重貼，也不宣稱 Chat 已讀新版。

正式輸出 build ID：`sha256:c72f4aeeabb2edfac6307a554ad6be950db69f433bcba7a678c4706abb88dc0e`。`index.html`／`data.html` 由生成器重建；卡片詳頁只有 build ID 更新。

## 測試與審查

| 檢查 | 證據 |
|---|---|
| TDD：舊裝置吃過殘留 | 新瀏覽測試先在修改前觀察到三種模式均為 `已吃 1 / 20`，而非預期 `0 / 20`；修改後通過 |
| 本機狀態 | 三種模式、v2-only／v2+v3 裝置；舊鍵存取攔截、原值不變、無暫排 UI、新鍵持久化、吃過篩選／重設、五卡、六日 reader 與手機溢出均通過 |
| Python 全部 `test_*.py` | `python3 -m unittest discover -s tools/verify -p 'test_*.py'`：57 tests，OK |
| 支援的 Node suite | `node --test functions/test-itinerary-response.mjs tools/verify/test_*.mjs`：51 tests，51 pass，0 fail／skip；PG18 rollback fixture 使用明確的本地測試環境 |
| 六日 reader 手機回歸 | `itinerary_reader_browser.mjs`：six days／Today／fallback／races／blocked storage／XSS／readonly／五卡／吃過／build／320、390、430px PASS |
| 實際正式輸出＋正式唯讀 API | 抽出 `data-smoke.yml` 的真實 JS，用本地正式輸出服務＋既有 production API 執行，`DATA_SMOKE=PASS`；不是僅測 mock |
| 既有旅程／交通檢查 | `journey_collapse_verify.py`、`transport_grouping_verify.py`：TOTAL FAIL 0 |
| 工作流／差異 | actionlint、`git diff --check` 通過；公開資料／Function／migration／reader 資產無差異 |
| 獨立唯讀審查 | 主修改與定向複核無剩餘阻擋；審查者未替代控制者的 runtime／發布驗證 |

測試環境用工作區相依與既有 user-space Chromium libraries（`LD_LIBRARY_PATH`），沒有安裝系統套件。初次完整探索因新 worktree 缺 `pg`／Playwright、Chromium libraries 未加入搜尋路徑而失敗；補齊環境後上述 suite 全通過。另有歷史 `functions/test-local-api.mjs` 需要外部 DSN／固定舊 Neon 筆數，初次 broad glob 在未提供 DSN 時失敗；不宣稱該歷史遠端支架通過，不為這項 UI 工程注入正式 credential 或修改其筆數。

## 驗站觀測修正（非旅遊資料修改）

- 新增 console 檢查後，原有未知卡 `slug=nope` 案例會刻意取得 404。已核對錯誤來源；只排除該精確 API URL 的預期 404 resource message，其他 console／page error 仍阻擋。
- 另一次舊 probe 在多次 reload 後回報 reader readiness 不符，沒有足夠追蹤證據判定該次根因，不能宣稱是產品 regression 或已證明的 timing 問題。
- 獨立審查辨識舊 probe 累積跨文件 response 的缺口；新增真瀏覽器測試先重現「舊回應能認證仍等待 API 的新文件」，再修正為 request／navigation owner 對應、有限等待目前文件 body、區分 request／body／HTTP／來源／revision 診斷。延遲舊回應＋reload＋新 body 無效測試通過；這是獨立證明的測試修補，不拿它冒充前次根因證明。
- 修正後完整本地正式輸出／live API smoke 通過，仍需以正式 Pages 版本與 CI 結果另外驗收。
