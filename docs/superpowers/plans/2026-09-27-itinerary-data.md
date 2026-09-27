# Itinerary Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可原子修改、追蹤與公開讀取的六日日程。

**Architecture:** 一個 006 migration 按 task 分段累加 schema、投影、更新函式及 ACL；不修改歷史 migrations。單一公開 view 產生 payload 與 SHA-256；Chat 使用另一個私有讀取函式及批次更新函式。

**Tech Stack:** PostgreSQL 18、PLpgSQL、Python unittest／psycopg2。

**Spec:** `../specs/2026-09-27-itinerary-chat-ci-design.md`。

## Global Constraints

沿用 [總計畫 Global Constraints](2026-09-27-itinerary-implementation.md#global-constraints) 全部限制。固定 `phuquoc-2026`／10/10–15、六日、private version 不公開、006 additive、tests production 零寫入。

## Review Focus

- 並行更新／同 ID 重送只提交一次：A2。
- pool→food 依賴在等鎖時變動要重新收集：A1/A2。
- 無關來源不變指紋、引用來源改變須變：A1。
- 部分日期非法不能留下 audit／request：A2。
- SECURITY INVOKER 不等於 owner connector 無法繞過：A3 實際 ACL 與文件。

## 檔案及測試支援

- 新增 `tools/migrate_neon/006_itinerary_model.sql`：三個表、audit request_id、驗證／公開投影／編輯讀取／受控更新／ACL。
- 新增 `tools/verify/itinerary_db_support.py`：隔離 DSN guard、unittest fixture helpers、兩連線測試工具；不自動對任何庫跑歷史 004 seed。
- 新增 `tools/verify/test_itinerary_projection.py`、`test_itinerary_update.py`、`test_itinerary_acl.py`。
- 新增 `tools/verify/fixtures/itinerary-test-seed.sql`：交易內合成來源及六日資料；fixture 明示非旅行建議，測試結束 rollback。

### Task A1：schema、驗證器與一致公開投影

**Files:** 建立上述 migration、support、seed、projection tests。

**Interfaces:**
- `public.itinerary_public` view：`itinerary_id TEXT,payload JSONB,content_revision TEXT`。
- `itinerary_payload(p_id TEXT) RETURNS JSONB`：固定公開白名單，無私有欄。
- `itinerary_validate_day(p_day JSONB) RETURNS VOID`：語法／型別／參照驗證；錯誤 SQLSTATE `22023`、固定訊息。
- `itinerary_read_for_edit(p_id TEXT) RETURNS JSONB`：`{version,content_revision,days}`，維護身分限定；資料同一 statement snapshot。
- support `ItineraryDBCase(unittest.TestCase)`：`self.db` 開啟 rollback fixture 交易；`scalar(sql,params=())` 第一欄；`execute(sql,params=())`；`snapshot()` 回傳 `{payload,revision,version,audit_count,request_count}`。

- [ ] **1. 建立 failing projection tests 與 fixture harness。** guard 檢查環境後連指定 DB；migration 初次由執行者套到隔離環境，harness 不猜目標。fixtures 用現有來源表結構 INSERT 合成鍵 `fixture-*`，建立六日；主活動使用既有 card slugs，不硬填正式餐廳。第一個測試：

```python
from itinerary_db_support import ItineraryDBCase

class ProjectionTests(ItineraryDBCase):
    def test_six_days_and_no_private_metadata(self):
        s = self.snapshot()
        self.assertEqual(len(s['payload']['days']), 6)
        self.assertRegex(s['revision'], r'^phq1:[0-9a-f]{64}$')
        forbidden = {'version','locked_constraints','request_id','old_value','new_value'}
        def walk(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden.intersection(value))
                for child in value.values(): walk(child)
            elif isinstance(value, list):
                for child in value: walk(child)
        walk(s['payload'])
```

- [ ] **2. 執行 RED。** `python3 -m unittest discover -s tools/verify -p test_itinerary_projection.py -v`；預期不存在 view，而不是 DSN／dependency 錯誤。
- [ ] **3. 寫 schema 與 validator。** 三表欄位依 spec §4。`changes` 日 ID／date 不允許變；JSON key 白名單每層驗，time 區間 min≤max、HH:mm、day_offset 0/1、IANA timezone 需存在 `pg_timezone_names`。拒絕未知 ref／negative minutes／重複 segment／錯條件引用／備案巢狀。對 pool-only NULL 保留合法語義。核心 SQL：

```sql
ALTER TABLE public.content_revisions ADD COLUMN IF NOT EXISTS request_id uuid;
CREATE INDEX IF NOT EXISTS content_revisions_request_id_idx
  ON public.content_revisions(request_id) WHERE request_id IS NOT NULL;
-- 公開 view 的 payload 在同一 statement 只組一次。
CREATE OR REPLACE VIEW public.itinerary_public AS
SELECT id AS itinerary_id, p.payload,
 'phq1:' || encode(sha256(convert_to(p.payload::text,'UTF8')),'hex') AS content_revision
FROM public.itineraries
CROSS JOIN LATERAL (SELECT public.itinerary_payload(id) AS payload) p;
```

`itinerary_payload` 回總計畫共用 data 形狀；days 按日期，refs 每類按穩定鍵排序。food 白名單沿 `export_json.py:64–70`；cards/points/pool/bookings/transport 沿同檔與 API 現有清單。base 只從 approved booking/point 鍵映射公共位置，未知位置不猜座標。用 SQL JSONB path 收集 segments／replacement_segments／transfer 端點＋main_card；pool 再展開 food。bookings 關聯只由 locked constraints 決定；不公開 locked constraints 本身。來源 ref 不存在就拒絕投影，不回半份內容。
- [ ] **4. 加 dependency/hash tests。** 比較更新引用 food 的 hours_text 前後 revision；更新 fixture-unrelated food revision 相同；更換 pool.notion_id 後 refs.foods 跟隨；timestamp／private version 更動 revision 相同；六日還原原公開 payload 取得原指紋。將上述 cases 用 `self.execute` 在 fixture 交易內操作，驗 bytes canonical hash 與 view 一致。
- [ ] **5. 執行 GREEN 並 commit。** 同 RED 命令全 PASS；`git add tools/migrate_neon/006_itinerary_model.sql tools/verify/itinerary_db_support.py tools/verify/test_itinerary_projection.py tools/verify/fixtures/itinerary-test-seed.sql`；`git commit -m "feat: add itinerary model and public projection"`。

### Task A2：原子更新、重送、稽核與併發

**Files:** 修改 migration/support；新增 `tools/verify/test_itinerary_update.py`。

**Interfaces:** A1 的 view/validator；新增以下 function（exact order）：

```sql
itinerary_update(p_itinerary_id text, p_base_version integer,
 p_expected_content_revision text, p_request_id uuid, p_changes jsonb,
 p_explicit_selection_decisions jsonb, p_actor text, p_source text, p_reason text)
RETURNS jsonb
```

return=`{request_id,resulting_version,changed_day_ids,content_revision}`。固定錯誤：VERSION_CONFLICT、SOURCE_CHANGED（SQLSTATE 40001）、REQUEST_ID_REUSED、INVALID_PLAN、LOCKED_ARRANGEMENT、EXPLICIT_DECISION_REQUIRED（22023）。source/reason 必填非空；actor 可 NULL。

support 增 `candidate(day,card)`（從 fixture current day 複製且同步 activity/meal/transfer）、`update(request_id,changes,base=None,revision=None,decisions=None)`（預設讀當前 base/revision）、`new_request_id()`（uuid4 字串）。test rollback 後重新建立 savepoint，避免吞 PostgreSQL aborted transaction。

- [ ] **1. 寫 atomicity/retry failing tests。**

```python
from itinerary_db_support import ItineraryDBCase

class UpdateTests(ItineraryDBCase):
    def test_retry_returns_receipt_without_extra_audit(self):
        before = self.snapshot()
        request = self.new_request_id()
        changes = [self.candidate('2026-10-12', 'cable')]
        first = self.update(request, changes, before['version'], before['revision'])
        after = self.snapshot()
        second = self.update(request, changes, before['version'], before['revision'])
        self.assertEqual(first, second)
        self.assertEqual(after, self.snapshot())
        self.assertEqual(after['audit_count'], before['audit_count'] + 1)
```

- [ ] **2. 執行 RED。** `python3 -m unittest discover -s tools/verify -p test_itinerary_update.py -v`；預期 itinerary_update 未定義。
- [ ] **3. 實作交易入口。** 固定 `search_path=pg_catalog,public` 並全限定表；SECURITY INVOKER。輸入含 decisions 一起 canonical hash；先鎖主檔再 dedupe，再驗 base。採 `FOR SHARE` 鎖來源（不是 KEY SHARE）。pool→food 是多層依賴：收集後依固定 table/id 鎖列，再重算 closure；若集合改變，raise SOURCE_CHANGED 回滾，讓 Chat 重讀，禁止持鎖後無限追新依賴。新候選引用雖不在舊 hash，仍需讀當前來源、鎖列並驗狀態；Chat 不得聲稱舊指紋保護了尚未被引用的歷史事實。

```sql
-- 在同一函式交易內，任何 RAISE 使本次寫入回滾。
SELECT version INTO v_version FROM public.itineraries
 WHERE id=p_itinerary_id FOR UPDATE;
-- dedupe 在比對 base 前；相同 request hash 回原 receipt。
IF v_version <> p_base_version THEN
 RAISE EXCEPTION USING ERRCODE='40001', MESSAGE='VERSION_CONFLICT';
END IF;
-- 驗證完所有日後才開始 UPDATE；每個日各一筆 audit。
```

`explicit_selection_decisions` 固定 array 元素 `{day_id,segment_id,previous_ref,decision}`；decision=`keep/remove/replace`；舊 explicit 被移除／換 ref 必須有匹配聲明，未改選擇不要求。locked_constraints 核對保護的日期/card/booking；不把整日餐飲鎖死。requests receipt 最後寫，源自同交易 post-update payload。
- [ ] **4. 加失敗／還原 tests。** 兩日交換後其他四日完全相同；第二日非法參照時 snapshot 完全不變；舊 base、來源更新、同 ID 改 payload 各失敗；restore 新 request 對應新的 audit 而原紀錄仍在。測 UTF-8 bytes 超過128 KiB（不是字元數）、unknown keys、NULL/負數估時、OnBird 主活動移日拒絕。
- [ ] **5. 加雙連線真併發 tests。** helper 建立明示專用 fixture 後 commit，finally 按 fixture keys 清理（僅隔離庫）；兩 thread barrier 同時用同 base，恰一個成功；同 request/payload 雙呼叫兩者同 receipt。另一連線持有 pool 列鎖並改 notion_id，更新等待後必須 SOURCE_CHANGED 或重新驗證正確新 closure，不能 receipt 混舊 food。測试設 statement_timeout=5s 避免掛住。
- [ ] **6. 執行 GREEN、commit。** `python3 -m unittest discover -s tools/verify -p 'test_itinerary_*.py' -v`；`git add tools/migrate_neon/006_itinerary_model.sql tools/verify/itinerary_db_support.py tools/verify/test_itinerary_update.py`；`git commit -m "feat: add atomic itinerary update and audit"`。

### Task A3：權限、migration 重跑與發布輸入

**Files:** 修改 migration；新增 `tools/verify/test_itinerary_acl.py`、`docs/ops/ITINERARY_DB_RUNBOOK.md`。

**Interfaces:** 006 只建立結構與函式，不初始化正式內容；`phq_web_ro` 僅新 view SELECT，helper 不開寫入 EXECUTE；維護者沿現有經核准身分。runbook 記 migration SHA256、target branch ID、applied_at、test result，無 DSN。

- [ ] **1. 寫 failing ACL test。** 以 `SET LOCAL ROLE phq_web_ro` 實讀 view，嘗試 SELECT requests/audit/new private tables、執行 update 各須 insufficient_privilege。每個預期失敗使用 SAVEPOINT 回復。

```python
class ACLTests(ItineraryDBCase):
    def test_reader_can_read_only_projection(self):
        self.execute('SET LOCAL ROLE phq_web_ro')
        self.assertEqual(self.scalar('SELECT count(*) FROM public.itinerary_public'), 1)
        self.assertFalse(self.scalar("SELECT has_table_privilege(current_user, 'public.itinerary_requests', 'SELECT')"))
```

- [ ] **2. 執行 RED。** 同 unittest discovery 只跑 `test_itinerary_acl.py`；預期 view 權限缺失或函式 PUBLIC 尚未收斂。
- [ ] **3. 加精確 ACL、owner projection。** view 採預設 owner 權限，只顯式投影；唯讀 helper 如須 EXECUTE 僅給投影函式，不給驗證／編輯讀／更新。`REVOKE ALL ON FUNCTION public.itinerary_update(text,integer,text,uuid,jsonb,jsonb,text,text,text) FROM PUBLIC,phq_web_ro;`。授維護者依部署前查得的角色，不硬猜新角色；若 owner 正是既有維護者無須另 grant。
- [ ] **4. 驗證重跑保留資料。** 同隔離庫套 006 兩次，更新及 request/audit row counts 不變；schema 無差異。runbook 列正式初始化必須使用已批准六日內容，初始 version=1，初始化者核對 locked constraints，執行六日及主活動約束查詢後一次 commit。部署回復為撤回 API/前端讀新 view，不 DROP 有內容的新表。
- [ ] **5. 執行全部 A tests、commit。** `python3 -m unittest discover -s tools/verify -p 'test_itinerary_*.py' -v` 全 PASS；`git add tools/migrate_neon/006_itinerary_model.sql tools/verify/test_itinerary_acl.py docs/ops/ITINERARY_DB_RUNBOOK.md`；`git commit -m "test: verify itinerary access and migration lifecycle"`。
