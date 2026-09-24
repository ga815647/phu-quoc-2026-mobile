# 裝置 localStorage 匯出／匯入（一次性，可保存可匯入）

> 鍵：`phq-v3-slots`（暫排）、`phq-v3-food-eaten`（吃過）、舊鍵 `phq-v2-slots`／`phq-v2-food-eaten`（備份）。
> 同源政策：localStorage 屬於「原裝置＋原瀏覽器＋正式站來源」，
> 只能在該組合下讀寫；換裝置、換瀏覽器、開其他網址都讀不到。
> 伺服器拿不到這些資料；以下只產生**可保存的文字檔**。使用者已明確放棄保留（2026-09-26）；本文件保留作換裝置手動重設參考。

## 匯出（原裝置、原瀏覽器、開啟正式站頁面內執行）

1. 在原裝置用原瀏覽器開啟正式站任一頁（須是正式站來源下執行，別處貼碼讀不到）。
2. 桌面瀏覽器：F12／開發者工具→Console，貼上執行：

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

3. 手機／平板（多無開發者工具）：改用人工承接（見下），不要貼來路書籤碼。
4. 把 `phq-localstate-2026.json` 存到私人位置（不進公開 repo、不貼 Chat）。
   驗證：用記事本開啟，內有 `phq-v3-slots`／`phq-v3-food-eaten` 鍵即成功；
   值為 `null` 表示該裝置本來就沒有該紀錄（誠實空值，不是失敗）。

## 匯入（新裝置、新瀏覽器、正式站頁面內執行）

1. 把 JSON 檔傳到新裝置（私人傳輸）。
2. 新裝置瀏覽器開正式站→開發者工具 Console 貼上執行（將 `PASTE_JSON_HERE` 換成檔內容）：

```js
((backup) => {
  const keys = ['phq-v3-slots','phq-v3-food-eaten','phq-v2-slots','phq-v2-food-eaten'];
  keys.forEach(k => { if (backup[k] !== null && backup[k] !== undefined) localStorage.setItem(k, backup[k]); });
  return '匯入完成，請重整頁面確認暫排／吃過已出現';
})(PASTE_JSON_HERE);
```

3. 重整頁面：暫排行程下拉與吃過按鈕狀態出現即成功。

## 人工承接（無開發者工具時；如實手動搬運，不偽裝自動同步）

- 暫排：在原裝置把 10/12–14 暫排下拉逐日截圖；新裝置照圖重選。
- 吃過：在原裝置美食區篩選「已吃」→逐項截圖店名；新裝置逐項點「已吃」。

## 保存到 Notion 的對照

- 上述 JSON 或截圖是**一次性搬運工件**，不常駐同步；真正要留的結論
  （如「10/12 暫定 Cable」「已吃前三名單」）由使用者口述，經 Chat 寫入
  私人準備頁對應段落（每日索引／選定摘要），並讀回確認。
- 裝置資料已由使用者明確放棄保留（2026-09-26）；換裝置手動重設，不宣稱已搬遷。
