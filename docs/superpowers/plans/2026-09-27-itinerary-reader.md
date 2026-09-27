# Itinerary Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用同一公開投影驅動 API、JSON 備援、六天畫面與「今天」摘要。

**Architecture:** API 只新增固定 itinerary 端點；Python exporter 讀同一 view。將新行程載入／渲染放獨立 ES module，生成器僅提供容器、資產與明確模式；不重構現有美食／交通等無關模組。

**Tech Stack:** Node.js 24／pg、Python 3／psycopg2、原生 ES modules、Node test、Playwright 1.55.0。

**Spec:** `../specs/2026-09-27-itinerary-chat-ci-design.md`。

## Global Constraints

完整繼承 [總計畫](2026-09-27-itinerary-implementation.md#global-constraints)。`GET /api/itinerary` no-store；8 秒超時；整包六日替換；production 模式固定正式 Function；公開指紋與 build ID 分開；既有 localStorage 不刪。

## Review Focus

- API 還沒 migration／六日未初始化：502/503 固定錯誤，不能 200 空計畫；B1。
- 段落文字含 HTML：當文字呈現，不執行標籤；B2。
- 兩次刷新回應反序：只顯示最後請求結果；B2。
- 午夜／未知估時／localStorage 拒絕存取：仍正確顯示；B2。
- 既有 Today/slots 程式覆蓋新畫面、API 小端點拼入新日程：B2。

## 檔案責任

- `functions/phq-readonly-api.mjs`：固定路由與 response；不擴充任意查詢。
- 新 `functions/itinerary-response.mjs`：可依賴注入 query 的 endpoint handler，獨立測試而不連 DB。
- 新 `functions/test-itinerary-response.mjs`：Node unit tests。
- 新 `tools/itinerary_export.py`：單 view fetch 與 JSON envelope。
- 修改 `tools/export_json.py`：Neon 正常匯出時輸出 itinerary；SQLite 明示不支援新日程。
- 新 `tools/verify/test_itinerary_export.py`：Python unit tests。
- 新 `tools/itinerary-reader.mjs`：驗證、載入、render、初始化，無 Node runtime dependency。
- 修改 `tools/build_site.py`：模式、容器、資產複製、build digest；`tools/site.css` 僅必要狀態／可讀列表樣式。
- 新 `tools/verify/test_itinerary_reader.mjs`、`itinerary_reader_browser.mjs`、`fixtures/itinerary-envelope.json`。

### Task B1：固定 GET 與同源備援

**Consumes:** A 的 `public.itinerary_public(itinerary_id,payload,content_revision)`；總計畫 data/meta shape。

**Produces:**
- `itineraryResponse(query, meta, cors) -> Promise<Response>`；query=`async(sql,params)=>({rows})`。
- Python `read_itinerary(fetch, source, environment, exported_at) -> dict`，fetch 回 row dictionaries。
- API 單 itinerary object（不是 array）；JSON backup 同 shape。

- [ ] **1. 寫 failing response/export tests。**

```javascript
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {itineraryResponse} from './itinerary-response.mjs';
test('empty initialization is not a successful itinerary', async () => {
  const r = await itineraryResponse(async () => ({rows:[]}),
    {source:'neon-test',environment:'candidate',fetched_at:'2026-09-27T00:00:00Z'}, {});
  assert.equal(r.status,503);
  assert.equal(r.headers.get('cache-control'),'no-store');
  assert.equal((await r.json()).error.code,'ITINERARY_UNAVAILABLE');
});
```

```python
import unittest
from tools.itinerary_export import read_itinerary

class ExportTests(unittest.TestCase):
    def test_missing_projection_fails_instead_of_old_snapshot(self):
        with self.assertRaisesRegex(ValueError, 'ITINERARY_UNAVAILABLE'):
            read_itinerary(lambda sql: [], 'neon-test', 'candidate', '2026-09-27T00:00:00Z')
```

- [ ] **2. 執行 RED。** `node --test functions/test-itinerary-response.mjs` 與 `python3 -m unittest discover -s tools/verify -p test_itinerary_export.py -v`；預期缺新 module。
- [ ] **3. 寫 endpoint／export helper。** 單 statement `SELECT payload,content_revision FROM public.itinerary_public WHERE itinerary_id=$1`；固定 ID 傳參。row 缺失或 days 不是六日→503；DB exception→502 UPSTREAM_DB；回應不含 error detail。核心組合：

```javascript
return new Response(JSON.stringify({data: row.payload, meta: {
  ...meta, schema_version: 1, content_revision: row.content_revision
}}), {status: 200, headers:{'Content-Type':'application/json; charset=utf-8',
  ...cors, 'Cache-Control':'no-store'}});
```

在 API 現有 route switch 增 itinerary，使用注入 `pool.query.bind(pool)`；既有 routes 不改 cache。export helper 用固定 SQL 字面 ID；`exported_at` 不進 payload/hash；先取得並驗證 itinerary，再開始覆寫任何 output JSON，以免缺 view 時已部分匯出。新 JSON 以 UTF-8 tempfile+replace 寫出。SQLite archive 模式不製造 itinerary，CLI 輸出 `itinerary unsupported for sqlite archive`，新候選 reader 拒絕缺檔。不得 broad except 後把舊 itinerary 當最新。
- [ ] **4. 加 contract tests。** 以同一 fixture 比 API data/meta.content_revision 與 exporter 完全相同；改 fetched_at 不改 hash；GET 成功 no-store、POST405、無 row503、db error502 fixed string、ro 舊 endpoints 不回歸。隔離整合追加 `/api/itinerary` 到現有 test harness，舊表 counts 如與隔離來源不同先解釋 seed 差異，不任意改正式期望。
- [ ] **5. GREEN／commit。** 上述兩命令 PASS；隔離庫 `PHQ_META_SOURCE=neon-test PHQ_META_ENV=candidate node --test functions/test-local-api.mjs`（ro DSN 環境注入，不輸出）；`git add functions/phq-readonly-api.mjs functions/itinerary-response.mjs functions/test-itinerary-response.mjs functions/test-local-api.mjs tools/itinerary_export.py tools/export_json.py tools/verify/test_itinerary_export.py`；`git commit -m "feat: expose and export consistent itinerary projection"`。

### Task B2：六日 reader、今天摘要及穩定 DOM

**Consumes:** B1 envelope；既有 generator `build_itinerary_days_html`／`renderToday`／localStorage v3；總計畫 DOM 契約。

**Produces:**
- `validateEnvelope(value) -> envelope` 或 throw Error('INVALID_ITINERARY')。
- `loadItinerary({apiUrl,fallbackUrl,fetchImpl=fetch,timeoutMs=8000}) -> Promise<{envelope,mode:'live'|'fallback'}>`。
- `renderItinerary(root,loaded) -> void`，以 DocumentFragment 一次 replaceChildren。
- `mountItinerary({root,todayRoot,refreshButton,apiUrl,fallbackUrl,fetchImpl=fetch,now=()=>new Date()}) -> {refresh:async()=>void,destroy:()=>void}`。
- generator 新 `--itinerary-mode legacy|candidate|readonly`，預設 legacy；新模式不得靜默套用到 production。

- [ ] **1. 建立 fixture 與 failing unit/browser tests。** 用 A 隔離投影導出六日合成 fixture，refs name 顯示「測試店家」，不是正式行程。測試載入舊 schema、六日缺一、重複 day ID、無效 reference、live failure→backup，backup 也無效時回明確 unavailable。

```javascript
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadItinerary} from '../itinerary-reader.mjs';
import {readFile} from 'node:fs/promises';
const fixture = JSON.parse(await readFile(new URL('./fixtures/itinerary-envelope.json',import.meta.url)));
test('failed live read uses entire dated backup',async()=>{
 const seen=[];
 const r=await loadItinerary({apiUrl:'https://api.test/api/itinerary',fallbackUrl:'https://site.test/data/itinerary.json',
  fetchImpl:async url=>{seen.push(url);if(seen.length===1)throw Error('offline');return new Response(JSON.stringify(fixture));}});
 assert.equal(r.mode,'fallback');
 assert.deepEqual(r.envelope.data.days,fixture.data.days);
});
```

- [ ] **2. RED。** `node --test tools/verify/test_itinerary_reader.mjs`；預期 module 不存在。
- [ ] **3. 寫 load／render。** AbortController 限 8 秒；fetch response.ok/schema/hashes/refs 驗證；更新單一六日 view model，不讀 `/api/foods` 回填日程。已顯示內容在刷新失敗時可保留，但清楚標 stale／未更新，不能仍標最新。使用 generation counter 丟棄舊結果：

```javascript
let generation=0;
async function refresh(){
 const mine=++generation;
 const loaded=await loadItinerary({apiUrl,fallbackUrl,fetchImpl});
 if(mine!==generation)return;
 renderItinerary(root,loaded);
}
```

DOM 全部 textContent／createElement，URL 只從已核准 maps_query 編碼產生 Google Maps search，card link 只用 allowlist slug。餐飲 alternatives 用 details 收合；unknown duration 顯示「待估」，不以0相加；time day_offset=1 顯示「次日」，timezone 用 Intl 明示。顯示來源、版本摘要、exported_at、最後讀取時間及 refresh。正確填總計畫所有 DOM hooks；hook 僅測試識別，visible text 必須來自同 view model。
- [ ] **4. 接 generator，守住既有狀態。** candidate 模式保留舊編輯區並標「舊本機暫排」，新行程區使用獨立容器；readonly 才不生成舊編輯控制。`renderToday` 新模式只從已載入 view model 選越南日期，不讀 slots、不寫舊 Today 硬編碼 map。旧 handler 對 resetSlots 元素缺失先 guard，food/eaten 保持；新模組不碰 localStorage。reader asset 複製到輸出 `assets/itinerary-reader.mjs`。

build digest 用 SHA256：按路徑排序串接 `build_site.py/site.css/itinerary-reader.mjs` 的 UTF-8 bytes 與 mode；產出 `site-version.json={schema_version:1,build_id:"sha256:..."}`，html data-site-build 同值；旅行 JSON 不混入程式 digest。源檔消失報 build error，不輸出混版。
- [ ] **5. Browser cases。** 用 Playwright route fixture，不需真 DB：切六日可見正確活動／餐飲；今天日期指定 10/12 越南時間；seed localStorage slots=`starfish` 但新計畫 cable，Today 顯示 cable、舊 keys bytes 不變；拒絕 Storage 仍可看行程。延遲第一個 API response，第二個先回，確認最後維持第二個。文字含 `<img onerror=...>` 不執行；水平溢出≤1px、觸控≥41px、五卡連結、吃過持久化。跨午夜 next-day、未知估時、fallback 日期及來源各測 visible text。build metadata 與 DOM 同值。
- [ ] **6. GREEN／commit。** `node --test tools/verify/test_itinerary_reader.mjs`；`python3 tools/build_site.py --api-base http://localhost:8000/mock-api --out-dir /tmp/opencode/phq-itinerary-candidate --itinerary-mode candidate`；`node tools/verify/itinerary_reader_browser.mjs --site /tmp/opencode/phq-itinerary-candidate`（腳本自己開 loopback static server、route mock、finally 關閉）。PASS 後只 add 本 task 七個原始檔／fixtures，不 add 根生成頁；commit=`feat: add consistent six-day itinerary reader`。

## 交付邊界

B 完成是候選 reader 可驗收，視覺僅沿用既有樣式以驗資料接線。正式 UI 仍需已接受視覺稿；不因 readonly flag 可用就切換首頁。C2 依穩定 hooks 可開發 browser verifier。
