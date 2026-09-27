# 六日餐飲網路查核

查閱日2026-09-27；explore唯讀查核回傳、主代理整理。來源正文、搜尋摘要與舊JSON明確分級。這是內容提案，不更新Neon的last_verified，也不代表店家已回覆當日營業。

| 候選／穩定pool key | 實際取得的證據 | 建議 |
|---|---|---|
| Cosy早餐／住宿晚餐 | [住宿官網](https://www.phuquoccosybungalow.com/)維護中；[Expedia](https://www.expedia.com/Phu-Quoc-Hotels-Cosy-Bungalow-Phu-Quoc.h14874301.Hotel-Information)搜尋摘要早餐07–10，第三方 | 房內簡單早餐可預備；不能推定住宿供晚餐或房價含早餐 |
| `bun-ken-87` | [地址目錄](https://sodiachi.com/dia-diem/bun-ken-87)87 Đ.30Tháng4、08–17；[另一餐廳指南](https://sunsetrestaurant.vn/dac-san-phu-quoc/bun-ken-phu-quoc)06–12；皆非該店第一方 | 明確時段衝突；早餐可作待確認選項，不排晚餐或保證午餐 |
| `com-tam-nhi` | [目錄](https://sodiachi.com/dia-diem/com-tam-nhi)1 NguyễnTrungTrực、17–20；[VinWonders文章](https://vinwonders.com/vi/wonderpedia/news/top-11-quan-com-tam-phu-quoc/)地址相符，但不是店家第一方；社群有16–20／16:30–19說法 | 可作早晚餐候選，17–20及「常提早售完」不能標本輪店家確認；晚到就換附近餐飲 |
| `wow-que-toi` | [店家Facebook](https://www.facebook.com/wowquetoi.pq/)僅取得搜尋摘要07–20:30／AnThoi；[餐廳目錄](https://restaurantsphuquoc.com/vi/restaurants/wow-que-toi-1004)22J4+MC3、連回Facebook，無時段 | 南島候選，有待地圖確認是否順路；不可稱已驗證從SunsetTown走路可達 |
| `bup-seafood` | [店家Facebook](https://www.facebook.com/BupRestaurant/)搜尋摘要33 ĐạiLộTrungTâmAnThới／Meyhomes；第三方時間10–21:30與17–22:30衝突 | 僅實際經Meyhomes且確認營業才替代，不預設從纜車順路 |
| `banh-mi-anh-thu` | Vinpearl搜尋摘要21 30Tháng4，舊JSON13／21差異；正文403，無店家第一方時段 | 早餐待確認選項，保留門牌衝突，不繞路追店 |
| `bep-nha-grandworld` | 舊JSON VERIFY；未取得該店一手營業證據 | 只有本來就在GrandWorld時看現場，不因店名加一趟 |
| `vinwonders-inside`（非單店ID） | [官方餐飲優惠](https://vinwonders.com/en/offers/phu-quoc-meal-combos-deep-sea/)explore直接讀取：頁標2026-09-12，Deep Sea位SeaShell1樓，10–18／最後點餐17:30 | 可具名建議VinWonders午餐DeepSea；不是Safari餐廳、未訂套餐 |
| Giraffe（尚無此輪核定pool ID） | 同官方優惠頁列Safari開放草原區、09–16、雞飯／海鮮炒飯／薯條／漢堡 | 可具名建議Safari午餐，但時段存在下述官方衝突 |

## 官方餐飲時段的交叉衝突

景點組與主代理直接讀取[Safari主頁](https://vinwonders.com/en/vinpearl-safari-phu-quoc/)：Giraffe **10:30–15:30**；Flamingo & Rhino **10:30–15:45**。餐飲優惠頁卻列Giraffe **09:00–16:00**。兩者都是園方頁，沒有足夠日期特定資訊判定誰取代誰；不能選較長營業時間湊行程。

規劃建議：Safari午餐放**12:00左右（建議用餐時間，不是預訂）**，落兩者共同區間，仍當日確認；備案園內Flamingo/Rhino。這解決「去哪吃」的建議，不宣稱衝突已消失或餐廳保證供餐。

HonThom園內午餐本輪仍無足夠餐廳／時段第一方證據，不硬指定套餐。GànhDầu的`quoc-thien`／`phuc-ngan`為VERIFY地區備案，不是Safari園內或必然順路，無另決尾段不加。

## 穩定food ID（現有public JSON映射，非新建記錄）

| pool key | food notion_id |
|---|---|
| bun-ken-87 | 3c839f3f-a67c-81f6-ae32-c3c2f906c654 |
| com-tam-nhi | 3c839f3f-a67c-8117-badf-cfaac7584afc |
| wow-que-toi | 3c839f3f-a67c-81b4-ad7e-e4fc9cf00bef |
| bup-seafood | 3cd39f3f-a67c-814f-b700-f0c5d339537d |
| banh-mi-anh-thu | 3ce39f3f-a67c-81fb-b323-f1e9fb315a83 |
| bep-nha-grandworld | 3d139f3f-a67c-815f-9387-c05d91356008 |

以上店家現有last_verified仍依原記錄（部分超過30天，**出發前重查**），不可用本次頁面查閱日全部覆寫。2026-09-12僅官方優惠頁的標示日期；其餘未取得發布日者寫未標，不當作09-27營運確認。
