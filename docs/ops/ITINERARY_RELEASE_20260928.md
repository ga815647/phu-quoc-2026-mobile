# 六日 A 版發布紀錄（2026-09-28）

## 授權與目標

使用者明列範圍後選「整組授權（推薦）」：先隔離驗證，再正式新增006／最小唯讀ACL、以未知值如實初始化六日草案、發布Function／A版／CI／Chat規則。已確認訂單不改；OnBird保護固定10/11上午活動，精確時間待通知後首次受控補齊。後續變更已填核心時間仍須另授權。

- Neon project `holy-fog-65935796`，database `neondb`。
- 隔離 `itinerary-release-20260928`／`br-small-fire-b31fbrs4`，源自production；parent LSN `0/21C4680`。
- 正式 `br-silent-haze-b3xw64tm`。
- 正式migration前唯讀檢查：新itinerary表／view不存在，8筆bookings。
- 隔離baseline：PG18.6、維護身分與既有content_update owner均`neondb_owner`；cards7、food_places69、food_pool18、points48、bookings8、transport_options7、content_revisions31。
- 私人執行證據暫存 `/tmp/opencode/phq-release-private/`（不提交憑證、完整來源副本或連線字串）。

## 檢核清單

- [x] A reader整合及任務複核：42bd589／b2a9e1c；320／390／430px操作、未知時間、動態內容替換、舊裝置資料保留。
- [x] 建立上述隔離分支並唯讀baseline。
- [x] OnBird未知核心／首次補齊實作08a8f84，獨立審查通過；controller重跑56項Python與26項reader／CI Node測試，另跑手機browser通過。
- [x] 隔離006首次／重跑、來源零變更、真實ACL驗證；migration SHA256 `246a0a67e58e83e388f5fa1116c44ec93871a10822e7fb186a7ff2c81d43bf75`。既有資料／ACL雜湊一致，初始化前新表為空。
- [x] 真實六日初始化審查與隔離受控更新／還原／衝突／idempotency／audit驗證；兩處回程缺口修正後複核通過。
- [x] 正式006與初始化、最小ACL catalog讀回、既有來源一致；bookings8筆內容雜湊未變。僅food_pool增加两個園內待查核穩定引用。
- [x] Function deployment6 completed；正式API HTTP200與Neon匯出JSON六日內容逐值一致；公開revision `phq1:6806a27908e797aceeb99cb7003ad9d1a05e9ffb07db0ca8d82092c4c4c4a1c3`。
- [ ] A版生成、整合main／Pages與CI部署。
- [ ] OpenCode真實request→Actions→結果分支讀回。
- [ ] 提供Chat固定版本規則／接手操作；目標Chat親自修改讀回待使用者帶回。

此表只記已發生證據；發布未完成前不得把授權或本地通過當成正式入口已可用。

## 隔離驗證環境差異

Neon的owner並非`phq_web_ro`成員，`SET ROLE`遭拒絕；不擴權。失敗交易回滾後改用真正的restricted login驗證公開view可讀、私表／audit／edit／update不可用，通過。migration在同一交易重跑比對catalog fingerprint；提交後再核對資料與schema。私人證據 `006-qualification.json`。

初始化需新增兩筆園內通用餐飲池穩定鍵`safari-inside`／`honthom-inside`，沿用既有園內靜態条目例外（notion_id為null），只表示園內待查核用餐，不捏造具名餐廳、營業時間或新Notion店家。這是六日草案所需最小引用，與原研究列修改分開記錄；後續Chat可經受控安排改為已查明的店家。
