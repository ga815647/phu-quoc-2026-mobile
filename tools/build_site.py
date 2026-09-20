"""Build data-driven static site from data/*.json.

Reads: data/snapshot.json (foods/carriers/points/cards/bookings/transport/meta)
Writes: data.html (single-file, inline CSS/JS, fetch()es data/*.json at runtime)

Design contract (from v2.html, keep):
- sticky nav: 今天 / Cards / 美食 / 出發前，instant scroll, no hash
- localStorage: slot picks + eaten ticks, per-device, reset buttons
- food pool order + copy stays human-curated here; DB supplies status/grade/maps/verified badges
- 5 cards; anthoi=optional satellite; khem=retired (not rendered as card)
"""
import json
import html as h
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# Human-curated pool order: (food-id, match-substring, order-copy, desc-copy, role-badge)
POOL = [
 ("bun-ken-ut-luom", "Bún Kèn Út Lượm", "Bún kèn",
  "富國島地方味優先完成；椰奶魚風味米線。Út Lượm 沒吃到再看 bún kèn 87 backup。", "carrier", "主池｜這趟優先完成"),
 ("banh-mi-anh-thu", "Bánh mì Anh Thư", "Bánh mì",
  "高優先、低摩擦；很適合塞進行程空檔或晚一點快速吃。", "carrier", None),
 ("banh-canh-phung", "Bánh Canh Phụng", "Bánh canh cá",
  "魚湯粗粉類；早段機會比較珍貴，時間對就值得先完成。", "carrier", None),
 ("bun-mam-dung-ha", "Bún Mắm Dung Hà", "Bún mắm",
  "偏南部、發酵魚醬風味；想吃重一點的在地味時優先，營業窗再現場確認。", "conditional", None),
 ("nhum-8k", "Nhum nướng 8K", "Nhum nướng mỡ hành",
  "烤海膽＋蔥油；只在尚未完成 Nhum 時追，先確認有貨、做法與當日價。", "conditional", None),
 ("banh-kheo-co-dung", "bánh Khéo cô Dung", "Bánh khéo 綜合幾種口味",
  "小顆、多口味，適合分食；不用硬塞在「下午茶」時段。", "fallback", None),
 ("duong-dong-market", "Chợ Dương Đông", "Bánh tét mật cật → kẹo chỉ / bánh bò thốt nốt → dừa sáp dầm thốt nốt；水果看 bòn bon / 榴槤",
  "熟食與小吃優先，不追固定攤；看到現做、熱賣的再買。", "market", None),
 ("nha-xua-68", "Nhà Xưa 68", "沒有鎖定單一必點；看當日家常菜＋白飯",
  "孩子累、想舒服坐下、正餐時間亂掉時很好用。", "fallback", None),
 ("com-tam-nhi", "Cơm tấm Nhị", "Cơm tấm",
  "想快速坐下吃一份飯時用；是實用 fallback，不是必追名店。", "fallback", None),
 ("bup-seafood", "BUP Seafood", "Nhum nướng mỡ hành（只有前面還沒吃到 Nhum）",
  "Cable 回島後才有意義；stock / preparation / price gate 都過才用。", "conditional", "區域備案｜人在那裡才看"),
 ("vinwonders-inside", None, "園內就近、孩子能吃的熱食",
  "沒有鎖定必吃店；正常或孩子累時，園內解決比為吃飯硬接 Grand World 更合理。", "fallback", None),
 ("wow-que-toi", "WOW QUÊ TÔI", "沒有鎖定必點；選當下現做熱食正餐",
  "南島低摩擦 fallback，不升 Dish Carrier。", "fallback", None),
 ("quoc-thien", "Quoc Thien", "熟食海鮮；先問秤重單價＋加工費",
  "Safari → Gành Dầu daylight tail 的目前第一現場備案；不是 protocol-certified winner。", "verify", None),
 ("phuc-ngan", "Phúc Ngân", "熟海鮮；若有熟 Nhum / còi biên mai 可優先問",
  "Gành Dầu 第二備案；目前證據不足以升 Carrier。", "verify", None),
 ("bep-nha-grandworld", "Bếp Nhà Restaurant", "目前沒有足夠證據指定必點；當越式正餐 fallback",
  "人在 Grand World 才用；不因為它存在就把 Grand World 接進行程。", "verify", None),
 ("com-nha-grandworld", "Cơm Nhà Phú Quốc", "家常飯菜；目前沒有 protocol-valid 必點",
  "family-style 第二備案；review-integrity 仍有疑慮。", "verify", None),
 ("an-thoi-market", "Chợ An Thới", "當下現做熟食／小吃，水果其次",
  "不是為市場硬排時間；剛好在 An Thới 才逛。", "market", None),
 ("ganh-dau-market", "Chợ Gành Dầu", "現做、熱賣的熟食",
  "只在 Safari daylight tail 已經到 Gành Dầu 時順手看。", "market", None),
]

ROLE_LABEL = {"carrier": "Carrier", "conditional": "條件式 Carrier",
              "fallback": "現場備案", "market": "Market Node", "verify": "VERIFY"}


def load():
    snap = json.loads((DATA / "snapshot.json").read_text())
    byname = {}
    for f in snap["foods"]:
        byname.setdefault(f["name"], f)
    return snap, byname


def find(byname, sub):
    if sub is None:
        return None
    for name, f in byname.items():
        if sub.lower() in name.lower():
            return f
    return None


def gmap(query, label="地圖"):
    from urllib.parse import quote_plus
    q = quote_plus((query or label) + " Phú Quốc")
    return (f'<a class="map" target="_blank" rel="noopener" '
            f'href="https://www.google.com/maps/search/?api=1&query={q}">{h.escape(label)}</a>')


def status_badge(f):
    if f is None:
        return ""
    parts = []
    if f.get("atlas_state") == "ACTIVE":
        parts.append('<span class="role carrier">ACTIVE</span>')
    elif f.get("atlas_state") == "VERIFY":
        parts.append('<span class="role verify">VERIFY</span>')
    elif f.get("atlas_state") == "DEACTIVATED":
        parts.append('<span class="role red">已下架</span>')
    ver = f.get("last_verified") or f.get("evidence_as_of") or ""
    if ver:
        parts.append(f'<span class="food-region">驗證 {h.escape(str(ver))}</span>')
    return "".join(parts)


def build_food_pool(byname):
    out = []
    rank = 0
    for fid, sub, order, desc, role, divider in POOL:
        if divider:
            out.append(f'<div class="pool-divider">{h.escape(divider)}</div>')
        rank += 1
        f = find(byname, sub)
        if f is None:
            name, region = fid, "—"
            badge, mlink = "", ""
        else:
            name = f["name"].split("｜")[0]
            region = f.get("region") or "—"
            badge = status_badge(f)
            mlink = gmap(f.get("maps_query") or f["name"])
        out.append(
            f'<article class="food-card" data-food-id="{fid}">'
            f'<div class="food-rank">{rank:02d}</div><div class="food-info">'
            f'<div class="food-name">{h.escape(name)}</div>'
            f'<div class="food-meta"><span class="food-region">{h.escape(region)}</span>'
            f'<span class="role {role}">{ROLE_LABEL[role]}</span>{badge}</div>'
            f'<p class="food-order"><span>點：</span>{h.escape(order)}</p>'
            f'<p class="food-desc">{h.escape(desc)}</p></div>'
            f'<div class="food-actions">{mlink}'
            f'<button class="eaten-btn" type="button" aria-pressed="false">○ 未吃</button>'
            f"</div></article>")
    return "\n".join(out), rank


CSS = open(ROOT / "tools" / "site.css").read() if (ROOT / "tools" / "site.css").exists() else ""


def main():
    snap, byname = load()
    pool_html, n_food = build_food_pool(byname)
    cards = [c for c in snap["cards"] if c["status"] == "ACTIVE"]
    bookings = snap["bookings"]
    meta = snap.get("meta", {})

    page = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#f4f6f1">
<title>富國島 2026｜執行站（data-driven）</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header class="hero">
<div class="eyebrow">PHU QUOC 2026 · DATA-DRIVEN · {h.escape(str(meta.get("source", "")))}</div>
<h1>照著走，<br>不用一直想。</h1>
<p>1 大 1 小 · Cosy Bungalow 單一基地 · 10/10–10/15 · 5 張 Day Cards（An Thới optional，Khem retired）</p>
<div class="hero-grid">
<div class="status"><b>已確認</b><strong>10/11 OnBird</strong><span>回 Cosy 先休息；預排 Dinh Cậu／河口 + DD evening，累就取消</span></div>
<div class="status"><b>旅行核心</b><strong>5 張 Day Cards</strong><span>Cable · VinWonders · OnBird · Starfish · Safari</span></div>
</div>
</header>
</div>
<div class="sticky"><nav class="nav" aria-label="快速導覽"><button class="primary" data-jump="today">今天</button><button data-jump="cards">Cards</button><button data-jump="food">美食</button><button data-jump="prep">出發前</button></nav></div>
<div class="wrap">
<section class="section" id="today">
<div class="section-head"><h2>今天怎麼決定</h2><span>只留真的會用到的資訊</span></div>
<div class="panel pad"><div class="label">CURRENT STATE</div><div class="today-big">10/11 已確認；10/12–10/14 保持彈性</div><div class="tiny">T−72 只暫排；每晚 T−1 只鎖隔天。</div><div class="choice-grid"><div class="choice"><strong>🚠 Cable</strong><span>最高優先。早餐後直接 Ga Ánh Dương，不插 DD micro-stop。</span></div><div class="choice"><strong>🎢 VinWonders</strong><span>Sea Shell first；Grand World 只有 early exit + 孩子 Green 才接。</span></div><div class="choice"><strong>⭐ Starfish</strong><span>七項 gate + 48h 現況全綠才成立。</span></div><div class="choice"><strong>🦒 Safari</strong><span>只有真的想去才排；tail 二選一，不自動綁 Grand World。</span></div></div></div>
<div class="section-head" style="margin-top:20px"><h2>四天排牌</h2><span>只存在這支手機</span></div>
<div class="panel pad"><div class="slot-list"><div class="slot"><div class="date"><b>10/11 Sun</b><small>OnBird confirmed</small></div><div class="locked">🤿 OnBird + Dinh Cậu／河口 + DD evening</div></div><div class="slot"><div class="date"><b>10/12 Mon</b><small>flex</small></div><select data-day="10/12"><option value="">尚未鎖定</option><option>Cable + Sunset Town</option><option>VinWonders</option><option>Starfish conditional</option><option>Safari</option><option>Free / Recovery</option></select></div><div class="slot"><div class="date"><b>10/13 Tue</b><small>flex</small></div><select data-day="10/13"><option value="">尚未鎖定</option><option>Cable + Sunset Town</option><option>VinWonders</option><option>Starfish conditional</option><option>Safari</option><option>Free / Recovery</option></select></div><div class="slot"><div class="date"><b>10/14 Wed</b><small>flex</small></div><select data-day="10/14"><option value="">尚未鎖定</option><option>Cable + Sunset Town</option><option>VinWonders</option><option>Starfish conditional</option><option>Safari</option><option>Free / Recovery</option></select></div></div><div class="row-actions"><button class="ghost" id="resetSlots">清除暫排</button></div></div>
</section>
<section class="section" id="cards">
<div class="section-head"><h2>5 張 Day Cards</h2><span>點開才看細節 · 資料來自 SQLite 快照</span></div>
<div class="cards" id="cardsMount"></div>
</section>
<section class="section" id="food">
<div class="section-head"><h2>美食 Pool</h2><span>優先順序＋吃過紀錄 · badge 來自 DB 即時狀態</span></div>
<div class="food-guide"><b>網站不替你判斷「現在該吃誰」</b><p>要吃的時候直接跟 ChatGPT 說：「現在 16:20，我在 Sunset Town，孩子狀態 Green。」我再依時間、位置、營業與你已吃過的項目重排。這裡只保留候選 Pool。</p></div>
<div class="pool-top"><div class="pool-progress" id="foodProgress">已吃 0 / {n_food}</div><button class="ghost" id="resetFood">重設吃過</button></div>
<div class="food-pool">
{pool_html}
</div>
<div class="pool-note">排序代表「這趟值得優先完成」而不是此刻推薦；真正要吃時，由 ChatGPT 用現在時間＋所在區域＋已吃狀態重新排。吃過紀錄只存在這支手機。</div>
</section>
<section class="section" id="prep">
<div class="section-head"><h2>出發前只查這些</h2><span>不要重新研究整趟</span></div>
<div class="panel pad"><div class="prep-grid"><div class="prep"><b>🤿 OnBird</b><span>接送時間、當天海況、是否照常出發；現場仍依教練安全評估。</span></div><div class="prep"><b>🚠 Cable</b><span>10 月第一波纜車時段、回程／末班、是否維修、天氣。</span></div><div class="prep"><b>🎢 VinWonders</b><span>園區營業與餐飲時段、票價／直訂價格、兒童設施限制；Grand World 仍是有體力才接。</span></div><div class="prep"><b>⭐ Starfish</b><span>前 48 小時確認路況、海星、水色、船與回程；七項條件全過才去。</span></div><div class="prep"><b>🦒 Safari</b><span>營業時間、直達叫車與北島回程；若去 Gành Dầu，先把回程車談好並在 17:00 前離開。</span></div><div class="prep"><b>🍜 Food</b><span>只查明天可能吃的店：是否營業、想點的東西有沒有、價格；真的要吃時再問 ChatGPT。</span></div></div><div class="callout" style="margin-top:12px"><b>前一天下午 15:00–17:00：</b>只確認明天。若預約、官方營運、回程交通、住宿與孩子限制都沒變，就不要重新研究整趟。</div></div>
<div class="section-head" style="margin-top:20px"><h2>交通底線</h2><span>簡化成可執行規則</span></div>
<div class="panel pad"><div class="prep-grid"><div class="prep"><b>市區／主要景點</b><span>Grab／GreenSM／taxi 都可；機場、Ga Ánh Dương、VinWonders、Safari 直接叫車。</span></div><div class="prep"><b>偏遠地點／多停點</b><span>出發前先確認回程；回程沒把握就不去。</span></div><div class="prep"><b>App 叫不到</b><span>5–10 分鐘還沒派車就換另一個 app 或 taxi；巴士還要等 15–20 分鐘以上就改叫車。</span></div><div class="prep"><b>孩子</b><span>約 115 cm，全程後座；長程優先三點式安全帶＋增高墊／兒童座椅。</span></div></div></div>
</section>
<footer class="footer">data-driven build · 來源 Notion ETL {h.escape(str(meta.get("source", "")))} · 卡規則：{h.escape(str(meta.get("cards_rule", "")))}<br>吃過／暫排只存這支手機（localStorage）。</footer>
</div>
<script>
(function(){{
const sticky=document.querySelector('.sticky');
const navButtons=[...document.querySelectorAll('[data-jump]')];
const navIds=navButtons.map(btn=>btn.dataset.jump);
function setActiveNav(id){{navButtons.forEach(btn=>btn.classList.toggle('primary',btn.dataset.jump===id))}}
function syncNav(){{const offset=sticky.offsetHeight+18;let current=navIds[0];navIds.forEach(id=>{{const el=document.getElementById(id);if(el&&el.getBoundingClientRect().top<=offset)current=id}});setActiveNav(current)}}
navButtons.forEach(btn=>btn.addEventListener('click',()=>{{const el=document.getElementById(btn.dataset.jump);if(!el)return;const y=el.getBoundingClientRect().top+window.scrollY-(sticky.offsetHeight+8);window.scrollTo(0,Math.max(0,y));setActiveNav(btn.dataset.jump);requestAnimationFrame(syncNav)}}));
let navTick=false;window.addEventListener('scroll',()=>{{if(navTick)return;navTick=true;requestAnimationFrame(()=>{{syncNav();navTick=false}})}},{{passive:true}});window.addEventListener('resize',syncNav);syncNav();
const slotKey='phq-v2-slots';let saved={{}};try{{saved=JSON.parse(localStorage.getItem(slotKey)||'{{}}')}}catch(e){{}}document.querySelectorAll('select[data-day]').forEach(sel=>{{if(saved[sel.dataset.day])sel.value=saved[sel.dataset.day];sel.addEventListener('change',()=>{{saved[sel.dataset.day]=sel.value;localStorage.setItem(slotKey,JSON.stringify(saved))}})}});document.getElementById('resetSlots').addEventListener('click',()=>{{if(!window.confirm('清除所有暫排行程？'))return;saved={{}};localStorage.removeItem(slotKey);document.querySelectorAll('select[data-day]').forEach(s=>s.value='')}});
const foodKey='phq-v2-food-eaten';let eaten={{}};try{{eaten=JSON.parse(localStorage.getItem(foodKey)||'{{}}')}}catch(e){{}}const foodCards=[...document.querySelectorAll('[data-food-id]')],foodProgress=document.getElementById('foodProgress');function renderFood(){{let count=0;foodCards.forEach(card=>{{const id=card.dataset.foodId,isEaten=!!eaten[id];if(isEaten)count++;card.classList.toggle('eaten',isEaten);const btn=card.querySelector('.eaten-btn');if(btn){{btn.setAttribute('aria-pressed',String(isEaten));btn.textContent=isEaten?'✓ 吃過':'○ 未吃'}}}});if(foodProgress)foodProgress.textContent=`已吃 ${{count}} / ${{foodCards.length}}`}}foodCards.forEach(card=>{{const btn=card.querySelector('.eaten-btn');if(!btn)return;btn.addEventListener('click',()=>{{const id=card.dataset.foodId;eaten[id]=!eaten[id];if(!eaten[id])delete eaten[id];localStorage.setItem(foodKey,JSON.stringify(eaten));renderFood()}})}});document.getElementById('resetFood').addEventListener('click',()=>{{if(!window.confirm('清除所有「吃過」紀錄？'))return;eaten={{}};localStorage.removeItem(foodKey);renderFood()}});renderFood();
fetch('./data/cards.json').then(r=>r.json()).then(cards=>{{
  const mount=document.getElementById('cardsMount');
  const active=cards.filter(c=>c.status==='ACTIVE');
  mount.innerHTML=active.map(c=>{{
    let gates=[];try{{gates=JSON.parse(c.gates||'[]')}}catch(e){{}}
    return `<details class="trip"><summary><div class="trip-title"><div><h3>${{c.name}}</h3>`
      +`<div class="trip-summary">${{c.notes||''}} · 驗證 ${{c.evidence_as_of||''}}</div>`
      +`<div class="badges"><span class="badge brand">${{c.status}}</span></div></div><div class="arrow">＋</div></div></summary>`
      +`<div class="inside"><div class="timeline"><div class="step"><div class="time">路線</div><div><b>Route</b><p>${{c.route||''}}</p></div></div>`
      +`<div class="step"><div class="time">交通</div><div><b>Transport</b><p>${{c.transport||''}}</p></div></div></div>`
      +`<ul class="mini-list">${{gates.map(g=>`<li>${{g}}</li>`).join('')}}</ul></div></details>`;
  }}).join('');
}}).catch(()=>{{document.getElementById('cardsMount').innerHTML='<div class="callout red">cards.json 載入失敗（file:// 直開會擋 fetch，請用 Pages 或本地 server 看）。</div>'}});
}})();
</script>
</body>
</html>"""
    (ROOT / "data.html").write_text(page)
    print("wrote data.html", len(page), "bytes;", n_food, "food cards;",
          len(cards), "active cards rendered client-side")


if __name__ == "__main__":
    main()
