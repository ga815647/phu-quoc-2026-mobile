# 富國島主要路線交通估時與晚間回程：公開證據基線

查核日：**2026-09-26**；旅期：2026-10-10～15。這是研究筆記，不是已核實的 10 月車程、預訂或正式內容變更。只查公開 repo 投影與營運者／服務商公開頁面，沒有讀取正式資料庫或私人 Notion。來源頁的**刊登日期**另列；今日能讀到頁面，不等於今日現場交通已驗證。

## 證據分級與讀法

- **A：業者明載的區域級時間**：可作粗基線，不能直接套在 Cosy 71B 門口、特定園區入口或反向晚間路況。以下沒有任何現場實測車程。
- **M：特定 pin／模式／方向／查詢時段的地圖 routing ETA**：本輪**未取得可重現數值**，全部保留未知；不拿「距離 ÷ 自訂時速」、巴士班次或卡片預定時段代替 M。
- **U：未知**：含出發點接車等待、返程派車、塞車、園區入口與轉乘步行、排隊／檢票、班次實際運行及站點。要將來補 M，記錄精確起終點 pin、Google Maps／其他路由器、車種、查詢時間與出發／抵達時段、方向、截圖或可重現連結；晚間與白天分開查，等車與入場緩衝另列。

現行公開卡片 [`data/cards.json`](../../data/cards.json) 的 `safari/vinwonders/cable/starfish` 均為 `evidence_as_of=2026-09-20`；[`data/points.json`](../../data/points.json) 的 `grand-world/sunset-town/starfish` 為 `2026-08-29`。這些是既有卡／點證據日期，**不是 09-26 交通實測，也不是旅期現況**。Cosy 暫以卡片的「Cosy Bungalow／71B Trần Hưng Đạo」為出發／回房錨點；DD 指 Dương Đông 區域，不能把兩者混成同一個 pin。`08:30–08:45` 出發、`10:30–10:45` 抵達之類卡片窗口是計畫／緩衝，**不能相減宣稱車程**。[C1]

## 路線基線（直達汽車優先；每一方向分開）

| 分段 | 已有業者明載時間／性質 | 尚不能聲稱的事、執行上的分拆 |
|---|---|---|
| Cosy／DD → **Grand World**；Grand World → Cosy／DD（晚間） | VinWonders 官方 [V1] 說陽東至 Grand World 有公共線 17/19，於 T2 下車；**沒有 Cosy 直達汽車車程**。北島 Vinpearl 園區官方 [V3] 的「約 40–45 分」指**機場→Vinpearl 區**，不是本段。 | 雙向直達車的 M=U；晚間叫車／車流與上車點 U。若搭 VinBus，需拆 Cosy→確切站點、候車、17/19→T2、T2→活動點、返程各段；不是 door-to-door taxi ETA。V1 載夜間內部線只到 Grand World、不含 VinWonders；巴士能跑並不保證返程每一站／每個時刻可搭。[V1][V2] |
| Cosy／DD → **VinWonders**；VinWonders → Cosy／DD（正常離園／晚間） | [V1] 說市區公共線到 Grand World T2 後**再轉內部接駁**到 VinWonders；其內部線晚間運行條件隨路線變動。**無本段 Cosy 直達車明載分鐘**。 | 雙向 M=U；直達汽車接車、行車、下車到園門、檢票各自 U。VinWonders→Grand World 可走內部接駁，但等車／末班與步行需即時查；不因頁面有班表就把返 Cosy 視為已安排。[V1][C1] |
| Cosy／DD → **Safari**；Safari → Cosy／DD；Safari → Grand World（若選晚間尾段） | [V2] 明示機場／陽東至 Safari **沒有直達巴士**：先到 Grand World，換內部接駁；北島內部 Safari 線載白天時段，非晚間 Safari 回程保障。**無 Cosy 直達 Safari 或 Safari→Grand World 汽車車程分鐘**。 | 三段 M=U；Safari 偏遠，先約定回接或核對可用返程，不以「有 Grab 城市服務」推論園門即時有車。現行卡的 Gành Dầu daylight 尾段要求 retained driver／明確回接、17:00 前離；Grand World evening 是另一條可選尾段，**不能合併**。[C1][V2] |
| Cosy／DD → **Ga Ánh Dương／Sunset Town**；Sunset Town → Cosy／DD（晚間） | Sun World [S1] **明載**「陽東中心→Sunset Town 約 40 分鐘，視路況」；[S2] 另以「陽東中心**或機場**→Sunset Town 約 30–40 分鐘／20–25 km」籠統合併兩起點，基線優先採來源較明確的 S1。Ga Ánh Dương 在 Sunset Town 纜車區，非 An Thoi 漁港。[S3] | 這是 **A，區域級去程**，非 Cosy 71B→Ga Ánh Dương 門到門精確 ETA，亦非返程實測或晚間保證。兩方向 Cosy pin 的 M=U；預留叫車、行車、步行進站、QR／廁所／排隊（纜車日）為不同項。Sun World 明確建議夜晚**預先安排 taxi、核查 shuttle 或與住宿協調接送**。[S1][C1] |
| **An Thoi Market／漁港 → Sunset Town**（纜車回島後順路衛星點） | VinWonders [V4] 說漁港在 An Thoi 南端、An Thoi 市場在通往漁港的路旁；Sun World [S1] 確認 Sunset Town 也在 An Thoi 區。**未找到市場／漁港指定 pin 至 Sunset Town 的業者車程**。V4「陽東→漁港 30–40 分」不是本段。 | 市場、漁港不是同一 pin；兩者各至 Sunset Town 的 M=U，連停留／等車、兒童體力也 U。現行 `anthoi` 是可跳過衛星點，卡片 45–60 分是**市場＋港口停留窗口**，不是這段行車時間；沒時間直接 Sunset Town。[C1][V4] |

### 接駁資料的可用性與衝突

[V1]（頁面標 2025-12-09，文內稱 2026 票價）明載**自 2026-01-01 公共 17/19/20 線一般乘客收費、符合票券條件者免費，內部線免費**；[V2]（同標 2025-12-09）與較早 [V5]（2025-11-17）仍多處概稱「免費」，部分列出的線號／站名／時段也不一致。不能選一個宣稱 10 月現行票價／末班；臨行及當日看營運者 [VinBus 即時路線](https://maps.vinbus.vn/pq)／app，核對票券 QR 資格、確切站點、末班與轉乘。Sun World 的 [S4] 是 **2025-08-04** 宣傳 2025-07-07 開行的免費跨島接駁及停靠概況，不能當 2026-10 晚間回 DD 班表；[S1]（2026-03-11）也明言具體營運時段需官網出發前查。卡片以其作**回程省錢備案**且要求 T−72 查證，不是硬保證。[C1]

## 偏遠回程門檻與低強度晚間

- **海星 Rạch Vẹm／Hàm Rồng**：公開卡 [`starfish`](../../data/cards.json) 的條件為 T−1 談妥 Cosy 門到門往返 SUV／MPV、精確上船點、當日短船與兒童救生衣、**原船回＋原車回**、取消條件及 48h 現況；任一不符則不去。這是**既有計畫門檻（2026-09-20）**而非研究已訂車或現場查驗。沒有可靠的此路段開車／乘船分鐘，也沒有「到偏遠上船點再開 Grab 必有車」的一手保證。[C1] Grab 的 [G1] 列 Phu Quoc 為服務城市；[G2] 宣傳 Advance Booking，但選項以 app／地址可用性為準，且 FAQ 明載駕駛取消後需重新分派，**不能推出 Rạch Vẹm 晚間或臨時回接保證**。具體 T−1 與 T−48/24 向同一承運者確認回程車輛、船、人數／兒童尺寸、上船 pin、取消與壞天氣方案；確認不到即換日／取消，不拆為單程賭回程。
- **北島／南島夜間**：Grand World／Sunset Town 晚間回 Cosy 要在出發前確認**實際車輛或可執行的站點／末班**，主活動結束才開始叫車不等於已鎖回房時間；回程行車與等車須分開。若 21:00 是「活動結束」還是「回房」，目前產品決策尚未定義，不能倒推可行行程。[S1][V1][C1]
- **Cosy 附近低強度備案：King Kong Mart**。店家自家 [K1] 官網前端列 **141A Trần Hưng Đạo** 分店；Cosy 71B 同路名來自卡片 [C1]。因此可作「若孩子尚有精神、先回 Cosy 後再看是否近處逛超市」**候選**，但兩門牌不是精確步行 pin／分鐘；前端沒有可直接引用的該店 **2026-10 晚間營業確認或步行時間**，不要以搜尋結果／第三方 22:00 或 23:00 作保證。店家官方 Facebook 搜尋摘要可見不同分店／時段，未作可驗證現場確認；臨行核實分店位置、當天關門與孩子狀態，不適合從北／南島專程繞去。[K1][C1]

## 需要補的最小查核（不阻塞此基線）

1. T−72／T−1 以**同一對精確 pin**分別查 Cosy→VinWonders、Safari、Grand World、Ga Ánh Dương；返程以**實際晚間時段**反查；An Thoi 市場與漁港各自到 Sunset Town，保存模式、方向、日期與 ETA。這會產生 **M（地圖 routing 估時）**，仍非即時路況保證。本輪未取得 M，不填空白假數字。
2. 以當日 app／園方／司機核對能否在 VinWonders／Safari／Grand World／Sunset Town 上車、派車等待、最後可用接駁與回接費用；遠端海星只接受預約往返鏈。等車、排隊、步行、餐飲、孩子休息需各自留欄，不能包進「車程」。
3. 別把 [V3] 機場→Vinpearl 區 40–45 分、[V4] 陽東→漁港 30–40 分、[S1] 陽東中心→Sunset Town 約 40 分移植成不同起點／終點／方向的確定值；高可信來源也只能證明它實際寫的段落。

## 來源索引（本輪均於 2026-09-26 查閱）

| 代號 | 一手／公開來源及其頁面日期 | 可支持的範圍／侷限 |
|---|---|---|
| C1 | 本 repo [`data/cards.json`](../../data/cards.json)、[`data/points.json`](../../data/points.json)；卡證據 2026-09-20／點證據 2026-08-29 | 既有行程與門檻，非車程量測；`anthoi` optional。 |
| S1 | [Sun World：到 Sunset Town 交通指南](https://sunworld.vn/en/hon-thom/transportation/huong-dan-di-chuyen-den-sunset-town-phu-quoc-de-dang-va-thuan-tien-nhat-17630)，**2026-03-11** | 陽東中心→Sunset Town 約 40 分、路況條件；夜間應預約／查接駁。 |
| S2 | [Sun World：Sunset Town 攝影地點／交通](https://sunworld.vn/en/hon-thom/travel-guide/top-10-beautiful-photo-spots-in-sunset-town-phu-quoc-most-outstanding-17006)，**2026-02-17** | 合併「陽東中心或機場」起點的 30–40 分，不可當特定 Cosy ETA。 |
| S3 | [Sun World Hon Thom 官方園區入口／站名](https://sunworld.vn/en/hon-thom)，頁面未標文章日期 | 站名／區域定位參照；不提供 Cosy 車程。 |
| S4 | [Sun World：免費跨島巴士介紹](https://sunworld.vn/en/hon-thom/sunworld-news/60%20free%20bus%20trips%20every%20day%20bring%20tourists%20from%20all%20over%20Ngoc%20Island%20to%20Sun%20World%20Hon%20Thom)，**2025-08-04** | 舊服務介紹，不是 2026-10 末班。 |
| V1 | [VinWonders：到 VinWonders 巴士指南](https://vinwonders.com/en/wonderpedia/news/guide-to-taking-the-bus-to-vinwonders-phu-quoc/)，**2025-12-09**（頁面含 2026 費率更新，更新實際日期未另標） | 公共線到 Grand World 再轉園內接駁；2026 票價說法；班表需即時查。 |
| V2 | [VinWonders：Safari 巴士指南](https://vinwonders.com/en/wonderpedia/news/bus-to-vinpearl-safari-phu-quoc/)，**2025-12-09** | Safari 轉乘、路線與部分晚間限制；免費說法與 V1 有矛盾。 |
| V3 | [VinWonders：Vinpearl Phu Quoc 指南](https://vinwonders.com/en/wonderpedia/news/vinpearl-phu-quoc/)，**2025-12-02** | 約 40–45 分為機場→Vinpearl 區，不能套 Cosy。頁內 FAQ 又稱 45–60 分，自身亦非唯一時段。 |
| V4 | [VinWonders：An Thoi 漁港](https://vinwonders.com/en/wonderpedia/news/an-thoi-harbour-phu-quoc/)，**2025-08-15** | 市場在港口路旁；陽東→港口說法自身距離 25／30 km 不一，不能套港口→Sunset Town。 |
| V5 | [VinWonders：北島 VinBus 2026 班表](https://vinwonders.com/en/wonderpedia/news/vinbus-phu-quoc/)，**2025-11-17** | 舊頁稱全免費；與 V1 2026 更新衝突。 |
| G1 | [Grab 官方服務城市](https://www.grab.com/vn/en/locations/)，頁面未標日期 | 列 Phu Quoc；不是個別 pin／時段供車證明。 |
| G2 | [Grab Vietnam Advance Booking](https://www.grab.com/vn/en/transport/advance-booking/)，頁面未標日期 | 預訂產品與取消／重新分派條款；非偏遠返程承諾。 |
| K1 | [Kingkong Mart 官方網站](https://www.kingkongmart.vn/?page=homepage)，頁面未標日期；前端 JS 載入後分店欄顯示 141A Trần Hưng Đạo | 店家自列地址；本輪沒有可靠的 10 月營業或 Cosy 步行 ETA。 |

**交接定位**：本基線支持「把夜間與偏遠回程當作必備條件」及「陽東到南島約 40 分的區域級起點」；不支持把每段交通填成單一確定數字或把 Grab／舊接駁班表當保證。無正式資料、卡片、訂單或網站變更。
