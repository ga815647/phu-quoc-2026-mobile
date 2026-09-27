# Issue tracker: GitHub

使用者於 2026-09-26 選定 GitHub Issues。Repository：`ga815647/phu-quoc-2026-mobile`。
Issue 操作用 `gh` CLI，明確傳入 `--repo ga815647/phu-quoc-2026-mobile`；API 操作使用該 repo 的完整 path。

## Current map

[富國島體驗重整｜從六天預設行程到可開發規格](https://github.com/ga815647/phu-quoc-2026-mobile/issues/1)

地圖與各子決策的狀態，以 GitHub 當前資料為準；本文件不另存一份開放議題清單。
既有本地討論紀錄是歷史背景；新 Wayfinder 決策以子議題的 resolution comment 為唯一答案來源。

## Wayfinding operations

- **Map**：標記 `wayfinder:map` 的 issue。正文保留 Destination／Notes／Decisions so far／Not yet specified／Out of scope。
- **Child**：先建立帶 `wayfinder:grilling`、`wayfinder:research`、`wayfinder:prototype` 或 `wayfinder:task` 的 issue，再透過 GitHub 原生 sub-issue 關係掛入地圖。
- **Parent link**：`POST repos/ga815647/phu-quoc-2026-mobile/issues/<map-number>/sub_issues`，JSON `sub_issue_id` 使用子議題的數值 database ID，不是 issue number 或 node_id。
- **Dependencies**：`POST repos/ga815647/phu-quoc-2026-mobile/issues/<blocked-number>/dependencies/blocked_by`，JSON `issue_id` 使用阻塞者的 database ID。先建完議題再接關係。原生子議題與依賴在此 repo 已於 2026-09-26 實際建立成功。
- **List children**：`gh api --paginate repos/ga815647/phu-quoc-2026-mobile/issues/1/sub_issues`。以地圖子議題顺序為準，不從全 repo 的任意 open issue 挑選。
- **Frontier**：open、assignees 為空，且 `issue_dependencies_summary.blocked_by` 為 0 的子議題。若摘要缺失，查 `GET .../issues/<number>/dependencies/blocked_by` 並確認阻塞者狀態，不把缺欄位當成沒有依賴。
- **Claim**：開始處理前，`gh issue edit <number> --repo ga815647/phu-quoc-2026-mobile --add-assignee @me`。已被認領的議題由其他會話跳過。
- **Read**：`gh issue view <number> --repo ga815647/phu-quoc-2026-mobile --comments`；需要 labels、assignees、依賴時另外讀 JSON/API，不僅看題名。
- **Resolve**：先加 resolution comment（決策、理由與來源指標），再關閉議題；最後讀回最新地圖正文，在 Decisions so far 加一行名稱連結與結論摘要，避免覆蓋並行會話的更新。
- **Research**：獨立 subagent 先載入 research；報告存於獨立 `research/<name>` 分支，以固定 commit 檔案 URL 作 context pointer。事實未知可作研究結果，但不能替使用者解決 HITL 取捨。
- **Publish**：技能說 publish to tracker 時建立／更新 GitHub Issue，不把本地檔存在當作已發布。Issue 授權不等於網站部署或正式資料寫入授權。

## Operating rules

- 向使用者引用議題時用「名稱＋連結」，不只說編號。
- 一個會話至多解一個非研究決策；建圖會話不順便完成 HITL 決策。獨立研究可平行。
- 新問題能精確表述就建票並接依賴；尚無法表述者留在 fog。超出終點的項目進 Out of scope。
- 公開 issue 不放私人頁 URL、私人金額、訂單碼、聯絡方式或憑證。
- PRs as a request surface: **no**。此輪僅設定 Wayfinder；一般 triage 流程與 labels 未另行啟用。
