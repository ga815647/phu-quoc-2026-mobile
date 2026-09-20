"""ETL: Point Pool 5 tables -> SQLite points (dict-based, missing keys default None)."""
import sqlite3

SRC = "3ca39f3f-a67c-81f9-8608-e5b5187ab19b"

POINTS = [
 # DD / 中島 (17)
 dict(area="DD", slug="dinh-cau", name="Dinh Cậu＋水龍聖母廟＋河口港景", interest=3.0,
      durable_note="視為單一整塊Point；Cable Day僅低摩擦時作10-20分micro-stop。", status="ACTIVE"),
 dict(area="DD", slug="dd-market", name="Dương Đông Market",
      durable_note="條件式：無目標餐廳=3；有目標店=1，買水果=2。", status="OPTIONAL"),
 dict(area="DD", slug="sung-hung", name="Sùng Hưng Cổ Tự", interest=2.0,
      durable_note="因Cosy／DD動線方便；不專程。", status="ACTIVE"),
 dict(area="DD", slug="cao-dai", name="Cao Đài Temple", interest=2.0,
      durable_note="DD動線方便；高台教差異性可看，不專程。", status="ACTIVE"),
 dict(area="DD", slug="coi-nguon", name="Cội Nguồn Museum", interest=1.0,
      durable_note="建築不是古蹟；下雨／剛好附近才去。", status="OPTIONAL"),
 dict(area="DD", slug="dd-night-market", name="Dương Đông Night Market", interest=2.0,
      durable_note="快閃型；10-20分鐘看一下。", status="ACTIVE"),
 dict(area="DD", slug="su-muon", name="Sư Muôn Pagoda", interest=1.0,
      durable_note="有空順路再去。", status="OPTIONAL"),
 dict(area="DD", slug="suoi-tranh", name="Suối Tranh", interest=1.0,
      durable_note="天候體力都剛好才考慮。", status="OPTIONAL"),
 dict(area="DD", slug="suoi-da-ban", name="Suối Đá Bàn", interest=1.0,
      condition_gate="步行濕滑交通Returnability friction高",
      durable_note="景觀有特色但friction高。", status="OPTIONAL"),
 dict(area="DD", slug="fish-sauce", name="魚露工廠", interest=1.0,
      durable_note="低權重filler；很閒＋順路才去。", status="OPTIONAL"),
 dict(area="DD", slug="bee-farm", name="Phu Quoc Bee Farm", interest=1.0,
      durable_note="順路才去；導覽依賴扣分。", status="OPTIONAL"),
 dict(area="DD", slug="pepper-farm", name="Khu Tượng Pepper Farm", interest=0.0,
      durable_note="製程／導覽導向，淘汰。", status="RETIRED"),
 dict(area="DD", slug="pearl", name="珍珠養殖展示Ngọc Hiền", interest=0.0,
      durable_note="製程＋購物導向，淘汰。", status="RETIRED"),
 dict(area="DD", slug="ridgeback", name="Thanh Nga Ridgeback賽犬場", interest=0.0,
      durable_note="淘汰。", status="RETIRED"),
 dict(area="DD", slug="sunset-sanato", name="Sunset Sanato", interest=1.0,
      durable_note="看心情；不作default。", status="OPTIONAL"),
 dict(area="DD", slug="bittersweet", name="Bittersweet Chocolate Factory＋Workshop", interest=0.0,
      durable_note="無興趣淘汰，不作雨天備案。", status="RETIRED"),
 dict(area="DD", slug="soc-nau", name="Sóc Nâu 熱礦泥浴＋戲水", interest=0.0,
      durable_note="對泡泥無興趣淘汰，不作雨天備案。", status="RETIRED"),
 # 海灘 (10 + starfish special)
 dict(area="BEACH", slug="long-beach", name="Long Beach / Bãi Trường", interest=1.0,
      durable_note="非正式Point；Free-play/Buffer玩沙踩水。", status="OPTIONAL"),
 dict(area="BEACH", slug="ong-lang-beach", name="Ông Lang Beach", interest=1.0,
      durable_note="北上超順路＋天氣漂亮才停。", status="OPTIONAL"),
 dict(area="BEACH", slug="sao-beach", name="Sao Beach", interest=2.0,
      durable_note="南島海灘首選。", status="ACTIVE"),
 dict(area="BEACH", slug="khem-beach", name="Khem Beach", interest=1.5,
      durable_note="較resort化；已移出Card/default。", status="RETIRED"),
 dict(area="BEACH", slug="bai-dai", name="Bãi Dài 北島", interest=0.5,
      durable_note="VW/GW區100%順路＋天氣漂亮才看。", status="OPTIONAL"),
 dict(area="BEACH", slug="vung-bau", name="Vũng Bầu", interest=0.0,
      durable_note="淘汰。", status="RETIRED"),
 dict(area="BEACH", slug="hon-mot", name="Hòn Một", interest=1.0,
      condition_gate="Route Viability約0；偏遠道路",
      returnability="Returnability高，實際不排", status="OPTIONAL"),
 dict(area="BEACH", slug="bai-thom", name="Bãi Thơm 海岸＋紅樹林＋小聚落", interest=1.0,
      condition_gate="DD往返交通／Returnability friction高",
      durable_note="不為它單獨繞路。", status="OPTIONAL"),
 dict(area="BEACH", slug="np-trek", name="Phú Quốc National Park trekking", interest=0.0,
      durable_note="不列正式候選。", status="RETIRED"),
 dict(area="BEACH", slug="rainforest-walk", name="熱帶雨林 micro-walk", interest=0.0,
      durable_note="蛇類＋帶兒童，淘汰。", status="RETIRED"),
 dict(area="BEACH", slug="starfish", name="Starfish Beach（Rạch Vẹm／Hàm Rồng）",
      condition_gate="無/很少海星=0；很多=3但須往返交通確認；10月中不套乾季影片",
      durable_note="條件式；屬starfish Card。", status="ACTIVE"),
 # 漁村 (7)
 dict(area="FISH", slug="ganh-dau", name="Gành Dầu 漁村＋周邊海岸", interest=2.0,
      returnability="Returnability friction要算",
      durable_note="Cape已合併；Safari後北島小點領先。", status="ACTIVE"),
 dict(area="FISH", slug="rach-vem", name="Rạch Vẹm 漁村", interest=1.0,
      durable_note="海上餐廳較觀光化；海星Card boarding區。", status="ACTIVE"),
 dict(area="FISH", slug="ham-ninh", name="Hàm Ninh", interest=1.0,
      durable_note="若Food Atlas證明花蟹standout可升級。", status="ACTIVE"),
 dict(area="FISH", slug="cua-can", name="Cửa Cạn River＋Fishing Village", interest=1.0,
      play_mode="竹籃船短版45-60分可升1.5",
      durable_note="本體1；順路＋狀態佳才作付費Play Mode。", status="OPTIONAL"),
 dict(area="FISH", slug="rach-tram", name="Rạch Tràm", interest=0.0,
      condition_gate="偏遠＋雨季道路＋Returnability差",
      durable_note="淘汰。", status="RETIRED"),
 dict(area="FISH", slug="nguyen-trung-truc", name="Nguyễn Trung Trực Temple", interest=1.0,
      durable_note="北島歷史filler。", status="OPTIONAL"),
 dict(area="FISH", slug="anthoi-market", name="An Thới Market＋Harbour",
      durable_note="條件式：無目標店=3；有目標餐廳=1。現為Cable optional satellite。",
      status="OPTIONAL"),
 # 北島 (6)
 dict(area="NORTH", slug="safari", name="Vinpearl Safari", interest=2.0,
      durable_note="正式北島主Anchor；偏早上核心3-4h。", status="ACTIVE"),
 dict(area="NORTH", slug="safari-night", name="Vinpearl Safari Night Safari", interest=1.0,
      condition_gate="21:00散場後Returnability／接車",
      durable_note="夜間獨立付費Play Mode。", status="OPTIONAL"),
 dict(area="NORTH", slug="safari-vip", name="Vinpearl Safari VIP Zoo Tour", interest=0.0,
      durable_note="走不動直接離開；淘汰。", status="RETIRED"),
 dict(area="NORTH", slug="vinwonders", name="VinWonders", interest=2.0,
      durable_note="正式北島主Anchor；孩子偏好高於Safari。", status="ACTIVE"),
 dict(area="NORTH", slug="grand-world", name="Grand World", interest=2.0,
      durable_note="北島晚間尾段；Quintessence獨立=0不安排。", status="ACTIVE"),
 dict(area="NORTH", slug="quintessence", name="The Quintessence of Vietnam", interest=0.0,
      durable_note="不安排。", status="RETIRED"),
 # 南島 (6 + shows)
 dict(area="SOUTH", slug="hon-thom", name="Hòn Thơm Sun World Cable Car core", interest=3.0,
      mandatory="Yes", trip_priority="整趟最高",
      durable_note="Cable=Mandatory core；Aquatopia/Exotica/Bãi Trào皆內部內容。",
      status="ACTIVE"),
 dict(area="SOUTH", slug="sunset-town", name="Sunset Town＋Kiss Bridge", interest=2.0,
      mandatory="Yes",
      durable_note="代表性必訪；內部內容不另設Point。", status="ACTIVE"),
 dict(area="SOUTH", slug="sunset-shows", name="Sunset Town shows",
      condition_gate="View-dependent：Kiss付費0/免費1；Symphony付費0.5/免費2；免費位精彩者勝",
      durable_note="需驗證viewpoint/遮擋/卡位/2026免費與否。", status="OPTIONAL"),
 dict(area="SOUTH", slug="ho-quoc", name="Hộ Quốc Pagoda", interest=1.0,
      durable_note="南島順路scenic micro-point。", status="OPTIONAL"),
 dict(area="SOUTH", slug="ice-jungle", name="Ice Jungle Phú Quốc", interest=0.5,
      durable_note="付費室內光影60分；雨天晚間備選。", status="OPTIONAL"),
 dict(area="SOUTH", slug="sunday-game", name="Sunday Game An Thới室內兒童遊樂場", interest=0.5,
      durable_note="Child Free-play／Rain Buffer；低機率備案。", status="OPTIONAL"),
 dict(area="SOUTH", slug="theater", name="Phu Quoc Theater水上木偶戲", interest=1.0,
      durable_note="付費室內60-70分越語；晚間備選。", status="OPTIONAL"),
]

COLS = ["slug", "name", "area", "interest", "mandatory", "trip_priority",
        "condition_gate", "convenience", "returnability", "play_mode",
        "condition_note", "kid_note", "status", "durable_note",
        "source_notion_id", "evidence_as_of"]


def main(db_path="data/phuquoc.db"):
    db = sqlite3.connect(db_path)
    for p in POINTS:
        row = {c: p.get(c) for c in COLS}
        row["source_notion_id"] = SRC
        row["evidence_as_of"] = p.get("evidence_as_of", "2026-08-29")
        db.execute(
            "INSERT OR REPLACE INTO points(slug,name,area,interest,mandatory,trip_priority,"
            "condition_gate,convenience,returnability,play_mode,condition_note,kid_note,"
            "status,durable_note,source_notion_id,evidence_as_of)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [row[c] for c in COLS],
        )
    db.commit()
    print("points:", db.execute("select count(*) from points").fetchone())
    print(list(db.execute("select area,count(*) from points group by area")))
    print(list(db.execute("select status,count(*) from points group by status")))


if __name__ == "__main__":
    main()
