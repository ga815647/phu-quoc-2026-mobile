# Chat 六日安排操作手冊（工程候選；**未上線**）

2026-09-27。僅待 `006_itinerary_model.sql`、Function、站點與主線規則均經批准並**實際發布**後使用。現在 production 不存在可據此操作的新能力；勿在正式庫試寫、勿將本地 fixture 當旅行安排。先核對 `CONTENT_CONTRACT.md` §10 與 `CHAT_ACCEPT.md` 的發布狀態。既有研究／訂單凍結、私人 Notion 分工不變。

## 一次實際修改（有使用者具體要求且正式入口已驗收才執行）

1. 以 GitHub 讀 `main` ref 得到完整 40 碼 commit SHA；以**該 SHA**分別讀 `CONTENT_CONTRACT.md`、`chatgpt-instructions.md`、本檔與 `docs/ops/REDESIGN_SCOPE.md`。若 main 尚無新契約／發布驗收，停止。這個 Git SHA 是規則版本，**不是** Neon 內容 hash。
2. Neon 工具明確指定 `project_id=holy-fog-65935796`、`branch_id=br-silent-haze-b3xw64tm`、`database_name=neondb`，先唯讀查目標與有效權限。讀私有版本及完整六日候選原文（不從 GitHub 備援推導新版本）：

   ```sql
   SELECT public.itinerary_read_for_edit('phuquoc-2026') AS edit_state;
   SELECT itinerary_id,content_revision,payload FROM public.itinerary_public
    WHERE itinerary_id='phuquoc-2026';
   ```

   `edit_state` 提供 `version`、`content_revision`、每一天 `id,date,day_kind,main_card_slug,plan,version`；私有 version 只用於寫入，**不可**進公開請求。公開 view 的 revision = `phq1:`＋64 位小寫十六進位，是整份公開投影（含引用的餐飲／交通）的 hash；不是 `fetched_at`、Git SHA 或匯出檔 hash。
3. 先理解受影響的**完整日**及相關已確認預訂，再建立完整候選：保留不變欄位，主活動、餐飲建議與去回交通及備案一起重估；明確指定餐廳衝突先問，OnBird／航班／住宿不以此函式改訂單。資料用穩定 ID，不含私人價格、聯絡方式或訂單碼。例子只是 SQL 形狀（`2026-10-12`、`public_note` 不是預設旅遊安排）：用從 `read_for_edit` 取得的原 `days` 形成候選，且在送出前核對原 plan 與實際使用者決定一致。
4. 若通道支援 bind，參數型別依序為 `text,integer,text,uuid,jsonb,jsonb,text,text,text`，不要把 JSON 串進 SQL。Neon `run_sql` 只有 `sql` 字串而**沒有 bind** 時，可用下例的**字面值模板**：人工填入剛讀到的整數 version、完整 revision、外部產生且未用過的 UUID；檢查 version 為十進整數、hash 符合 `^phq1:[0-9a-f]{64}$`、UUID 符合 canonical UUID，再執行。動態 JSON／來源文字使用 PostgreSQL **唯一的** dollar-quote delimiter；先確認該 delimiter 在整份字串中不存在。不得以任意 `replace`／單引號拼接不受信輸入；無法安全編碼就停止，請改用支援 bind 的通道。

   ```sql
   -- 在已部署且有使用者授權的環境，替換所有 <...>；不得原樣執行。
   -- changes 必須是從最新 read_for_edit 重建之完整受影響日 JSON array，
   -- 如 [{"id":"phuquoc-2026:2026-10-12","date":"2026-10-12",
   --     "day_kind":"activity","main_card_slug":"cable","plan":{...}}]。
   -- decisions 無明確指定餐廳衝突時為 []；有衝突時先問，依契約填
   -- [{"day_id":"...","segment_id":"...","previous_ref":{...},"decision":"replace"}]。
   SELECT public.itinerary_update(
     'phuquoc-2026', <read_version>::integer, '<read_phq1_hash>'::text,
     '<fresh_canonical_uuid>'::uuid,
     $phq_changes_1$<complete_changed_days_JSON_array>$phq_changes_1$::jsonb,
     $phq_decisions_1$[]$phq_decisions_1$::jsonb,
     NULL::text, $phq_source_1$chat-neon$phq_source_1$::text,
     $phq_reason_1$<user-request-and-source-date>$phq_reason_1$::text
   ) AS receipt;
   ```

   若要避免複製整份 JSON，以下是**隔離庫的完整 SQL 形狀示例**：把讀取時記下的
   `version`、`content_revision` 兩個常數與新 UUID 代入，保留該日原有整份 `plan`、
   只把 `public_note` 更新為虛構文字。範例字面值均為測試用途，不可對 production
   原樣執行；真正換主卡時必須重新安排 meal/transfer 並由使用者決定內容。

   ```sql
   -- 第一次呼叫只讀，抄下 version/content_revision；不要在 UPDATE 當下
   -- 再以 SELECT 最新版冒充原讀取的 optimistic base。
   SELECT public.itinerary_read_for_edit('phuquoc-2026');
   -- 接下來把 <read_version>/<read_phq1_hash>/<fresh_canonical_uuid>
   -- 用上一步的原值及新 UUID 置換；不能把尖括號原樣送入 Neon。
   WITH selected AS (
     SELECT d.value AS day FROM jsonb_array_elements(
       public.itinerary_read_for_edit('phuquoc-2026')->'days') d
     WHERE d.value->>'id'='phuquoc-2026:2026-10-12'
   ), candidate AS (
     SELECT jsonb_build_array(jsonb_build_object(
       'id',day->'id','date',day->'date','day_kind',day->'day_kind',
       'main_card_slug',day->'main_card_slug',
       'plan',jsonb_set(day->'plan','{public_note}',
         to_jsonb($phq_note_1$測試文字（隔離庫）$phq_note_1$::text),true))) AS changes
     FROM selected
   )
   SELECT public.itinerary_update('phuquoc-2026',<read_version>::integer,
     '<read_phq1_hash>'::text,'<fresh_canonical_uuid>'::uuid,
     changes,'[]'::jsonb,NULL::text,'chat-neon'::text,
     '隔離庫測試：使用者要求及來源日期另記'::text) AS receipt FROM candidate;
   ```

   建議優先使用上方**完整 JSON 候選**流程，並先檢查 day 候選是否與原讀取一致；
   SQL `selected` 範例的第二次 read 只用來展示類型安全構造，不應拿來繞過
   原 base/hash 驗證，也不保證跨步驟取得同一快照。

   真正呼叫 bind 的形式（僅當工具實際可傳參數時）：

   ```sql
   SELECT public.itinerary_update($1::text,$2::integer,$3::text,$4::uuid,
     $5::jsonb,$6::jsonb,$7::text,$8::text,$9::text);
   ```

   Receipt 的 `request_id,resulting_version,changed_day_ids,content_revision` 要立即保存；**同 payload** 重送同 UUID 只回原 receipt；不同 payload 不得重用。
5. 同一請求成功後，立即按 UUID 讀私有 audit 真前值、讀公開 view，對照日／hash：

   ```sql
   SELECT target_table,target_id,field_name,old_value,new_value,
          base_version,resulting_version,changed_at,source,reason
     FROM public.content_revisions
    WHERE request_id='<receipt_request_uuid>'::uuid ORDER BY target_id;
   SELECT itinerary_id,content_revision,payload FROM public.itinerary_public
    WHERE itinerary_id='phuquoc-2026';
   ```

   不公開 audit 或版本。`VERSION_CONFLICT`／`SOURCE_CHANGED`（SQLSTATE 40001）→ 停止、重讀並說明差異，再按目前版本重組候選；不盲目重試覆寫。`REQUEST_ID_REUSED`（22023）→ 查是否誤用 UUID，不直接覆蓋。其他驗證失敗不當成功；資料已存但驗站 pending／fail **不回滾或改用舊 base**，保留 receipt 並重讀觀測值，查原因後另發請求。
6. 真實 GitHub 驗站（**本地測試未做這步**）：先確定公開 API `/api/itinerary` 讀到相同 `content_revision`；它可能有快取。以新 UUID 作**驗站 request ID**（不必等於 Neon 修改 UUID），建立 `chat-site-check/<uuid>` branch，以 main 為單一父 commit，該 commit **只新增** `bridge/site-check/requests/<uuid>.json`；JSON 使用契約 v1 的鍵 `schema_version:1,request_id,target:"production",itinerary_id:"phuquoc-2026",expected_content_revision,changed_day_ids,expected`，`expected` 每日包含 `day_id,main_card_slug,meals:[{segment_id,ref}],transfers:[{segment_id,from_ref,to_ref,mode}]`，完整列表由更新後公開投影產生。不可寫工具碼、workflow 或私人欄位；不可把請求 commit 當作內容版本。

   以下是**格式樣本，不可照抄 hash 或旅行內容**（`fixture-*` 僅本地隔離資料）。GitHub connector 應先由 main 建 branch，再只新增對應 UUID 路徑並讀回 request commit；同一 commit 不可含其他檔案：

   ```json
   {"schema_version":1,"request_id":"1f4be2aa-e9b5-4a8a-8f1c-68c6d7eef67a",
    "target":"production","itinerary_id":"phuquoc-2026",
    "expected_content_revision":"phq1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "changed_day_ids":["phuquoc-2026:2026-10-12"],
    "expected":[{"day_id":"phuquoc-2026:2026-10-12","main_card_slug":"cable",
      "meals":[{"segment_id":"meal","ref":{"type":"food","id":"fixture-unrelated"}}],
      "transfers":[{"segment_id":"go","from_ref":{"type":"card","id":"cable"},
        "to_ref":{"type":"base","id":"hotel"},"mode":"taxi"}]}]}
   ```
7. 記下請求 commit SHA，等受信任主線 workflow 實際執行。解析 `site-check-results` ref，在**固定 result commit SHA** 讀 `requests/<uuid>/result.json`（另可讀 `.md`），核對 `request_id,request_commit,expected_content_revision,observed_content_revision,source,observed_build_id,run_id,status,finished_at`。`PASS` 只證明那次觀察；`FALLBACK/CONTENT_MISMATCH/UNREACHABLE/ERROR/INVALID_REQUEST` 不算已上站；pending 無結果不能當 PASS。截圖另在同 run artifact，綠燈、Git JSON 或 screenshot 單獨都不能替代網站/API/DOM 的同版檢查。Chat 讀 GitHub 結果不等於 Chat 自己能 HTTP 看站。

## 各層證據與發布邊界

| 層 | 需持有的證據 | 目前狀態 |
|---|---|---|
| 本地工程候選 | 隔離 PG18 回滾測試、candidate build、Chromium、**假 GitHub**固定 SHA readback | 可重跑；不是正式資料／Actions |
| 規則已發布 | main commit 並由 Chat **實際固定 SHA 讀取** | 未驗，不能稱 Chat 已知道新契約 |
| 內容已存 | 正式受控更新 receipt＋私有 audit 與公開 view 讀回 | 新入口未上線，待授權 |
| 網站實際顯示 | 正式 Function API＋正式 DOM 同 hash，CI 結果 branch 固定 SHA＋手機接受 | 待部署、真請求與手機驗收 |
| 離線備援 | OpenCode 從 Neon 匯出 `data/itinerary.json`、有日期的 release commit、Pages 發布後斷網讀回 | **獨立**待發布；Chat 不可聲稱已刷新 |

正式 `006` 套用、ACL／Function、六天真內容初始化、視覺預覽、手機接受與 readonly 切換均要另行核准和留證；本手冊不是發布授權。
