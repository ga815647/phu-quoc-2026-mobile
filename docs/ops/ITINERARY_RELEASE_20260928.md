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
- [x] A版生成、PR12已合併main `f82a2254898c27bbdcec86cd1784c486d1334834`；Pages run `36369884190` success、正式data-smoke run `36369885516` success。正式站320／390／430px六日切換／實際API／20餐飲／5卡／無溢出與JS錯誤皆通過；阻斷Function時有日期六日備援與「非最新」標示通過。
- [x] OpenCode真實request→Actions→結果分支讀回：run `36369963344` success，固定結果commit `7ab1a469eb70c70355c1301f90075d8539d4d8b6` 的result.json為PASS、source=live、expected/observed revision一致；全部API／DOM／六日／備案／五卡導航檢查true。
- [x] 提供Chat規則／接手操作；目標Chat親自修改讀回待使用者帶回。規則以main解析為當次固定SHA讀取，毋須更換既有Project bootstrap。

此表只記已發生證據；發布未完成前不得把授權或本地通過當成正式入口已可用。

## 已發布工程與首次Chat驗收

- 正式站：https://ga815647.github.io/phu-quoc-2026-mobile/
- [Pages發布](https://github.com/ga815647/phu-quoc-2026-mobile/actions/runs/36369884190)、[正式手機smoke](https://github.com/ga815647/phu-quoc-2026-mobile/actions/runs/36369885516)。
- 目前正式生成模式為`--prod --itinerary-mode candidate`：A六日閱讀器讀正式Neon，同时保留舊手機暫排／裝置資料；此內部相容模式名稱不代表測試庫，也不等於舊編輯已退役。
- OpenCode初始發布驗站request `2be192b0-a25f-4420-88f9-da951a92c880`，request commit `46aabf7ff2bf9a5e1630f1bf48a50dc6f44036cb`。這是初始化後工程驗站，不是目標Chat修改receipt；Chat首次真實更新須依runbook使用其實際receipt UUID。
- [真Actions run](https://github.com/ga815647/phu-quoc-2026-mobile/actions/runs/36369963344)；[固定結果JSON](https://github.com/ga815647/phu-quoc-2026-mobile/blob/7ab1a469eb70c70355c1301f90075d8539d4d8b6/requests/2be192b0-a25f-4420-88f9-da951a92c880/result.json)。實際觀察於2026-09-28T02:29:24Z，build `sha256:67e7c5b2bcd264d0ec775e4be6c7c30b058f7c4ef057c8757c7f8ff802f1f48d`。
- 目標Chat接手只需同版Git規則＋正式Neon讀取及一筆明確授權修改→request→Actions結果讀回；先前完整connector能力驗收沿用，不重做。尚未有目標Chat本次證據；手機使用者接受與舊編輯退役亦未宣稱完成。

### 給目標Chat的接手起點

1. 將`ga815647/phu-quoc-2026-mobile`的main解析為固定commit，讀同版`chatgpt-instructions.md`、`CONTENT_CONTRACT.md`、`CHAT_ITINERARY_RUNBOOK.md`與本紀錄。
2. 正式Neon讀`itinerary_read_for_edit`和`itinerary_public`；先摘要六日安排與真正待查核項，不用Git備援冒充最新版本。
3. 依使用者當次具體要求改一項備註，保留其他安排；沿runbook保存receipt/audit→建立同UUID驗站請求→固定結果commit讀回，回報資料／即時顯示／離線備援各自狀態。
4. 之後旅遊事實查核按`CHAT_RESEARCH_HANDOFF.md`接手；已知未知可以留待接近出發補證，不自行填假時刻。

## 隔離驗證環境差異

Neon的owner並非`phq_web_ro`成員，`SET ROLE`遭拒絕；不擴權。失敗交易回滾後改用真正的restricted login驗證公開view可讀、私表／audit／edit／update不可用，通過。migration在同一交易重跑比對catalog fingerprint；提交後再核對資料與schema。私人證據 `006-qualification.json`。

初始化需新增兩筆園內通用餐飲池穩定鍵`safari-inside`／`honthom-inside`，沿用既有園內靜態条目例外（notion_id為null），只表示園內待查核用餐，不捏造具名餐廳、營業時間或新Notion店家。這是六日草案所需最小引用，與原研究列修改分開記錄；後續Chat可經受控安排改為已查明的店家。
