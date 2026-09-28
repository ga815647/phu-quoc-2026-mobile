# 六天行程工程候選驗收

日期：2026-09-27。分支 `feat/itinerary-chat-ci`，產品程式驗收 commit `2d707fc`。

## 結論

A 資料層、B API／匯出／閱讀器、C 請求／瀏覽驗站／結果發布的**本地工程候選**已完成。每 task 經獨立審查；整體分支審查發現的更新與顯示一致性缺口已修正，最後定向複核通過。

正式內容初始化、Neon migration／Function 部署、真實 GitHub Actions、Chat 正式更新讀回、手機正式站接受與公開預覽尚未完成。此頁不把本機測試或 fake GitHub 結果當成正式生效證據。

## 新鮮收尾驗證（控制者親跑）

測試環境：隔離 worktree、user-space PostgreSQL 18.6、私有 Unix socket、Node.js24、Playwright1.55.0。沒有寫入遠端資料庫。

| 命令 | 結果 |
|---|---|
| `python3 -m unittest discover -s tools/verify -p 'test_itinerary_*.py'` | 51 tests，OK |
| `node --test functions/test-itinerary-response.mjs tools/verify/test_itinerary_reader.mjs tools/verify/test_site_check_browser.mjs tools/verify/test_site_check_contract.mjs tools/verify/test_site_check_publish.mjs` | 45 tests，45 pass，0 fail／skip |
| `node tools/verify/itinerary_e2e_candidate.mjs` | PG18 rollback update/audit → public view/export → generated candidate → Chromium verifier → fake GitHub immutable result PASS |
| `node tools/verify/itinerary_reader_browser.mjs --site /tmp/opencode/phq-itinerary-candidate` | six days／Today／fallback／races／storage／XSS／readonly／cards／eaten／build／mobile PASS |
| `python3 tools/verify/journey_collapse_verify.py` | TOTAL FAIL 0 |
| `python3 tools/verify/transport_grouping_verify.py` | TOTAL FAIL 0 |
| `git diff --check` | exit 0 |

C2 實作者另外完成 workflow YAML assertions／actionlint，見對應 task 紀錄。舊 `candidate_ui_accept.py` 綁定歷史端點，本輪沒有宣稱其通過；舊正式 Neon 固定筆數 suite 也未在合成測試資料上冒充通過。

## 實作與審查索引

| 任務 | 主要提交 | 狀態 |
|---|---|---|
| A1 schema／projection | `562c823`、`e997f92` | task review 通過；後續一致性修正在末三筆 |
| A2 atomic update | `0cac542`、`6f26b33` | task review 通過 |
| A3 ACL／migration lifecycle | `60ef962` | task review 通過，本機 production-shaped schema |
| B1 endpoint／export | `fc7e0dc`、`d5a4e12` | 統一 canonical payload，task review 通過 |
| B2 reader | `141ce1e`、`05a135e`、`a2d0b03` | task review 通過 |
| C1 request | `eb85826`、`0f9d49e` | task review 通過 |
| C2 verifier／publisher | `7cd8483`、`04128fb` | task review 通過 |
| C3 docs／local integration | `54520d5`、`7d977ae`、`ee97af3` | 本機工程範圍通過；發布步驟4–6仍待前置 |
| 整體審查修正 | `4b141ea`、`bf85133`、`2d707fc` | 非法安排／OnBird核心／Starfish分支與回程／可見備案及五卡導航已補測，定向複核通過 |

## 控制者裁定與代價（依作出順序）

1. 依 harness 限制使用預設 subagent model；未擅自選模型。代價：執行成本／速度可能不同。
2. 將 A1–C3 派工文字轉為數字 scratch 標題供工具抽取，原核准計畫名稱保留。代價：可能抽取錯位，因此逐份檢查。
3. Docker 無權限，使用 user-space PG18 私有 socket。代價：Neon-specific ownership／角色仍須隔離分支驗證。
4. 既有驗收腳本有固定端點／路徑，不假稱支援不存在的 flags。代價：舊完整腳本不算本輪通過；由新候選測試覆蓋相關行為。
5. Canonical wire 遵循核准計畫的 nested `data.itinerary`；SQL 與 API／export 一起對齊。代價：本機 fixture/hash 需重算，尚無公開相容性影響。
6. `refs.bases` 只帶有使用的 `{id,ref:{type,id}}` 映射。代價：若消費者有其他需要，須顯式改公開契約。
7. 完整六日 `itinerary.json` 原子替換；舊 JSON 全目錄不是資料庫式原子交易。代價：發布一定要等完整 export 成功，不能發布中途失敗的輸出。
8. SQL 與 reader 同守五主卡、meal=food/pool。代價：以前寬鬆接受的無效合成形狀改為拒絕。
9. OnBird 初始化受保護活動核心，鎖定角色／時段但不凍結整日餐飲。代價：正式核心須由已確認安排初始化，不可猜時間。
10. Starfish 初始化經審閱的機器條件與回程限制，缺設定不能選用。代價：其條件未審定前保持不可選，其他預設可用。
11. 整體修正後仍發現會影響後續工作的缺口，因此追加限縮修正而不宣稱完成。代價：增加修正／複核時間。
12. SQL／JS 的條件鍵採同樣逐段語義；每個可執行 Starfish 備案皆受回程規則約束。代價：漏条件的旧形狀會被拒絕。
13. 任一非空主卡都必須有實際主線活動段，不因 light／arrival 等分類免驗。代價：只有主卡標題的空安排須補齊或設為 NULL。

## 下一階段的輸入

- 六天實際順序、餐廳、估時與來源，以及 OnBird 保護核心／Starfish 條件映射。
- 視覺稿、外部可瀏覽的預覽發布範圍。
- 指定 Neon 隔離分支資格驗證與 production migration／Function／Pages 發布授權。
- 真實 Chat 操作→GitHub 請求→Actions 結果→手機驗收，通過後才撤下舊手機行程編輯。

操作手冊：`CHAT_ITINERARY_RUNBOOK.md`；資料庫部署手冊：`ITINERARY_DB_RUNBOOK.md`。規則與工程分支尚未推送時，Chat 從遠端 main 無法讀到新版；發布與 Chat 已讀要另外留證據。
