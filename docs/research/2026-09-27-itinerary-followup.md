# 第二輪定向查核與A預覽內容修訂

查閱日2026-09-27。兩組explore查官網與店家，主代理跟進原始HTML／圖片，並直接讀回餐廳官網。

## 突破：HonThom現行營運公告可讀

入口：[Sun World Hon Thom](https://sunworld.vn/en/hon-thom)。官方頁題為「Sun World Hon Thom Operating Schedule from July 20th」。explore提供的圖片URL有一字元轉錄錯誤，直接GET為404；主代理由**當次官網HTML抽取實際src**而非猜URL，下載1920版本並直接讀圖。

[官方原圖](https://sun-ecommerce-cdn.azureedge.net/ecommerce/service-sites/thumbnail/SunWorldHonThom/_default_upload_bucket/93371/image-thumb__93371__1920/1784288388206_6205430788619455961_g72995911113574340_57ee9ea97b8e5972d1417d21d5f785b5_1784514616.jpg)

圖片清楚標示 **Apply from: 20.07.2026**：
- Cable Car：**09:00–11:30／13:30–17:00**。
- Aquatopia Water Park：**09:45–16:45**。
- Exotica Theme Park：**09:30–16:45**。
- Beach Area：**09:30–16:45**。

官網內嵌event17734資料亦有dateForm.dateOrigin=`2026-07-20`、dateTo.dateOrigin=`2026-11-30`、status=`ONGOING`。這是公告在網站的活動日期範圍，不能推成10/13不可能臨時停駛。圖片正文沒有「最後排隊／登車」截點，因此17:00僅寫運行窗口結束，不稱保證最後登車。

**本輪修正先前未知**：不再說完全找不到當前年份纜車／Aquatopia分別時段。仍未取得10/13特定維修／天候公告或無停修保證。

規劃建議（非已訂時間）：09:30–10:00目標搭乘，避開11:30–13:30空檔；15:30開始前往返程站點，以更衣／步行／排隊保留提早緩衝。飯店出發仍依實際接車與車程設定；不把窗口相減作車程。島上午餐仍無本輪核實特定店家／套票內容，不採用2020舊文餐廳或價格。

## 住宿周邊具名晚餐候選

主代理直接GET下列第一方正文，非僅搜尋摘要：
- [The Waterfront reservation](https://thewaterfrontphuquoc.com/reservation)："66G Đường Trần Hưng Đạo, Khu 1"、"Open daily: 11:00 - 22:00"。
- [The Waterfront menu](https://thewaterfrontphuquoc.com/menu)：Chicken Schnitzel（chicken breast/fries/mixed salad）、Chicken Escalope、Bolognese、Napoletana等。

可推薦為第一晚具名候選；不是兒童套餐保證、不是已訂位、未驗證Cosy到店精確步行距離。沒有既有核定food/pool穩定ID，本輪僅預覽提案，不建立正式記錄。若路線不順或抵達晚、孩子累則就近吃。

## 仍未知且不重複猜的項目

- Cosy自家站維護中，無法解決71B／81B門牌衝突；未取得GoogleMaps確切入口pin。交通仍待實際pin／routing，不從同路名猜分鐘。
- WOW的店家社群僅搜尋摘要、目錄pluscode不足以證明可從SunsetTown步行；保留區域候選，不以「低摩擦」包裝已核實順路。
- BUP是Meyhomes候選，非纜車日預設必跑。
- Vietjet主代理再次GETcheck-in只得到JS頁殼；官方搜尋結果50／50–60分鐘摘要仍不足以核定PQC特定截止。沒有把截止當到機場目標。

## 預覽修訂範圍

只改 `preview/redesign/content.json`：將上輪DeepSea／Giraffe及其查閱日／時段衝突寫到對應園区午餐；修正Cơm tấm Nhị時段及售完敘述的證據強度；新增Waterfront候選；把上列纜車公告與建議早回程寫入10/13。A為已選方向，B保留同份草案作歷史比較；沒有變更正式首頁、Neon主表或已確認預訂。

## 发布與驗收

另在preview README補來源連結。內容定向審查指出OnBird晚餐說明先吃後散步、列表卻反向；已調整列表為先晚餐再条件式散步。本機320／390／430px六日A/B切換、同內容段數、地圖、無overflow／pageerror與44px目標檢查通過。首次執行僅因本機server未啟動而連線拒絕，啟動後重跑通過。

獨立preview發布main `7ff6879b5a0cb15d97c49cfabf243dd74176d9e9`，diff僅content.json及README；Pages run `36357667760` success。主代理公開站再次查核320／390／430px六日可見新增內容、OnBird晚餐順序、備案開啟與無水平溢出／JS錯誤，全部通過；公開content.json与本地待發布版本完整物件一致。此證據只代表草案預覽已更新，不代表Neon內容或正式首頁升版。
