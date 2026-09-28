# Domain documentation

本 repo 採 single-context：術語表為根目錄 `CONTEXT.md`。

- 設計／訪談使用 domain-modeling；先讀現有詞義，再對照程式與內容契約。
- 確認的術語及歧義消除即時記入 CONTEXT；它是詞彙表，不是規格或實作計畫。
- 只有難以逆轉、缺背景會令人困惑、且確有取捨的已確認決策，才考慮寫入 `docs/adr/`；有需要時才建立。
- 行為授權與資料欄位依 `CONTENT_CONTRACT.md`，改版可改範圍依 `docs/ops/REDESIGN_SCOPE.md`；詞彙表不擴張權限。
- Wayfinder 決策答案放子議題 resolution comment；術語表與 ADR 引用該決策，不另寫矛盾版本。
