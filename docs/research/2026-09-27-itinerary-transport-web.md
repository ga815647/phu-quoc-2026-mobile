# 六天交通查核：增量證據

查閱日2026-09-27；explore唯讀研究回傳、主代理整理。先前基線為commit `c56159f7e07e359f4099988c117e6a804f83682b` 的 `docs/research/2026-09-26-transport-evidence.md`（主代理已git show讀取）。本報告不取代正式交通資料，不改已確認OnBird接送。

## 支持的事實與侷限

| 來源 | 本次證據層級與原文 | 對安排的影響 |
|---|---|---|
| [Grab PQC airport](https://www.grab.com/global/airport-rides/phu-quoc-international-airport) | explore直接讀取；列GrabCar7、"Available services could differ across Vietnam"、"request a ride on demand or schedule your airport transfer in advance" | 可優先用Grab，不能推出偏遠／晚間有司機或預約已成立 |
| 同頁 | city centre至airport約15分鐘、約10km | 區域級概述，不是Cosy門口pin或現場車程；不得直接拿來算飯店出發時刻 |
| [VinBus官方](https://vinbus.vn/en)／[即時路線](https://maps.vinbus.vn/) | 直接讀取官網："Search for routes and stops conveniently"；靜態回應未提供富國島逐站當日班表 | 使用時核對方向、上車站、末班與轉乘；不是Cosy門口接駁保證 |
| [VinWonders巴士指南](https://vinwonders.com/en/wonderpedia/news/guide-to-taking-the-bus-to-vinwonders-phu-quoc/) | 直接讀取、文標2025-12-09："No VinBus route runs directly from Phu Quoc Airport to VinWonders"；17／19到GrandWorld再轉內部線；班次可能變動 | 公車方案須計入走到站、候車、兩段車程與转乘；不能套直達汽車時間 |
| 同頁／既有9/26報告 | 2026-01-01公共17/19/20一般乘客收費，符合票券條件可免費；表格亦有04:05–04:05等歧義 | 不採行銷文章為末班保證。與舊頁免費／時段說法衝突，臨行以營運者路線系統確認 |
| [Vietjet check-in](https://www.vietjetair.com/en/pages/how-to-check-in-1685510691899) | **官方搜尋摘要，正文fetch無可讀內容**：Vietnam等出發的國際線櫃檯開放3小時前、關閉50分鐘前（Japan/Korea/India例外） | VJ844 08:20減50分鐘=07:30是櫃檯截止推算，不是建議到機場時間 |
| [Vietjet GDS](https://www.vietjetair.com/en/pages/gds-interline-1619077007317) | **官方搜尋摘要，未直接讀取正文**：50–60分鐘截止，詳主check-in頁 | PQC本航班是否特殊60分鐘未確認；07:20亦僅保守截止參考，不能當抵達目標 |

## 精確起點未核實

本輪未取得Cosy自家可驗證入口pin。公開列表門牌有衝突：
- [Agoda物業頁](https://www.agoda.com/cosy-bungalow/hotel/phu-quoc-island-vn.html) 搜尋結果列71B Trần Hưng Đạo；與既有卡片錨點相符。
- [Expedia物業頁](https://www.expedia.com/Phu-Quoc-Hotels-Cosy-Bungalow-Phu-Quoc.h14874301.Hotel-Information)／[Tripadvisor](https://www.tripadvisor.com/Hotel_Review-g1184679-d9750350-Reviews-Cosy_Bungalow_Phu_Quoc-Duong_Dong_Phu_Quoc_Island_Kien_Giang_Province.html)搜尋結果列81B。

以上搜尋由主代理重查確認「來源互相矛盾」，不能用多數票改住宿位置。飯店入口、最近VinBus站、Cosy→機場／北島／纜車雙向routing ETA仍未核實。不可利用距離÷自定時速假造估計。

## 與前次研究的差異

- 9/26 SunWorld官方已支持陽東中心→SunsetTown約40分的**區域級去程**，本輪沒有新的精確Cosy雙向ETA。保留原結論，避免又把有效基線說成全無來源。
- 北島要經GrandWorld轉車、免費說法衝突、偏遠回接與KingKong分店晚間時段未核實，皆是既有未知；本輪未假稱已解決。
- 新增Grab官方PQC頁及Vietjet截止摘要，但Vietjet正文仍未取得，證據信心不同。

## 六日安排採用規則

1. OnBird照既有Cosy業者往返，精確接車時間等業者通知；不自行拆Grab。
2. VinWonders／Safari以Grab優先，出發前核對實際回接；VinBus是有條件備案，未核對當日站與末班前不當已安排。
3. 纜車日沿用南島區域40分作粗背景，門到門、等待／步行另列未知。SunsetTown晚間只有回程可用才留；AnThoi先刪減。
4. 海星維持原船／原車回、兒童救生衣與成行條件；本研究不支持把它改成單程Grab。
5. 10/15不繞早餐。國際線建議較早到機場的目標屬規劃緩衝，不能與櫃檯截止混為一談；出門時刻待入口pin、車程及接車确认。

來源查閱日不是現場驗證或旅日保證；超過30天使用本報告標「出發前重查」。未取得的數字留待核實，不將缺證据包裝成已完成交通估時。
