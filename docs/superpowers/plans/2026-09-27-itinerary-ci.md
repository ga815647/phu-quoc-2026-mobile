# Itinerary CI and Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chat 提交純 JSON 驗站請求，CI 核對當次公開內容及手機畫面，Chat 可讀回精確關聯的結果。

**Architecture:** 純 request validator 與 browser verifier 分開；default-branch worker 唯讀驗站後用固定結果分支發布。可信測試 SHA、request SHA、網站 build ID、內容指紋各自保存，發布與內容寫入不由 CI 執行。

**Tech Stack:** Node.js 24／node:test、Playwright 1.55.0、GitHub Actions／REST API、Python 3。

**Spec:** `../specs/2026-09-27-itinerary-chat-ci-design.md`。

## Global Constraints

完整繼承 [總計畫](2026-09-27-itinerary-implementation.md#global-constraints)。request branch=`chat-site-check/<UUID>`；結果=`site-check-results`；正式 URL 固定 `https://ga815647.github.io/phu-quoc-2026-mobile/`。CI 不寫 Neon、不部署、不執行 request branch 程式；6 分鐘／20 秒間隔。

## Review Focus

- 合法 JSON 外包不可信 parent/workflow：C1 拒絕 ancestry 不符。
- 正確 DOM hooks 但畫面文字舊／空白：C2 核对 visible text。
- 結果分支並行更新互相覆蓋：C2 CAS retry 測試。
- workflow 取消或 artifact 上傳失敗：C2/C3 不誤報成功或保證通知。
- 新版 supersede 舊請求：只報觀察值／CONTENT_MISMATCH，無證據不推定 SUPERSEDED。

## 檔案責任

- 新 `tools/verify/site-check-contract.mjs`：常數、JSON/schema、request git ancestry/diff 驗證、結果欄位。
- 新 `tools/verify/test_site_check_contract.mjs`：node unit tests。
- 新 `tools/verify/site-check-browser.mjs`：唯讀 browser verifier，輸出本地 result＋screenshots。
- 新 `tools/verify/site-check-publish.mjs`：GitHub API 讀可信 request／CAS 寫結果。
- 新 `tools/verify/test_site_check_browser.mjs`、`test_site_check_publish.mjs`。
- 新 `.github/workflows/chat-site-check-request.yml`、`chat-site-check.yml`。
- 新 `docs/ops/CHAT_ITINERARY_RUNBOOK.md`；更新既有 AGENTS／CONTENT_CONTRACT／chatgpt-instructions／scope／CHAT_ACCEPT／data/AGENT_QUERY.md 與新設計輸入文件。

### Task C1：request schema 與可信事件驗證

**Consumes:** A2 receipt／B 公開 envelope 與穩定 IDs。

**Produces:** `validateRequest(rawBytes,gitContext) -> request`，錯誤 throw Error('INVALID_REQUEST')；gitContext=`{repository,event,branch,requestSha,parents,mainAncestor,files}`。固定 REQUEST schema：

```json
{
 "schema_version":1,
 "request_id":"1f4be2aa-e9b5-4a8a-8f1c-68c6d7eef67a",
 "target":"production",
 "itinerary_id":"phuquoc-2026",
 "expected_content_revision":"phq1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
 "changed_day_ids":["phuquoc-2026:2026-10-12"],
 "expected":[{"day_id":"phuquoc-2026:2026-10-12","main_card_slug":"cable","meals":[],"transfers":[]}]
}
```

expected meal=`{segment_id,ref:{type,id}}`；transfer=`{segment_id,from_ref:{type,id},to_ref:{type,id},mode}`。每 changed day 恰一 expected；陣列列出該日全部主線 meal/transfer，不允許省掉部分繞過檢查。新驗站可有 `previous_request_id`；拒絕其他欄，128 KiB 上限、UUID 與路徑一致。不接受任意 URL 或 shell 值。

- [ ] **1. 寫 failing validator tests。** fixture 用上述 request；gitContext 存可信 repo、push、parent是main祖先、files 唯一 added request JSON。

```javascript
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {validateRequest} from './site-check-contract.mjs';
test('untrusted parent rejected even when last diff is just JSON',()=>{
 const bytes=new TextEncoder().encode(JSON.stringify(requestFixture));
 assert.throws(()=>validateRequest(bytes,{...trustedContext,mainAncestor:false}),/INVALID_REQUEST/);
});
```

測試檔在 setup 定義 `requestFixture`／`trustedContext`，不從環境信任 branch SHA。
- [ ] **2. RED。** `node --test tools/verify/test_site_check_contract.mjs`；module 缺失。
- [ ] **3. 寫 validator。** JSON object exact keys；格式/上限/dependent arrays/ID 引用；只同 repo `ga815647/phu-quoc-2026-mobile`、push、branch前綴、單 parent，parent 由 worker GitHub compare API 證明位於可信 main 歷史。diff 改 workflow、第二檔、rename/delete、merge commit、錯request ID均拒絕。非同步 GitHub 請求在 publish 模組完成，純 validator 不 fetch。

```javascript
export const SITE_URL='https://ga815647.github.io/phu-quoc-2026-mobile/';
export const RESULT_BRANCH='site-check-results';
export const UUID_RE=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
```

- [ ] **4. GREEN cases。** 正確新增 JSON 通過；空 changed_day_ids、重複日期、未知 slug、private key、128KiB+1、分支ID不符、非UTF8、檔名 traversal、mainAncestor false 拒絕。request 下 `expected` 只驗靜態形狀；C2 跟實際 payload 比完整集合。
- [ ] **5. commit。** 上述命令 PASS；`git add tools/verify/site-check-contract.mjs tools/verify/test_site_check_contract.mjs`；`git commit -m "feat: define trusted site-check request contract"`。

### Task C2：實際瀏覽器驗證、結果及 workflow

**Consumes:** C1 request、B1 API envelope、B2 DOM/build ID。

**Produces:**
- `verifySite({request,page,siteUrl,now,sleep,budgetMs=360000,intervalMs=20000}) -> Promise<result>`；siteUrl 注入僅供 unit tests，production CLI 固定 SITE_URL、不接受 URL arg。
- `readTrustedRequest({event,github}) -> {request,requestSha,testSha}`。
- `publishResult({github,requestSha,result,markdown}) -> {commitSha,path}`。
- result=`{schema_version,request_id,request_commit,test_commit,run_id,url,status,expected_content_revision,observed_content_revision,observed_build_id,source,started_at,finished_at,checks,observations,artifacts}`。

- [ ] **1. 寫 RED browser tests。** Playwright 本地 route 接 B fixture；正確 API/hash 但 DOM 有舊餐廳時必失敗；hook正確但文字空白亦失敗。6分鐘測試用注入假時鐘，禁止真等六分鐘。

```javascript
test('does not certify fallback as current live content',async()=>{
 const result=await verifySite({request,page,siteUrl:localUrl,
   now:()=>clock,sleep:async ms=>{clock+=ms;},budgetMs:100,intervalMs:20});
 assert.equal(result.status,'FALLBACK');
 assert.notEqual(result.status,'PASS');
});
```

test setup 定義 page/localUrl/request、route envelope 與 fallback data-source；finally browser.close。
- [ ] **2. RED。** `node --test tools/verify/test_site_check_browser.mjs tools/verify/test_site_check_publish.mjs`；預期新 modules 未存在。
- [ ] **3. 寫 verifier。** 到 SITE_URL 後固定允許正式 API host；禁止 query/API override。讀網站實際 consumption 的 API response，核对 production/source/schema/hash；不是另抓新 API 就認為頁面已用它。逐日切 tab，再驗可見活動/餐飲名稱/交通文字與 envelope解析值及 expected refs 完整集合。data-source/hash/DOM hooks 同值；site-version.json 和 html build ID 同值。每輪 pageerror 清單保留上下文，超時／unreachable有限次重試；截圖手機390×844、觸控41px、五卡及溢出。

PASS 必須全部 checks 成功；fallback／unreachable／內容不符按觀察分類。只有可信較新 request result 能證明取代時用 SUPERSEDED，否則 CONTENT_MISMATCH。result 時間戳說明是該次觀察，不聲稱其後不會變。
- [ ] **4. 寫 GitHub adapter／publisher。** `github` 是 `{request(method,path,body?)}` 注入介面；token 僅 env，不 log。讀 commit、parent compare、full diff（處理 pagination）、raw blob by SHA，驗 payload，再取 trusted main SHA。發布讀結果 branch HEAD、確認同 request 已有證據：相同 requestSha 回已有結果，不同拒絕；新 blob/tree/commit base=目前HEAD，PATCH ref force=false。409/422 再讀HEAD、重建tree最多3次，保留其他request檔；branch不存在首次建立，競爭已建立就重試。只改 `requests/<UUID>/result.json/result.md`，immutable filename不由任意JSON提供。

```javascript
// 不使用 --force。retry 必須重新建 tree，不能沿用舊 parent。
await github.request('PATCH',`/repos/ga815647/phu-quoc-2026-mobile/git/refs/heads/${RESULT_BRANCH}`,
 {sha:newCommitSha,force:false});
```

- [ ] **5. 寫兩個 workflows。** request workflow 名 `chat site-check request`，push branches=`chat-site-check/**`，paths=`bridge/site-check/requests/*.json`，permissions contents:read；只有常數 shell `true`，不 checkout。worker：

```yaml
on:
  workflow_run:
    workflows: ['chat site-check request']
    types: [completed]
permissions:
  contents: read
  actions: read
```

worker 分 verify/publish jobs：verify 讀 current main 固定SHA後checkout（不使用head_branch），Node24、既有版本 Playwright，無 Neon secrets；write local result。無效事件/請求也產生 INVALID_REQUEST 診斷，只有合法UUID路徑可發布。artifact upload `if: always()`；artifact upload 失敗記 ERROR，不報含不存在截圖的PASS。publish job 加 contents:write，從**當次可信verify job**讀artifact並再次檢查run/request/檔案名；不執行任何artifact腳本。結果串行 concurrency固定 `site-check-result-publish`、cancel-in-progress=false，CAS仍保留。verify每request可獨立跑，duplicate不cancel既有run。

production CLI 接 `GITHUB_EVENT_PATH/GITHUB_RUN_ID`、可信程式讀 request；不以 `${{ ... }}` 把分支文字直接拼 shell。workflow總timeout 12分鐘含瀏覽器安裝；browser本體6分鐘。有run取消無result時Chat呈pending並連Actions狀態，不製造完成證據。
- [ ] **6. GREEN cases。** publish fake API兩個requests同時先读同HEAD，第二個CAS失敗重建後兩份都存在；相同request不同SHA拒絕；page只有API PASS但DOM未更新失敗；錯環境、JS error、溢出、無法連線、artifact error、快取舊版各有結果。`node --test tools/verify/test_site_check_contract.mjs tools/verify/test_site_check_browser.mjs tools/verify/test_site_check_publish.mjs` PASS；解析兩份YAML並核對權限/觸發；若環境有actionlint執行，沒有則記錄並在PR/隔離驗證補上，不宣稱跑過。
- [ ] **7. commit。** 僅 add 本task三個新modules（contract僅新增共用result常數時修改）、兩tests、兩workflow；`git commit -m "feat: verify requested itinerary changes and publish CI evidence"`。

### Task C3：操作文件、端到端驗收與正式切換條件

**Files:** 新 `docs/ops/CHAT_ITINERARY_RUNBOOK.md`；修改 `CONTENT_CONTRACT.md`、`AGENTS.md`、`chatgpt-instructions.md`、`data/AGENT_QUERY.md`、`docs/ops/REDESIGN_SCOPE.md`、`CHAT_ACCEPT.md`、`CHAT_CI_DESIGN.md`、`ITINERARY_MODEL_OPTIONS.md`；必要時依已接受視覺規格更新 `tools/build_site.py/site.css` 與 `.github/workflows/data-smoke.yml`。

**Interfaces:** 不新增API；提供Chat可直接複製的SQL參數及GitHub request操作；record區分本地測試、published commit、Chat實際讀取、production/API/CI/mobile各階段。

- [ ] **1. 撰寫runbook。** 操作順序：解析main→固定SHA讀規則→`SELECT public.itinerary_read_for_edit('phuquoc-2026')`→建立受影響日候選→帶base/hash/UUID呼叫update→同request讀audit→公開projection讀回→建request branch/file→固定request commit→查results branch→讀固定result commit。SQL例子用參數綁定，不將JSON手拼成SQL；Neon工具無bind功能時使用可驗證dollar quote與UUID/型別檢查，拒絕不安全字串拼接。

```sql
SELECT public.itinerary_update($1::text,$2::integer,$3::text,$4::uuid,
 $5::jsonb,$6::jsonb,$7::text,$8::text,$9::text);
SELECT target_id,old_value,new_value,base_version,resulting_version
 FROM public.content_revisions WHERE request_id=$1::uuid ORDER BY target_id;
```

VERSION_CONFLICT/SOURCE_CHANGED→重讀、解釋差異再重組；REQUEST_ID_REUSED→檢查是否重用ID，不直接覆蓋。資料已存但驗站pending/fail，保持原receipt並讀回，不回滾。fallback更新仍由OpenCode匯出發布，Chat不得聲稱已刷新離線檔。
- [ ] **2. 文件同步與本機完整端到端。** 凍結規則新增每日安排受控例外，研究／訂單限制原樣；表／函式／view ACL與PUBLIC JSON欄位逐项列明。隔離庫完成一個測試修改→B候選載入→C browser verifier→mock GitHub publish→固定SHA readback；測試證據存 `CHAT_ACCEPT.md` 的新功能區，不覆蓋舊connector證據。
- [ ] **3. 執行工程整合checks。** A所有unittest、B/C node tests、B browser script；既有 `candidate_ui_accept.py/journey_collapse_verify.py/transport_grouping_verify.py` 先讀usage再以候選目錄執行，不能猜預設而測到production。`git diff --check`；生成器legacy模式輸出對比五卡、navigation、eaten與slots保留。修正本次引入回歸，歷史資料差異單獨記錄。
- [ ] **4. 發布前讀取總計畫四項前置。** 已批准六日內容／視覺稿／預覽範圍未具備時停在已測工程候選；清楚列等待輸入。取得部署確認後才套006到指定正式branch、核對ACL、初始化真實安排；部署Function→Neon匯出→候選預覽→手機接受。每段記錄target/version，CI本身不代跑部署。
- [ ] **5. 驗真實請求與備援。** 使用者要求的真實日程變更由Chat執行；建立request觸發真Actions，固定SHA讀result；確認來源production、API/DOM/hash/顯示值一致。使用者手機確認後才切readonly；保留原localStorage bytes及legacy入口／匯出說明。最後執行OpenCode fallback匯出和授權Pages發布，離線打開可見正確備援日期；這是獨立結果。
- [ ] **6. 更新正式smoke與交付。** 舊slots「可編輯」assert僅在readonly正式接受後換成「keys保存、新資料優先」；不刪food/eaten/五卡/觸控/溢出assert。生成首頁由`--prod --itinerary-mode readonly`產生，按核准release提交；Chat記錄已讀新規則commit。用 `verification-before-completion`核對證據，再由Subagent-driven完成whole-branch review與整合收尾。
- [ ] **7. commit。** 文件變更逐路徑add；`git commit -m "docs: document itinerary editing and verified release"`。正式生成輸出與fallback應另有具來源/日期的release commit；缺發布前置時不假寫release完成。

## 完成判準

工程候選完成：A/B/C1–2及C3步驟1–3的可重現測試均通過。正式切換完成：C3步驟4–6有真實證據。兩個里程碑分開回報，不能拿單純workflow綠燈或本地fixture截圖代替旅途中可用。
