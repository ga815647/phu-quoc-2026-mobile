from pathlib import Path
from urllib.parse import quote_plus
import json
import re

hp = Path("index.html")
jp = Path("assets/page-kjCTkZIS.js")
cp = Path("assets/index-C-szeJ12.css")
mp = Path("SITE_SYNC_MANIFEST.json")
html = hp.read_text()
page = jp.read_text()
css = cp.read_text()

PATCH_ID = "PHQ-SITE-FOOD-LOCATION-TIME-QUEUE-2026-09-05-01"

queues = [{'id': 'food-central',
  'title': '🌅 Central / Cosy',
  'summary': '人在這區，就依現在時間直接選；正餐、小吃、糕點同一 Queue',
  'open': True,
  'rows': [{'slot': '05:00–12:00',
            'name': 'Bánh Canh Phụng',
            'role': 'Carrier',
            'tone': 'carrier',
            'note': '早段強選項；約 05:00–11:30/12:00，06:30–08:30 最穩。可能售罄；魚肉注意刺。',
            'maps': [['Phụng', 'Bánh Canh Phụng Phú Quốc']]},
           {'slot': '06:00–12:00',
            'name': 'Bún Kèn Út Lượm',
            'role': 'Carrier',
            'tone': 'carrier',
            'note': 'A-priority；約 06:00–12:00。若沒吃到，Bún kèn 87 是正式 Backup，但時段仍要 T−72/T−1 重查。',
            'maps': [['Út Lượm', 'Bún Kèn Út Lượm Phú Quốc'], ['87', 'Bún kèn 87 Phú Quốc']]},
           {'slot': '午間／先確認',
            'name': 'Bún Mắm Dung Hà',
            'role': '條件式 Carrier',
            'tone': 'conditional',
            'note': '想吃 bún mắm 時優先；先問 normal/special bowl 與 extras，不清楚就跳過。實際營業窗 T−72/T−1 再鎖。',
            'maps': [['Dung Hà', 'Bún Mắm Dung Hà Phú Quốc']]},
           {'slot': '06:00–00:00',
            'name': 'Bánh mì Anh Thư',
            'role': 'Carrier',
            'tone': 'carrier',
            'note': '目前最穩的全天／晚間鹹食 Carrier；任何不是正餐時段、只想快速吃一點也能用。',
            'maps': [['Anh Thư', 'Bánh mì Anh Thư Phú Quốc']]},
           {'slot': '06:30–21:30',
            'name': 'bánh Khéo cô Dung',
            'role': 'ACTIVE · 地方糕點',
            'tone': 'fallback',
            'note': '43 Đ. 30 Tháng 4；地方特色高、成本低，適合任何順路嘴饞時段少量買多口味。不是 Dish Carrier。',
            'maps': [['Cô Dung', 'bánh Khéo cô Dung, 43 Đ. 30 Tháng 4, Phú Quốc']]},
           {'slot': '看到好貨就買',
            'name': 'Chợ Dương Đông｜糕點／小吃／水果',
            'role': 'MARKET NODE',
            'tone': 'market',
            'note': '不綁餐次：熟食／小吃優先，其次 bòn bon（A）與榴槤（B）。看到 Bánh tét mật cật、kẹo chỉ、bánh bò thốt nốt、dừa sáp dầm thốt nốt 可順手試；目前不假裝有固定 Carrier。',
            'maps': [['Dương Đông Market', 'Chợ Dương Đông Phú Quốc']]},
           {'slot': '傍晚／晚間',
            'name': 'Nhum nướng mỡ hành 8K',
            'role': '條件式 Carrier',
            'tone': 'conditional',
            'note': '只有 Nhum 尚未完成才優先；先確認有貨、確為 nướng mỡ hành、當日價格。「8K」不是現價保證。',
            'maps': [['Nhum 8K', 'Hàu Nướng Nhum nướng 8K Phú Quốc']]},
           {'slot': '17:00–20:00',
            'name': 'Cơm tấm Nhị',
            'role': '現場備案',
            'tone': 'fallback',
            'note': '想快速坐下吃飯、又不需要追高優先 Dish 時用；屬功能型 fallback。',
            'maps': [['Cơm tấm Nhị', 'Cơm tấm Nhị Phú Quốc']]},
           {'slot': '09:30–22:00',
            'name': 'Nhà Xưa 68',
            'role': '家庭現場備案',
            'tone': 'fallback',
            'note': '白飯、蛋、肉與清淡熟食較容易拆；孩子累、想坐下、或正餐時間被打亂時都能直接用。',
            'maps': [['Nhà Xưa 68', 'Nhà Xưa 68 Phú Quốc']]}]},
 {'id': 'food-vinwonders',
  'title': '🎢 VinWonders｜園內餐飲',
  'summary': '人在園內就先看目前還營業的選項；不為吃飯硬提早離園',
  'open': False,
  'rows': [{'slot': '園內營業時段',
            'name': '園內先吃',
            'role': '園內備案',
            'tone': 'park',
            'note': 'Món ngon Việt Nam、Cơm gà Hội An & Bún Chả Hà Nội 等目前多落在白天到約 19:00；T−72/T−1 再查實際時段。',
            'maps': [['VinWonders', 'VinWonders Phú Quốc']]},
           {'slot': '提早離園＋Green',
            'name': 'Grand World Queue',
            'role': '可選尾段',
            'tone': 'fallback',
            'note': '只有刻意提早離園、孩子還有力才接；可直接跳到 Grand World Queue，不要為了晚餐單獨硬加 Grand World。',
            'maps': [],
            'jump': ['看 Grand World Queue', '#food-grandworld']}]},
 {'id': 'food-south',
  'title': '🌇 An Thới / Sunset Town',
  'summary': '沒有 generic Primary；到這區再依時間與當下需求選',
  'open': False,
  'rows': [{'slot': '白天／一般',
            'name': 'WOW QUÊ TÔI',
            'role': '現場備案',
            'tone': 'fallback',
            'note': '本區沒有穩定 generic Food Primary；WOW 是低摩擦正餐備案，不是 Dish Carrier。',
            'maps': [['WOW', 'WOW QUÊ TÔI An Thới Phú Quốc']]},
           {'slot': 'Cable 回島後',
            'name': 'BUP Seafood',
            'role': '條件式 Backup Carrier',
            'tone': 'conditional',
            'note': '只有 Nhum 尚未完成且 stock／preparation／price 都通過才用。Cô Thu 仍是 VERIFY；否則直接 WOW。',
            'maps': [['BUP', 'BUP Seafood An Thới Phú Quốc'], ['Cô Thu', 'Bún Kèn Cô Thu An Thới Phú Quốc'], ['WOW', 'WOW QUÊ TÔI An Thới Phú Quốc']]},
           {'slot': 'Show 前／晚間',
            'name': 'WOW QUÊ TÔI',
            'role': '現場備案',
            'tone': 'fallback',
            'note': '不要為 Food 折返 An Thới；接近 show 時以低摩擦為主。',
            'maps': [['WOW', 'WOW QUÊ TÔI An Thới Phú Quốc']]},
           {'slot': '市場開放時段',
            'name': 'Chợ An Thới',
            'role': 'MARKET NODE',
            'tone': 'market',
            'note': '只當現場探索點；熟食／小吃優先，水果其次。目前沒有可重訪、protocol-valid 的固定攤位 Carrier。',
            'maps': [['市場', 'Chợ An Thới Phú Quốc']]}]},
 {'id': 'food-ganhdau',
  'title': '🌊 Gành Dầu',
  'summary': 'Safari daylight tail 到這區後再吃，不是為了 Food 才選 tail',
  'open': False,
  'rows': [{'slot': '白天／Safari 後',
            'name': 'Quốc Thiên',
            'role': 'VERIFY · 現場備案 #1',
            'tone': 'verify',
            'note': '目前最實用的 Gành Dầu fallback；秤重海鮮先問單價、重量、加工費與其他費用。不是 Carrier。',
            'maps': [['Quốc Thiên', 'Welcome To Nha Hang Quoc Thien Gành Dầu Phú Quốc']]},
           {'slot': '白天～晚餐',
            'name': 'Phúc Ngân',
            'role': 'VERIFY · 第二備案',
            'tone': 'verify',
            'note': '偏 cooked local seafood；有 Nhum／còi 類線索，但證據仍不足以升 Carrier。',
            'maps': [['Phúc Ngân', 'Nhà Hàng Biển Phúc Ngân Gành Dầu Phú Quốc']]},
           {'slot': '早上較佳',
            'name': 'Chợ Gành Dầu',
            'role': 'MARKET NODE',
            'tone': 'market',
            'note': '早上較有市場感；只挑當下現做、熱賣的熟食，不指定不存在的固定攤位。',
            'maps': [['市場', 'Chợ Gành Dầu Phú Quốc']]}]},
 {'id': 'food-grandworld',
  'title': '🌃 Grand World',
  'summary': '人在 Grand World，就看當下仍營業且摩擦最低的選項',
  'open': False,
  'rows': [{'slot': '約11:00–23:00',
            'name': 'Bếp Nhà Restaurant',
            'role': 'VERIFY · 現場備案 #1',
            'tone': 'verify',
            'note': '目前最完整的 Grand World fallback；保守按約 11:00–23:00 執行，T−72/T−1 重查。不是 Carrier。',
            'maps': [['Bếp Nhà', 'Bếp Nhà Restaurant Grand World Phú Quốc']]},
           {'slot': '約08:00–22:00',
            'name': 'Cơm Nhà Phú Quốc',
            'role': 'VERIFY · 第二備案',
            'tone': 'verify',
            'note': 'family-style execution 比較乾淨；review-integrity 有疑慮，所以不升 Food winner。',
            'maps': [['Cơm Nhà', 'Cơm Nhà Phú Quốc Grand World']]}]}]


def replace_both(old, new, required=True):
    global html, page
    count = html.count(old) + page.count(old)
    if required and count == 0:
        raise SystemExit(f"missing coherence source: {old}")
    html = html.replace(old, new)
    page = page.replace(old, new)
    return count


replacements = [
    ("Central dynamic breakfast", "Central / Cosy｜Food Queue"),
    ("Central dynamic queue", "Central / Cosy｜Food Queue"),
    ("regional dynamic queue", "Central / Cosy｜Food Queue"),
    ("Central breakfast", "Central / Cosy｜Food Queue"),
    ("今天是狀態，不是第七張 Card；不要為填空硬補景點。", "今天是 Free / Recovery 狀態，不是第六張 Card；不需要為填空硬補景點。"),
    ("🚦 交通＋營業時間已整合", "🚦 交通＋吃飯 Queue 已整合"),
    ("現在只剩 execution refresh", "出發前只做必要複核"),
    ("不再 broad research", "不再廣泛重查"),
    ("🚕 Central／大節點", "🚕 Central / Cosy＋大節點"),
    ("🛻 Remote／多停點", "🛻 偏遠點／多停點"),
    ("Remote returnability 先鎖：海星用完整 door-to-door round trip；Safari→Gành Dầu daylight tail 用 retained driver／明確回接；無可靠回程就 skip。", "偏遠點先鎖回程：海星用完整門到門往返；Safari → Gành Dầu daylight tail 用留車／明確回接；無可靠回程就 skip。"),
    ("⏱️ Stop-loss", "⏱️ 切換規則"),
    ("Food / satellite cut order", "時間不夠時怎麼砍"),
    ("交通／return／Food", "交通／回程／吃飯"),
    ("Direct car primary", "直達叫車優先"),
    ("Normal / tired exit", "正常／孩子累"),
    ("Early exit only", "提早離園"),
    ("child Green", "孩子 Green"),
    ("目前 not admitted／最高 execution risk。不是「有 package 就可以」。", "目前尚未通過 gate／執行風險最高。不是「有 package 就可以」。"),
    ("完整 door-to-door round trip", "完整門到門往返"),
    ("七項 hard gate＋48h live evidence", "七項 hard gate＋48h 現況證據"),
    ("Direct car → Safari", "直達叫車 → Safari"),
    ("Cosy direct pickup", "Cosy 直達叫車"),
    ("VERIFY execution fallback #1", "VERIFY 現場備案 #1"),
    ("Food 只降低 evening failure risk，不把 Grand World 升成 Food destination。", "吃飯只是降低晚餐踩空風險，不會讓 Grand World 變成必去美食點。"),
    ("Food 只保證兩條 tail 都有可吃選項，不替你決定 tail。", "吃飯 Queue 只保證兩條 tail 都有可吃選項，不替你決定 tail。"),
]
for old, new in replacements:
    replace_both(old, new)

replace_both(
    "Food 不改 Cable Mandatory。早餐用 Central / Cosy｜Food Queue；An Thới 是 optional，不是 standalone Card。",
    "吃飯不改變 Cable 必排。早餐直接用「Central / Cosy｜Food Queue」；An Thới 仍只是 optional satellite。",
)
replace_both(
    "South / North / Central 依 current regional queue；VERIFY 只解 execution，不升格 Carrier。selected place 的 hours／stock／price T−72/T−1 重查。",
    "依所在區域 Food Queue 執行；VERIFY 只代表可用的現場選項，不會升格 Carrier。選定店家的營業時間／庫存／價格 T−72/T−1 重查。",
)
replace_both(
    "先洗澡休息；若回程正常、孩子狀態 Green，再接 Dinh Cậu／河口＋DD 吃飯／夜市快閃；累就留 Cosy／Long Beach。",
    "先洗澡休息；若回程正常、孩子狀態 Green，再接 Dinh Cậu／河口＋DD evening；吃飯直接看 Central / Cosy Queue。累就留 Cosy／Long Beach。",
)

role_icon = {
    "carrier": "✅", "conditional": "⚠️", "verify": "🔎",
    "fallback": "🍲", "market": "🧺", "park": "🎟️",
}


def map_link(label, query):
    href = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(query)
    return f'<a class="pq-btn map-button" href="{href}" target="_blank" rel="noopener noreferrer">📍 {label}</a>'


def food_row(row):
    maps = "".join(map_link(label, query) for label, query in row.get("maps", []))
    jump = ""
    if row.get("jump"):
        label, href = row["jump"]
        jump = f'<a class="pq-btn queue-jump" href="{href}">↳ {label}</a>'
    tone = row["tone"]
    return (
        '<div class="food-row">'
        f'<div class="food-slot">{row["slot"]}</div>'
        '<div class="food-main">'
        f'<div class="food-titleline"><strong>{row["name"]}</strong><span class="food-role {tone}">{role_icon.get(tone,"•")} {row["role"]}</span></div>'
        f'<p>{row["note"]}</p></div>'
        f'<div class="food-maps">{maps}{jump}</div>'
        '</div>'
    )


def food_region(region):
    body = "".join(food_row(r) for r in region["rows"])
    op = " open" if region.get("open") else ""
    return (
        f'<details class="food-region" id="{region["id"]}"{op}>'
        '<summary>'
        f'<strong>{region["title"]}</strong><span>{region["summary"]}</span>'
        '</summary>'
        f'<div class="food-region-body">{body}</div>'
        '</details>'
    )


food_html = (
    '<section class="section" id="food">'
    '<div class="stitle"><h2>區域 Food Queue</h2><span>所在區域 → 現在時間 → 直接選</span></div>'
    '<div class="food-legend">'
    '<span class="food-role carrier">✅ Carrier</span>'
    '<span class="food-role conditional">⚠️ 條件式</span>'
    '<span class="food-role verify">🔎 VERIFY</span>'
    '<span class="food-role fallback">🍲 現場備案</span>'
    '<span class="food-role market">🧺 MARKET NODE</span>'
    '</div>'
    '<div class="food-stack">' + ''.join(food_region(q) for q in queues) + '</div>'
    '<div class="callout amber food-note"><strong>怎麼看：</strong>先看你現在在哪一區，再看目前時間與仍營業的選項。正餐、小吃、糕點、甜飲放在同一個區域 Queue；時段只是可用窗口與排序訊號，不代表早餐／午餐／下午茶一定要吃指定類型。Carrier 才是 protocol-valid production 選擇；VERIFY／現場備案只是到了這區可直接用，不等於認證最好吃。Market Node 只代表可逛的市場節點。選定店家仍做 T−72／T−1 營業時間、庫存與價格複核。</div>'
    '</section>'
)
html_pattern = re.compile(r'<section class="section" id="food">.*?</section>(?=<section class="section" id="rules">)', re.S)
if len(html_pattern.findall(html)) != 1:
    raise SystemExit("HTML food section boundary mismatch")
html = html_pattern.sub(food_html, html, count=1)

food_hash_script = '''<script id="food-hash-unlock">(function(){function q(h){if(!h||!h.startsWith('#food-'))return null;try{return document.getElementById(decodeURIComponent(h.slice(1)))}catch(e){return null}}function u(h){var el=q(h);if(!el||!el.classList.contains('food-region'))return false;el.open=true;requestAnimationFrame(function(){el.scrollIntoView({behavior:'smooth',block:'start'});setTimeout(function(){if(location.hash===h){history.replaceState(null,'',location.pathname+location.search)}},500)});return true}document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[href^="#food-"]');if(!a)return;var h=a.getAttribute('href');if(!q(h))return;e.preventDefault();history.replaceState(null,'',h);u(h)});window.addEventListener('hashchange',function(){u(location.hash)});var h=location.hash;if(h&&h.startsWith('#food-'))setTimeout(function(){u(h)},60)})();</script>'''
if 'id=\"food-hash-unlock\"' not in html:
    html = html.replace('</body>', food_hash_script + '</body>', 1)

if "var PQFoodQueues=" not in page:
    queue_js = json.dumps(queues, ensure_ascii=False, separators=(",", ":"))
    helper = f'''var PQFoodQueues={queue_js};
function PQFoodRow({{slot:e,name:t,role:n,tone:r,note:a,maps:o=[],jump:s}}){{return(0,j.jsxs)(`div`,{{className:`food-row`,children:[(0,j.jsx)(`div`,{{className:`food-slot`,children:e}}),(0,j.jsxs)(`div`,{{className:`food-main`,children:[(0,j.jsxs)(`div`,{{className:`food-titleline`,children:[(0,j.jsx)(`strong`,{{children:t}}),(0,j.jsxs)(`span`,{{className:`food-role `+r,children:[{{carrier:`✅`,conditional:`⚠️`,verify:`🔎`,fallback:`🍲`,market:`🧺`,park:`🎟️`}}[r]||`•`,` `,n]}})]}}),(0,j.jsx)(`p`,{{children:a}})]}}),(0,j.jsxs)(`div`,{{className:`food-maps`,children:[...o.map(([e,t])=>(0,j.jsx)(xu,{{query:t,children:`📍 `+e}},t)),s?(0,j.jsxs)(`a`,{{className:`pq-btn queue-jump`,href:s[1],children:[`↳ `,s[0]]}}):null]}})]}})}}
function PQFoodRegion({{id:e,title:t,summary:n,open:r=!1,rows:a=[]}}){{return(0,j.jsxs)(`details`,{{className:`food-region`,id:e,open:r,children:[(0,j.jsxs)(`summary`,{{children:[(0,j.jsx)(`strong`,{{children:t}}),(0,j.jsx)(`span`,{{children:n}})]}}),(0,j.jsx)(`div`,{{className:`food-region-body`,children:a.map((e,t)=>(0,j.jsx)(PQFoodRow,{{...e}},e.slot+`-`+t))}})]}})}}
'''
    marker = "function Cu(e){"
    if page.count(marker) != 1:
        raise SystemExit("client helper insertion marker mismatch")
    page = page.replace(marker, helper + marker, 1)

js_food = '''(0,j.jsxs)(`section`,{className:`section`,id:`food`,children:[(0,j.jsx)(Su,{title:`區域 Food Queue`,note:`所在區域 → 現在時間 → 直接選`}),(0,j.jsxs)(`div`,{className:`food-legend`,children:[(0,j.jsx)(`span`,{className:`food-role carrier`,children:`✅ Carrier`}),(0,j.jsx)(`span`,{className:`food-role conditional`,children:`⚠️ 條件式`}),(0,j.jsx)(`span`,{className:`food-role verify`,children:`🔎 VERIFY`}),(0,j.jsx)(`span`,{className:`food-role fallback`,children:`🍲 現場備案`}),(0,j.jsx)(`span`,{className:`food-role market`,children:`🧺 MARKET NODE`})]}),(0,j.jsx)(`div`,{className:`food-stack`,children:PQFoodQueues.map(e=>(0,j.jsx)(PQFoodRegion,{...e},e.id))}),(0,j.jsxs)(`div`,{className:`callout amber food-note`,children:[(0,j.jsx)(`strong`,{children:`怎麼看：`}),`先看你現在在哪一區，再看目前時間與仍營業的選項。正餐、小吃、糕點、甜飲放在同一個區域 Queue；時段只是可用窗口與排序訊號，不代表早餐／午餐／下午茶一定要吃指定類型。Carrier 才是 protocol-valid production 選擇；VERIFY／現場備案只是到了這區可直接用，不等於認證最好吃。Market Node 只代表可逛的市場節點。選定店家仍做 T−72／T−1 營業時間、庫存與價格複核。`]})]})'''
js_pattern = re.compile(r'\(0,j\.jsxs\)\(`section`,\{className:`section`,id:`food`,children:\[.*?\]\}\)(?=,\(0,j\.jsxs\)\(`section`,\{className:`section`,id:`rules`)', re.S)
if len(js_pattern.findall(page)) != 1:
    raise SystemExit("client food section boundary mismatch")
page = js_pattern.sub(js_food, page, count=1)

old_nav_css = ".bottom nav{grid-template-columns:repeat(4,1fr);"
new_nav_css = ".bottom nav{grid-template-columns:repeat(5,1fr);"
if css.count(old_nav_css) != 1:
    raise SystemExit(f"bottom nav grid mismatch: {css.count(old_nav_css)}")
css = css.replace(old_nav_css, new_nav_css, 1)

css_marker = "/* PHQ-SITE-UX-COHERENCE-FOOD-QUEUES-2026-09-05-01 */"
if css_marker not in css:
    css += """
/* PHQ-SITE-UX-COHERENCE-FOOD-QUEUES-2026-09-05-01 */
.food-legend{display:flex;flex-wrap:wrap;gap:7px;margin:0 2px 10px}.food-role{display:inline-flex;align-items:center;width:max-content;border-radius:999px;padding:4px 8px;font-size:11px;font-weight:850;line-height:1.2;background:#efefeb;color:#595f5b}.food-role.carrier{background:var(--green2);color:var(--green)}.food-role.conditional{background:var(--amber);color:#7d641e}.food-role.verify{background:var(--blue);color:#315d73}.food-role.fallback{background:#efefeb;color:#595f5b}.food-role.market{background:var(--orange);color:#855124}.food-role.park{background:var(--green2);color:var(--green)}.food-stack{display:grid;gap:10px}.food-region{border:1px solid var(--line);background:var(--paper);box-shadow:var(--shadow);border-radius:18px;overflow:hidden;scroll-margin-top:12px}.food-region>summary{cursor:pointer;list-style:none;display:flex;justify-content:space-between;align-items:center;gap:12px;min-height:58px;padding:13px 14px}.food-region>summary::-webkit-details-marker{display:none}.food-region>summary:after{content:'＋';color:var(--green);font-size:18px;font-weight:900;flex:none}.food-region[open]>summary:after{content:'−'}.food-region>summary strong{font-size:15px}.food-region>summary span{color:var(--muted);text-align:right;font-size:11px;line-height:1.35;max-width:52%}.food-region-body{border-top:1px solid var(--line)}.food-row{display:grid;grid-template-columns:78px minmax(0,1fr);gap:9px 11px;padding:12px 13px;border-top:1px solid var(--line)}.food-row:first-child{border-top:0}.food-slot{color:var(--green);font-size:12px;font-weight:900}.food-titleline{display:flex;flex-wrap:wrap;align-items:center;gap:7px}.food-titleline strong{font-size:14px}.food-main p{color:var(--muted);margin:4px 0 0;font-size:12px;line-height:1.5}.food-maps{grid-column:2;display:flex;flex-wrap:wrap;gap:6px}.food-row .map-button,.queue-jump{min-height:34px;padding:7px 9px;border-radius:10px;font-size:11px;text-decoration:none}.queue-jump{display:inline-flex;align-items:center;background:var(--blue);color:#315d73;font-weight:850}.food-note{margin:12px 0 0}.queue-inline{color:var(--green);font-weight:850}@media (width>=600px){.food-row{grid-template-columns:96px minmax(0,1fr) auto}.food-maps{grid-column:3;justify-content:flex-end;max-width:240px}.food-region>summary span{max-width:none}}
"""

stale = [
    "Central dynamic breakfast", "Central dynamic queue",
    "不是第七張 Card", "grid-template-columns:repeat(4,1fr)",
]
for text in stale:
    if text in html or text in page or text in css:
        raise SystemExit(f"stale inconsistency remains: {text}")

required = [
    "Central / Cosy｜Food Queue", "吃飯 Queue", "food-central",
    "food-vinwonders", "food-south", "food-ganhdau", "food-grandworld",
    "Google Maps", "OnBird + optional DD",
    "Cable 日不再安排 Dinh Cậu 或其他 DD 停留",
]
for text in required:
    if text not in html and text not in page:
        raise SystemExit(f"missing required site marker: {text}")
if html.count("www.google.com/maps/search/?api=1") < 15:
    raise SystemExit("too few static Google Maps links")

hp.write_text(html)
jp.write_text(page)
cp.write_text(css)

manifest = json.loads(mp.read_text())
manifest["ux_coherence_patch_id"] = PATCH_ID
manifest["ux_coherence_scope"] = "PUBLIC_GITHUB_PAGES_STAGING_ONLY"
manifest["food_queue_ui"] = "LOCATION_TIME_REGIONAL_QUEUE_WITH_SNACKS_AND_GOOGLE_MAPS"
manifest["regional_food_queue_name"] = "Central / Cosy｜Food Queue"
manifest["site_language_consistency"] = "NORMALIZED_TRAVEL_FACING"
manifest["bottom_nav_columns"] = 5
manifest["canonical_cutover"] = False
mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

print("SITE_COHERENCE_PATCH_ASSERTIONS=PASS")
