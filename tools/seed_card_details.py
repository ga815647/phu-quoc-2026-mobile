"""Seed card detail content (stops / transport / dining) into phuquoc.db cards table.

Source: v2.html timelines (cable/vin/onbird/safari) + starfish gate list
        + site-sync-regional-food.yml cable/vin timelines
        + onbird-dd-followup.yml (Cable no DD micro-stop, OnBird optional DD tail)
Existing columns (route/gates/transport/notes) untouched; only new detail columns written.
Re-runnable: ALTERs only missing columns, UPDATEs only the 5 ACTIVE cards.
"""
import json
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "phuquoc.db"

NEW_COLS = ["summary", "key_times", "badges", "stops", "transport_out",
            "transport_back", "kid_note", "dining", "cut_order", "callout"]

M = lambda label, query: {"label": label, "query": query}  # noqa: E731


def stop(time, title, desc, maps=None):
    return {"time": time, "title": title, "desc": desc, "maps": maps or []}


CARDS = {
    "cable": {
        "summary": "最高優先 · first-wave target · An Thới 只 optional",
        "key_times": ["08:30–08:45 離 Cosy", "11:00 hard arrival（first-wave 09:30–11:30*，T−72 重查）"],
        "badges": [{"tone": "brand", "text": "必排"}, {"tone": "warm", "text": "Heavy"},
                   {"tone": "", "text": "No DD micro-stop"}],
        "stops": [
            stop("07:00–08:15", "Food Pool 早餐",
                 "告訴 ChatGPT 現在時間＋位置；從未吃且仍可用者挑早餐。早餐後直接往 Ga Ánh Dương；Cable 日不再安排 Dinh Cậu 或其他 DD 停留。"),
            stop("08:30–08:45", "離開 Cosy / DD",
                 "Grab／GreenSM／taxi 直接往 Ga Ánh Dương；不要為早餐或老城散步拖過 departure window。",
                 [M("📍 Cosy Bungalow · 地圖", "Cosy Bungalow Phu Quoc"),
                  M("📍 Ga Ánh Dương · 地圖", "Ga Anh Duong Phu Quoc")]),
            stop("10:30–10:45", "Soft arrival", "留 QR、廁所、量身高、排隊 buffer。"),
            stop("11:00", "Hard arrival", "目前 first-wave close 11:30；T−72 重查 October exact hours。"),
            stop("回本島後", "An Thới optional",
                 "時間與孩子狀態都好才留 45–60 分看 Market + Harbour；否則直接 Sunset Town。",
                 [M("📍 Chợ An Thới · 地圖", "Cho An Thoi Phu Quoc")]),
            stop("Evening", "Sunset Town", "Kiss Bridge + 日落保留；免費 show 只算 bonus。",
                 [M("📍 Sunset Town · 地圖", "Sunset Town Phu Quoc"),
                  M("📍 Kiss Bridge · 地圖", "Kiss Bridge Phu Quoc")]),
        ],
        "transport_out": [
            {"title": "去程 · 直達叫車",
             "desc": "Grab／GreenSM／taxi → Ga Ánh Dương；08:30–08:45 離 Cosy，不要為早餐或老城散步拖過 departure window。"}],
        "transport_back": [
            {"title": "回程 · 纜車＋末班 T−72 確認",
             "desc": "回程／末班時段、是否維修、天氣，出發前 72h 重查。"},
            {"title": "備案 · Sun World 免費接駁",
             "desc": "只作回程省錢備案（T−72 確認班次）；時間緊就直接叫車。"}],
        "kid_note": "約 115cm，纜車站量身高留排隊 buffer；全程後座，長程優先三點式安全帶＋增高墊。",
        "dining": [
            {"meal": "早餐", "place": "Central / Cosy Food Pool", "note": "把時間＋位置丟給 ChatGPT 從未吃者挑；不再固定店。"},
            {"meal": "晚餐", "place": "Sunset Town 低摩擦（WOW QUÊ TÔI）", "note": "接近 show 以低摩擦為主；不要為吃折返 An Thới。"},
            {"meal": "順手", "place": "Chợ An Thới（僅 satellite 成立時）", "note": "熟食／小吃優先；不是為市場硬排時間。"}],
        "cut_order": ["先砍：An Thới Market + Harbour optional satellite。", "再砍：任何 VERIFY food hunting，直接 WOW。"],
        "callout": None,
    },
    "vinwonders": {
        "summary": "Sea Shell first；正常／孩子累就園內吃完撤",
        "key_times": ["09:15–09:35 main gate", "10:00 Sea Shell first"],
        "badges": [{"tone": "brand", "text": "核心"}, {"tone": "warm", "text": "Heavy"},
                   {"tone": "", "text": "GW optional"}],
        "stops": [
            stop("Breakfast", "Food Pool 早餐", "不固定某一家；把時間＋位置丟給 ChatGPT 再決定。"),
            stop("09:15–09:35", "Main gate", "直達叫車優先；安檢／票券後自然接 Sea Shell。",
                 [M("📍 Cosy Bungalow · 地圖", "Cosy Bungalow Phu Quoc"),
                  M("📍 VinWonders Phú Quốc · 地圖", "VinWonders Phu Quoc")]),
            stop("10:00", "Sea Shell first", "先做全齡、高確定性內容，再依 115cm 與孩子狀態選其他區域。",
                 [M("📍 The Sea Shell · 地圖", "The Sea Shell VinWonders Phu Quoc")]),
            stop("正常／累", "園內解決吃飯", "正常離園或孩子已累，不為晚餐硬加 Grand World；園內餐飲 window T−72/T−1 重查。"),
            stop("Early exit", "Optional Grand World",
                 "只有刻意提早離園且孩子 Green 才接；Bếp Nhà 是 VERIFY 現場備案 #1，Cơm Nhà secondary，兩者都不是 production Carrier。",
                 [M("📍 Grand World · 地圖", "Grand World Phu Quoc")]),
        ],
        "transport_out": [
            {"title": "去程 · 直達叫車優先", "desc": "Direct car primary；VinBus 只在 live ETA 與 T2 internal 接駁清楚時用。"}],
        "transport_back": [
            {"title": "回程 · 直達叫車", "desc": "Grand World 不是成功條件；走不動就直接離開回 Cosy。"}],
        "kid_note": "約 115cm，各設施限制現場確認；Sea Shell first 保全齡確定性；累了就撤，不硬撐。",
        "dining": [
            {"meal": "午餐", "place": "園內就近熱食", "note": "Món ngon Việt Nam 等多落在白天到約 19:00；T−72/T−1 重查實際時段。"},
            {"meal": "晚餐（僅 early exit＋Green）", "place": "Grand World Queue", "note": "Bếp Nhà（約11:00–23:00）VERIFY #1；Cơm Nhà secondary。不為吃飯單獨硬加 Grand World。"}],
        "cut_order": ["Grand World 不是成功條件；走不動就離開。", "正常／累：園內吃 → 撤。"],
        "callout": {"tone": "blue", "text": "正常／child-tired：園內吃 → 撤。只有 early exit + child Green 才接 Grand World。"},
    },
    "onbird": {
        "summary": "10/11 Morning confirmed · Cosy 往返 · 回來先休息",
        "key_times": ["Morning operator pickup（exact window 依通知）", "回程後休息；DD evening 僅 optional"],
        "badges": [{"tone": "brand", "text": "已確認"}, {"tone": "", "text": "10/12–14 改期 buffer"}],
        "stops": [
            stop("−90m", "房內簡單早餐", "太早就前晚備麵包、水果、奶類與水；不繞 An Thới。"),
            stop("Morning", "Operator door-to-door", "Cosy pickup／drop-off；exact window 依 OnBird 通知；不自拆 Grab 去港口。",
                 [M("📍 Cosy Bungalow · 地圖", "Cosy Bungalow Phu Quoc")]),
            stop("回 Cosy", "洗澡＋休息",
                 "休息後預排 Dinh Cậu／河口 + DD evening；若回程太晚或孩子累，就取消這段留 Cosy／Long Beach。",
                 [M("📍 Dinh Cậu · 地圖", "Dinh Cau Temple Phu Quoc")]),
        ],
        "transport_out": [
            {"title": "去程 · 業者接送 only", "desc": "Operator Cosy 71B door-to-door round trip；不自拆 Grab 去港口。"}],
        "transport_back": [
            {"title": "回程 · 業者送回 Cosy", "desc": "先洗澡休息；DD evening 另用 Grab／taxi，累就取消。"}],
        "kid_note": "5 歲 transfer／船上照看事先書面確認；child-size life jacket；現場仍依教練安全評估，可改期（10/12–14 buffer）。",
        "dining": [
            {"meal": "早餐", "place": "房內簡單解決", "note": "前晚先備好；不繞店。"},
            {"meal": "晚餐", "place": "Central / Cosy Queue（僅 DD evening 成立時）", "note": "Dinh Cậu／河口＋DD evening；累就留 Cosy／Long Beach 就近吃。"}],
        "cut_order": ["DD evening 是 optional tail，不是 OnBird 成功條件。", "回程晚／下雨／孩子累 → 現場直接取消。"],
        "callout": {"tone": "", "text": "Dinh Cậu／河口 + DD evening 先排上；若回程晚、下雨或孩子累，現場直接取消。"},
    },
    "starfish": {
        "summary": "All-green only · 不接受「先叫車去看看」",
        "key_times": ["T−48／T−24 gate 確認", "任一 gate fail → 整包 fail"],
        "badges": [{"tone": "red", "text": "七項 hard gate"}, {"tone": "", "text": "48h 現況"}],
        "stops": [
            stop("Gate 1", "Exact Cosy pickup／drop-off", "門到門往返先談好，不是到了再找車。",
                 [M("📍 Cosy · 地圖", "Cosy Bungalow Phu Quoc")]),
            stop("Gate 2", "Road + 實際 vehicle type", "路況＋車型先確認；SUV/MPV round-trip ≤160–180萬優先。"),
            stop("Gate 3", "Boarding map pin + 船型／容量／上下船",
                 "精確上船點等 T−48／T−24 gate 確認 operator boarding pin；現在不放模糊導航點。"),
            stop("Gate 4", "Short-boat minutes", "當日有海星區短船才成立；原船回。"),
            stop("Gate 5", "Child-size life jacket + child-safe boat", "兒童救生衣＋兒童安全船型，缺一不可。"),
            stop("Gate 6", "同船＋同 road vehicle return", "原船回 → 原車回，回程不斷鏈。"),
            stop("Gate 7", "Bad-water／no-star／road closure cancellation", "壞水況／無海星／封路的取消機制先談好。"),
            stop("Gate 8", "過去 48h 現況", "路況、海星、水色照片，48h 內證據全綠才去。"),
        ],
        "transport_out": [
            {"title": "去程 · T−1 包車 charter", "desc": "Round-trip SUV/MPV charter，≤160–180萬優先；去程不等於成立。"}],
        "transport_back": [
            {"title": "回程 · 原船＋原車", "desc": "同船＋同 road vehicle return；回程沒把握就不去。"}],
        "kid_note": "最高 execution risk；child-size life jacket + child-safe boat 兩項是 hard gate；無海星=0，不硬去。",
        "dining": [
            {"meal": "當日", "place": "不綁固定餐", "note": "回 DD 後看 Central / Cosy Queue；不為吃飯改變 gate 判斷。"}],
        "cut_order": ["任一 gate fail → 整包 fail。", "無海星=0，有海星=3 但需往返交通確認。"],
        "callout": {"tone": "red", "text": "任一 gate fail → 整包 fail。不接受「先叫車去看看」。"},
    },
    "safari": {
        "summary": "Gành Dầu daylight 或 Grand World evening，二選一",
        "key_times": ["09:00* Safari arrival（T−72 重查）", "Gành Dầu tail 17:00 前離"],
        "badges": [{"tone": "warm", "text": "Optional"}, {"tone": "", "text": "不是自動遞補"}],
        "stops": [
            stop("07:55–08:10", "Cosy 直達叫車", "先從 Food Pool 解決早餐；不做完整 DD 散步。",
                 [M("📍 Cosy Bungalow · 地圖", "Cosy Bungalow Phu Quoc")]),
            stop("09:00*", "Safari arrival", "保守用 09:00；T−72 重查 official hours；園內 3–4h，偏早上。",
                 [M("📍 Vinpearl Safari Phú Quốc · 地圖", "Vinpearl Safari Phu Quoc")]),
            stop("Tail A", "Gành Dầu daylight", "retained driver；17:00 前離；先把回程車談好。",
                 [M("📍 Gành Dầu · 地圖", "Ganh Dau Phu Quoc")]),
            stop("Tail B", "Grand World evening", "孩子 Green 才接；不為吃飯硬選這條。",
                 [M("📍 Grand World · 地圖", "Grand World Phu Quoc")]),
        ],
        "transport_out": [
            {"title": "去程 · 直達叫車", "desc": "Cosy direct car → Safari；偏遠點先鎖回程再出發。"}],
        "transport_back": [
            {"title": "回程 A · retained driver", "desc": "Gành Dầu daylight tail 用留車／明確回接，17:00 前離。"},
            {"title": "回程 B · 直達叫車", "desc": "Grand World evening tail 直達叫車回 Cosy。"}],
        "kid_note": "約 115cm，設施限制現場確認；Junior Zoo Keeper=0 不問；VIP 車淘汰；3–4h 偏早上，累了就撤。",
        "dining": [
            {"meal": "午餐", "place": "Safari 園內／就近解決", "note": "不為吃飯硬接 tail。"},
            {"meal": "Tail A 餐", "place": "Gành Dầu（Quốc Thiên VERIFY #1／Phúc Ngân #2）", "note": "秤重海鮮先問單價、重量、加工費。"},
            {"meal": "Tail B 餐", "place": "Grand World（Bếp Nhà #1／Cơm Nhà #2）", "note": "人在 Grand World 才用。"}],
        "cut_order": ["tail 只選一個，不自動綁 Grand World。", "只有真的想去才排；不是自動遞補。"],
        "callout": None,
    },
}


def main():
    db = sqlite3.connect(DB)
    have = {r[1] for r in db.execute("PRAGMA table_info(cards)")}
    for col in NEW_COLS:
        if col not in have:
            db.execute(f"ALTER TABLE cards ADD COLUMN {col} TEXT")
            print("added column", col)
    for slug, c in CARDS.items():
        row = {"summary": c["summary"],
               "key_times": json.dumps(c["key_times"], ensure_ascii=False),
               "badges": json.dumps(c["badges"], ensure_ascii=False),
               "stops": json.dumps(c["stops"], ensure_ascii=False),
               "transport_out": json.dumps(c["transport_out"], ensure_ascii=False),
               "transport_back": json.dumps(c["transport_back"], ensure_ascii=False),
               "kid_note": c["kid_note"],
               "dining": json.dumps(c["dining"], ensure_ascii=False),
               "cut_order": json.dumps(c["cut_order"], ensure_ascii=False),
               "callout": json.dumps(c["callout"], ensure_ascii=False) if c["callout"] else None,
               "evidence_as_of": "2026-09-20"}
        sets = ", ".join(f"{k}=:{k}" for k in row)
        cur = db.execute(f"UPDATE cards SET {sets} WHERE slug=:slug", {**row, "slug": slug})
        assert cur.rowcount == 1, f"missing card {slug}"
        print("seeded", slug, len(c["stops"]), "stops")
    # verify: old columns untouched + new columns parse
    for r in db.execute("SELECT slug,route,gates,transport,notes,summary,stops FROM cards WHERE status='ACTIVE'"):
        assert r[1] and r[2] and r[3] and r[4], f"old column empty on {r[0]}"
        assert r[5], f"summary missing on {r[0]}"
        stops = json.loads(r[6])
        assert isinstance(stops, list) and stops, f"stops bad on {r[0]}"
        for s in stops:
            assert set(s) == {"time", "title", "desc", "maps"}, f"stop keys bad on {r[0]}: {s}"
    db.commit()
    print("SEED_VERIFY=PASS")


if __name__ == "__main__":
    main()
