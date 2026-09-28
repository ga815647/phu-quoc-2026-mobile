# 富國島六天行程：Chat 修改、網站讀取與 CI 驗站規格

日期：2026-09-27。狀態：**使用者已於同日核准書面規格；進入實作計畫，尚未實作**。

本規格承接已確認的每日安排模型與角色分工；不是執行 migration、修改正式資料或部署的指令。使用者審閱後才進入 writing-plans；實作採 subagent-driven-development。

## 1. 成果與範圍

使用者在 Chat 說「把某天改成纜車」，Chat 能讀目前行程、組成一致的候選安排、一次保存受影響日期、讀回稽核並請 CI 驗正式站。網站顯示六天具體主線、建議餐飲、交通估時與條件式備案；Chat 分別回報資料已儲存與網站已驗證。

本規格處理資料模型、受控更新、公開讀取／備援、前端資料契約與驗站橋接。完整六天實際內容與視覺稿由既有時間線／視覺決策票收斂；本規格不捏造待查車程、營業時間或已確認预訂，也不自行發布未接受的 UI。

### 已確認的產品約束

- 2026-10-10 至 10-15，六天都有預設安排；預設不代表已訂位。
- 已確認的航班、住宿、10/11 OnBird 保持原意。10/12–14 主活動預設選 VinWonders、纜車、Safari；具體順序由時間線決策決定。海星保留五卡之一，作替換候選且須滿足其接送條件。
- Grab 優先，但不把偏遠返程當作保證；An Thoi 為纜車日可跳過的順路加點，不占獨立一天。
- 一般餐廳建議隨新路線調整；使用者刻意指定且不合路線的餐廳，先問一次。
- 以孩子為主，約 21:00 是晚間活動結束目標，回住宿時間另列；不是必須硬撐。
- Chat 是行程修改入口。網站閱讀／備案／導航；既有手机編輯與資料在替代鏈路驗收前保留。
- 新每日安排及餐飲／交通指派旅中可經受控入口修改；現有研究主表與已確認訂單仍遵守既有凍結／授權限制。
- 私人準備留既有 Notion，不新增登入、跨裝置個人狀態同步或私人記帳網站。

## 2. 角色與能力證據

| 角色 | 職責 |
|---|---|
| Chat | 固定 Git commit 讀規則；Neon 讀取／授權更新／讀回；提交驗站請求並讀 GitHub 結果 |
| OpenCode | 實作資料結構、受控入口、接線、測試與核准發布；維護契約及兩端規則入口 |
| 網站 | 讀公開行程、顯示資料來源與內容識別、提供導航；不寫 Neon |
| CI | 唯讀檢查正式 API／手機畫面；寫驗收報告到結果分支，不改 Neon 或部署 |

Chat 正式唯讀、非正式分支受控更新／還原／衝突拒絕及 GitHub branch/file 寫入，已有使用者提供的 2026-09-27 證據。它們不證明新功能存在。Chat 直接 HTTP／瀏覽器不可用不阻塞此設計；runtime 由 CI／手機驗收。來源詳見 `docs/ops/CHAT_ACCEPT.md`。

## 3. 選型與模組邊界

採「專用行程主檔＋每日安排＋一次受控修改」；不將六天內容塞入既有 cards 文字欄，也不做通用行程編輯平台。

有序日程段落用每日 `plan JSONB`，穩定日期／主活動等關聯使用實體欄位；JSON 中的參照由受控入口驗證。這比完整六天單列方便局部修改，也比將每個提示拆成多表更符合本案規模。

| 單元 | 輸入／輸出 | 職責 |
|---|---|---|
| 私有編輯讀取 | itinerary ID → private version、六日安排及來源版本 | 供 Chat 判斷修改；不經公開 API |
| 受控變更 | base version、expected content identity、受影響日 plans、request ID → receipt | 檢查完整性與併發、原子修改、稽核與去重 |
| 公開投影 | itinerary ID → public payload＋content_revision | 統一 API／匯出／CI 可見資料，排除私有控制欄 |
| 網站載入器 | 即時投影或備援 → 同一 view model | 顯示、來源標識、更新結果，不另维护旅遊事實 |
| CI 橋接 | 經驗證的請求 JSON → GitHub 報告＋截圖 | 確認當次版本和語義已在正式站呈現 |

## 4. 新資料結構

初期僅一趟固定旅程，不新增多使用者／權限管理系統。

### 4.1 `itineraries`

- `id TEXT PRIMARY KEY`：固定 `phuquoc-2026`。
- `start_date DATE`、`end_date DATE`：10/10–10/15。
- `timezone TEXT`：`Asia/Ho_Chi_Minh`；當地行程時刻依此解讀，出發地交通另附其原時區。
- `version INTEGER`、`updated_at TIMESTAMPTZ`：私有併發控制，不進公開投影。
- `locked_constraints JSONB`：初始化時從經確認安排建立的保護條件，不由普通行程更新修改。包括指定日期／活動／預訂關聯；只限制受保護的核心，不把整個 OnBird 日的早餐／晚餐全部鎖死。

### 4.2 `itinerary_days`

- `id TEXT PRIMARY KEY`：固定 `phuquoc-2026:YYYY-MM-DD`，不因換活動更換 ID。
- `itinerary_id` 外鍵；`date DATE`；UNIQUE(itinerary_id,date)。固定六個日期，不透過日常更新新增／刪除天數。
- `day_kind TEXT`：arrival／activity／light／departure。
- `main_card_slug TEXT NULL`：引用既有 cards.slug。activity 必須有主活動；arrival／light／departure 可為 NULL。
- `plan JSONB`：下節 schema；不複製店家名稱／地址／研究全文或卡片整份內容。
- `version INTEGER`、`updated_at TIMESTAMPTZ`：私有；被更新日各遞增一次。

### 4.3 `itinerary_requests`

私有交易／重送紀錄：`(itinerary_id,request_id UUID)` 唯一；canonical request hash、base_version、resulting_version、changed_day_ids、result_content_revision、created_at。
只在變更交易成功時寫入；同 request ID／同 payload 回傳原 receipt，不重複修改；同 ID／不同 payload 拒絕。
receipt 表示該次成功，不保證之後沒有新修改；重送後仍須讀最新投影判斷是否已被較新版本取代。

### 4.4 稽核沿用 `content_revisions`

每個被修改日寫一筆：target_table=`itinerary_days`、target_id=穩定 day ID、field_name=`day_plan`。
old_value/new_value 是完整日公用編輯結構（day_kind/main_card_slug/plan）的 canonical JSON 字串；base/resulting_version 使用該日的私有版本。source/reason 與可知 actor 依既有語義，未知 actor 為 NULL。
request ID 放入可明確關聯的稽核 reason 結構或新增專用 nullable request_id 欄；本規格固定採**新增 nullable request_id UUID 欄及索引**，舊資料保持 NULL，既有 content_update 呼叫不受影響。
requests 與 audit 均不公開、不匯出。

## 5. 每日 plan schema v1

根欄位固定為 `schema_version:1`、`segments:[]`、`alternatives:[]`、`public_note`（可省略）。拒絕未知 key、重複 segment ID、過長輸入與任意私人／執行指令欄位。文字欄是公开行程文案；欄位白名單不代表能自動判斷所有私人文字，Chat 仍須遵守內容隱私契約。

### 段落

- `id`：日內穩定短 ID；有序陣列就是順序。
- `kind`：activity／meal／transfer／rest／optional。
- `label`：行程段標題，例如早餐、返回住宿；不是另一份店家名稱來源。
- `time`：`start_window`（當地 HH:mm 的 min/max 或 NULL）、`day_offset`（0 或 1，跨午夜時為 1）、`timezone`（預設行程時區；出發地可明列 IANA 時區）、`duration_minutes`（min/max 或 NULL）、`kind`（scheduled／estimated／planned／unknown）、`source_refs`、`evidence_as_of`。缺實據的車程留 NULL／unknown，不填 0 或假精準值；planned 僅代表安排預留，不能冒充已查車程。
- `ref`：`{type,id}` 或 NULL。type 僅 card／food／pool／point／base；card/food/pool/point 必須存在於對應來源。base 只能是既有住宿／交通基地的核准鍵，不接任意 URL。
- `selection`：derived／explicit。meal 必填；其他段可省略。explicit 表示使用者刻意選定，不是「已預訂」。
- `transfer`：僅 transfer 段有，含 `from_ref`、`to_ref`、`mode`（operator_pickup／grab／taxi／bus／charter／walk／cable）、`wait_minutes` 區間或 NULL、`buffer_minutes` 非負整數、`condition_refs`。行車、等車、緩衝分開顯示；未知項存在時不顯示貌似完整的確定總耗時。
- `condition_refs`：指向本日 alternatives 的條件 ID，或已核准的卡片成行條件鍵。optional 段不加入主線必須完成清單。
- `note`：僅此段特有的公開安排說明。

單日上限 32 段、8 個 alternatives；單次候選請求上限 128 KiB。這是輸入上限，不是鼓勵排滿。

### 條件式備案

每筆包含穩定 `id`、trigger_kind（weather／fatigue／late／unavailable／manual）、`trigger_text`、`action`（skip_optional／use_alternative／return_or_rest）、`target_segment_ids`、`replacement_segments`。replacement_segments 沿用上述段落 schema，use_alternative 時必填非空，其餘 action 為空陣列；不嵌套 alternatives。替代段 ID 在日內也須唯一，所有參照、來源及 explicit 選擇一併驗證；每個備案最多 32 段。
備案是可閱讀的決策規則，不是網站自行判斷天氣／疲勞後改 DB 的引擎。Starfish 必須保留包車／回接等門檻，Grab 偏好不能覆蓋它。

餐廳用 food stable ID，或 pool ID（包括合法 NULL 店家例外 vinwonders-inside）；不从 dining.place 的自由文字猜 ID。未核實／條件式候選保留原標示，不因被安排就自動升成已確認。

## 6. 受控修改 `itinerary_update`

新入口獨立於既有單欄 `content_update`：

`itinerary_update(itinerary_id, base_version, expected_content_revision, request_id, changes JSONB, explicit_selection_decisions JSONB, actor, source, reason)`

`changes` 是 1–6 個受影響日期的完整候選日結構，不允許裸 SQL、JSON path 任意寫入或觸及來源表。交換兩日是同一請求更新兩日；只改一天不重送其他五天。

### 交易程序

1. 驗證請求形狀與大小；canonicalize/hash 完整有語義參數。`actor/source` 是聲明，不是授權憑證。
2. 鎖 itinerary 列；查成功 requests。相同 ID／payload 回原 receipt，不比對舊 base 而誤判重送；相同 ID 不同 payload 拒絕。
3. 比較 private base_version；不符即回 VERSION_CONFLICT、零寫入。
4. 收集目前全行程及候選新增引用的 cards／foods／pool／points／公開 bookings／transport 依賴，按固定表名及 stable ID 順序取得共享 row lock，防止驗證與投影間被 content_update 改動。新引用或刪除列需要重新確認；維持單一行程鎖順序避免互鎖。
5. 在鎖定後的一致讀取中計算目前公開 content_revision，與 expected 比較；來源事實已變而 itinerary.version 未變時，仍回 SOURCE_CHANGED，Chat 重讀，不盲寫。
6. 驗證日期範圍、參照、schema、核心 locked_constraints、主活動與相關段落關聯，以及明確餐廳選擇的更動聲明。規則能驗引用／結構／鎖定，不能憑空證明路線地理合理或營業時段；這部分由 Chat 用來源證據組合及 CI 顯示驗收。
7. 不合新路線的 explicit 餐廳：Chat 先取得使用者答覆，請求附 `explicit_selection_decisions`（對應 day/segment 與原選擇、決定）。伺服器核對與原日一致；此為操作聲明，不冒稱密碼學的使用者授權證明。
8. 原子更新各受影響日與日版本，寫每日日誌；itinerary.version 遞增一次，計算新的公開投影指紋並保存 request receipt。同交易提交，任何失敗全回滾。
9. 回傳 request_id、resulting_version、changed_day_ids、content_revision；Chat 另讀回日計畫與稽核。還原以目前版本再次提交目標日計畫，是新 request／新稽核。

所有新寫入函式採 SECURITY INVOKER，PUBLIC 與 phq_web_ro 無 EXECUTE；僅既有核准的內容維護身分可執行。網站 GET 不新增寫回權限。此是程序契約與資料權限的組合，不聲稱具 owner 能力的 connector 技術上無法繞過函式。

## 7. 公開投影與內容識別

### 單一公開表示

以固定、顯式白名單的投影產生 `schema_version`、itinerary 公開識別／日期／時區、六日 plans、被引用來源的公開顯示資料。按日期／ID 排序，剔除 private version、requests、audit、locked_constraints 及既有非公開欄。

投影只帶日程及其引用／備案所需資料；整份無關餐廳目錄變更不應使行程內容識別變動。被引用的店家營業狀態、卡片指派與交通顯示資料改變則必須反映。

新增 owner-controlled 固定公開 view，使用 explicit columns／JSON allowlist；phq_web_ro 只獲該 view 的 payload／content_revision SELECT，無新增原始新表、private version 或 audit 存取。若為組裝使用輔助函式，僅公開唯讀投影函式可授必要 EXECUTE，不能連帶開放 update 函式。view／函式的 owner 與有效 ACL 要在隔離環境實測。

### `content_revision`

採公開 payload 的 deterministic SHA-256 指紋（prefix `phq1:`）。由 Postgres 單一一致查詢計算：固定排序的 JSONB payload 轉文字／UTF-8 bytes 再 hash；精確 canonicalization 由同一資料庫投影實作負責，前端和 Chat 不自行重算。
指紋不含 fetched_at、匯出時間、內部 version／audit。相同公開內容可有相同指紋，即使內部曾修改再還原；request_id 與私有版本用來區分操作，指紋只證明顯示內容相同。

選指紋而不另造必須被每張來源表手動遞增的公開計數器，可避免餐廳另更新卻忘記更新行程版號。公開指紋不是權限 token，不能授權寫入。

## 8. API、備援與前端契約

- 新增固定 GET `/api/itinerary`，只讀本案 itinerary；不接受任意表名／SQL。response 沿用 `{data,meta}`，meta 增 `content_revision` 與 `schema_version`；source/environment/fetched_at 仍各自保留。
- 新 endpoint 成功與失敗均 `Cache-Control:no-store`，避免日常修改被原有 300 秒政策延遲；舊端點快取策略不在此輪一併改造。
- 公開 view／payload 與 hash 必須來自同一 statement snapshot；不能分兩個查詢取 payload 與 revision。
- `export_json.py` 從同一公開表示產生 `data/itinerary.json`，含相同 content_revision，匯出時間另記。它是離線備援，不使用 SQLite 當來源。
- API 成功且 schema 有效才整包替換六天 view model；失敗／8秒超時／未知 schema 時整包降級備援，顯示備援與匯出日期。禁止三天新資料混三天舊資料卻只顯示一個「最新」標記。
- CI 最新修改驗收要求 live/production 與預期內容識別；fallback 能顯示不算本次 live 更新通過，另列 FALLBACK。
- 每次載入／使用者刷新取一次，不新增常駐背景輪詢。保留「重新整理資料」操作與資料版本／來源的可讀摘要。
- 頁面提供穩定 DOM hooks：day ID、main card slug、meal ref、transfer ref、content revision、data source、schema version；不依賴餐廳顯示名作測試識別。
- 生成器產生公開 `site-version.json` 及同值 DOM build ID。build ID 是前端來源／資產的 deterministic digest，與 itinerary content_revision 不同；不把生成前的 git HEAD 冒充已發布 commit。

本輪只定義資料接線與必要狀態，不在此定死視覺布局。首頁／日詳情的接受稿需通過原型決策，再套入此 view model。

## 9. Chat 操作與回報

1. 固定 Git commit 讀契約／操作說明，Neon 讀行程私有版本、公開內容指紋與受影響日。
2. 明確授權的一般日程修改直接組成候選；不對每個欄位重複請示。只有 explicit 餐廳衝突、已確認安排或未知必要條件才追問。
3. 呼叫一次 itinerary_update；失敗保留原安排，回報原因；版本／來源衝突先重讀，不自動覆蓋。
4. 成功後讀回與稽核，先回報「資料已儲存」；以相同 request_id 和回傳公開指紋產生驗站請求。
5. 查 GitHub 結果；沒有結果是 pending，不假裝背景通知一定會到。Chat 不持續佔用無限輪詢，使用者追問時可續查同一 request。
6. 網站核對通過才說「網站已驗證」。CI 失敗不回滾已儲存行程；明示目前是資料成功、驗站未過及原因。

GitHub 程式／規則讀取、Neon 最新內容與 JSON 備援仍是不同來源。Chat 的私人 Notion 操作不因行程更新觸發發布，也不把私人索引複製到公開安排。

## 10. CI request/result bridge

### 固定入口與資料契約

- 請求分支：`chat-site-check/<request-id>`，從當次解析的 main commit 建立。
- 請求檔：`bridge/site-check/requests/<request-id>.json`；唯一新增檔，禁止其他變更。
- version 1 request：schema_version、request_id、target=`production`、itinerary_id、expected_content_revision、changed_day_ids、expected public assertions（day/main_card/meal refs/transfer refs）。不含 SQL、DB locator、私人文字、任意 URL 或程式。
- 結果分支：`site-check-results`，`requests/<request-id>/result.json` 與 `result.md`。附 screenshot artifact／run URL；Chat 可固定 result commit 讀取。
- 同 request ID 若重新觸發：相同 request commit 可安全讀已有結果；不同 request commit／內容拒絕，不覆寫舊成功證據。新驗站使用新 ID，可附前次 request ID 作關聯。

### 信任與觸發

兩個小 workflow：
1. `chat-site-check-request.yml` 在限定請求分支／路徑 push 啟動，唯讀權限，作為事件入口，不執行請求分支程式、不接 secret。
2. `chat-site-check.yml` 使用預設分支上的 `workflow_run` 接完成事件。核對同一 repo、push、分支格式／run，以及 request commit 與其 parent 差異確為單一允許 JSON；以固定 SHA 取得 request，schema／大小／日期／ID 全部驗證。測試程式 checkout 當次解析後固定的受信任 main commit，絕不 checkout 請求分支執行。

request commit 必須只有一個 parent，且該 parent 位於受信任 main 歷史；拒絕 merge commit 或以修改過 workflow 的非主線 parent 包裝請求。事件入口只完成最小通知工作；worker 不信任其 artifacts 或執行結果作為驗站證據。

worker 授予執行測試及寫結果分支所需的最小 workflow 權限；使用既有 GITHUB_TOKEN，不新增 Neon 寫入 secret。token 的 contents:write 不是 GitHub 技術上的單分支權限，實作須固定只提交結果分支並驗證 diff，不誇稱平台強制隔離到一支分支。
結果分支不符合請求／部署 trigger，不產生觸發循環。寫結果的 commit 與正式站程式／資料版本分開。
結果發布採單一寫入佇列或 compare-and-swap 重試合併不同 request 檔，禁止 force-push 覆蓋其他請求結果；同一 request 的不同 run 不取消正在執行的驗站。

### 檢查及結果

讀固定正式 URL；最多 6 分鐘內有限次重讀（每 20 秒最多一次），記錄每次觀察，不能為通過而改 API base 或使用測試庫。
以 Chromium 390×844 驗：
- live API 的內容指紋／schema／環境，以及 DOM 的同值識別。
- changed_day_ids 的主活動、餐飲／交通穩定引用與 expected assertions 一致。
- DOM build ID 與同站 site-version.json 一致；記錄實際值，不拿 request／結果／測試程式 commit 冒充網站 build。
- 無未處理 JS 錯誤、無水平溢出、主要觸控目標達既有標準，五卡及導航可達。
- 截圖與必要失敗診斷 artifact；只截公開頁，不帶私人登入狀態。

result 記 request commit、trusted test commit、run ID、URL、expected／observed content revision、observed build ID、source、checks、時間與 artifact 引用。
狀態為 PASS／CONTENT_MISMATCH／FALLBACK／UNREACHABLE／INVALID_REQUEST／SUPERSEDED／ERROR。未完成時視為 PENDING（查不到 result 不等於 ERROR）。
expected 已被更新取代而內容指紋不同時不能報 PASS；若無證據區分新版／舊版，只能報 CONTENT_MISMATCH，不自行推定 SUPERSEDED。

## 11. 初始化、部署與回復

新增 `006_itinerary_model.sql`，不改寫已套用的 003–005。先在指定隔離分支測結構、ACL、交易與投影；正式 migration／Function 讀取授權變更按核准計畫執行。
六日初始內容由已接受的行程時間線供給；日期順序、餐廳及估時有來源，不由 schema migration 自動選景點。不得把示意 fixtures 當正式安排。

階段：新增結構／受控入口與公開投影 → read API／匯出 → 接入候選前端與 CI bridge → 真實授權修改及版本／API／手機驗收 → 切換正式閱讀入口。
現有 localStorage keys 不刪、不自動寫回 Neon；下拉移除只在替代鏈路驗收後進行，保留本機匯出／舊入口的回復說明。吃過狀態繼續沿用。
回復 UI／API 部署與還原行程內容是不同操作：前者恢復已知可用版本，後者經目前版本的新受控修改並留稽核。不得用還原 Git 覆蓋最新 Neon 內容或降回 SQLite。

## 12. 有意義的驗收

### 資料與受控更新

- 一日變更、兩日交換、其他日期不變；餐飲／交通一起成功。
- 中途非法參照／不合法 plan 全回滾，無成功 requests／audit。
- 過期 itinerary version 與來源已更新兩種衝突分別阻止寫入。
- 同 ID 同 payload 重送只套用一次；同 ID 不同 payload 拒絕。
- 跨來源更新時公開內容識別有變；無關餐廳更新不影響本行程指紋。
- 明確餐廳衝突聲明、已確認安排約束、合法 pool-only 例外、未知估時不能變 0。
- 更新／還原前後值與版本／request 關聯正確；ro 無寫入／原始版本／稽核讀取能力。

### API／前端／CI

- API 與 export 共用投影；hash 不含 fetched_at／匯出時間；整包備援且明示來源。
- 空值、未知 schema、網路逾時、合法／失效引用的顯示行為。
- 新 Chat 操作產生的 request 精確對應 CI 結果；錯內容即使頁面正常仍失敗。
- 舊備援、版本不符、錯環境、非法請求、結果分支循環、請求分支含額外程式檔等負面案例。
- worker 不執行請求分支程式，結果發布不改 main／部署；報告、截圖能由既有 GitHub 能力找到。
- 既有五卡、吃過持久化、導航、手機溢出／觸控回歸保持；舊暫排测试在功能切換前保留，切換後更新成資料保留／唯讀規則而非直接刪測試。

### 最終業務驗收

使用者真正要求的一個日程修改：Chat 讀前版本 → 更新 → 稽核讀回 → request commit → CI API／DOM 同內容識別與語義通過 → 使用者手機確認。此後才取消舊手機編輯。正式寫入不得以「驗收」名義使用未授權的虛構改動。

## 13. 文件與交付

同一功能交付更新 CONTENT_CONTRACT 的新表／欄／入口／公開投影／旅中例外及兩條生效鏈；AGENTS 與 Chat 指示保持一致。Chat 指示不得宣稱未上線入口可用。
驗站 report branch 不是 JSON 備援來源；資料匯出＋Pages 的發布鏈獨立保留。本輪 CI 驗站不自動觸發備援重匯或 Function 部署。

需要變更的範圍：新增 migration／測試與公開投影；functions/phq-readonly-api.mjs；tools/export_json.py；tools/build_site.py／site.css／必要的獨立行程載入器；新 request／worker workflows 與固定驗站腳本；對應規則文件。
SQL、workflow 和 UI 的可改檔清單、提交順序與隔離方式由 writing-plans 固定；不在此跨過使用者書面規格審閱。

## 14. 與其餘決策的接續

本規格不要求使用者再決定技術欄位名稱。尚待其他票交付的產品內容是：三個彈性日先後與具體六天時間線、可從 VPS 外觀看的預覽發布範圍、手機視覺方向。它們不改本規格已確認的角色／原子更新／證據分工；若回饋需要介面變更，更新規格後再排實作。
