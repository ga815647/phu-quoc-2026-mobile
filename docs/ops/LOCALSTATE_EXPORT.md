# 裝置 localStorage 匯出／匯入（一次性，可保存可匯入）

> 鍵：`phq-v3-slots`（暫排）、`phq-v3-food-eaten`（吃過）、舊鍵 `phq-v2-slots`／`phq-v2-food-eaten`（備份）。
> 伺服器拿不到這些資料；以下步驟產生**可保存的文字檔**，換裝置可匯入。
> 本輪未執行（需使用者裝置），只提供步驟；未搬遷亦未放棄。

## 匯出（舊裝置，連網開正式站一次即可）

1. 在舊裝置用瀏覽器開啟正式站任一頁。
2. 開啟開發者工具 Console（手機：用 `about:blank` 貼下碼書籤方式，或借桌面版同瀏覽器同步後操作），貼上執行：

```js
(() => {
  const keys = ['phq-v3-slots','phq-v3-food-eaten','phq-v2-slots','phq-v2-food-eaten'];
  const out = {};
  keys.forEach(k => { out[k] = localStorage.getItem(k); });
  const blob = new Blob([JSON.stringify(out, null, 1)], {type: 'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'phq-localstate-2026.json';
  a.click();
  return '匯出觸發下載：phq-localstate-2026.json';
})();
```

3. 把 `phq-localstate-2026.json` 存到私人位置（不進公開 repo、不貼 Chat）。
   驗證：用記事本開啟，內有 `phq-v3-slots`／`phq-v3-food-eaten` 鍵即成功；
   值為 `null` 表示該裝置本來就沒有該紀錄（誠實空值，不是失敗）。

## 匯入（新裝置）

1. 把 JSON 檔傳到新裝置（私人傳輸）。
2. 開正式站→ Console 貼上執行（將 `PASTE_JSON_HERE` 換成檔內容）：

```js
((backup) => {
  const keys = ['phq-v3-slots','phq-v3-food-eaten','phq-v2-slots','phq-v2-food-eaten'];
  keys.forEach(k => { if (backup[k] !== null && backup[k] !== undefined) localStorage.setItem(k, backup[k]); });
  return '匯入完成，請重整頁面確認暫排／吃過已出現';
})(PASTE_JSON_HERE);
```

3. 重整頁面：暫排行程下拉與吃過按鈕狀態出現即成功。

## 免 Console 替代（無開發者工具時）

- 暫排：逐日截圖暫排下拉（10/12–14 共 3 格）；新裝置照圖重選（3 次點擊）。
- 吃過：在美食區篩選「已吃」→逐項截圖店名；新裝置逐項點「已吃」。
- 兩者皆為如實手動搬運，不偽裝自動同步。
