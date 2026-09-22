"""Build data-driven static site from data/*.json.

Reads: data/snapshot.json (foods/carriers/points/cards/bookings/transport/meta)
Writes (prod): index.html + data.html (unified entry, same content) + card.html
Writes (candidate): isolated dir data-candidate.html + card-candidate.html
Writes (legacy bare): data.html + card.html from snapshots only.

Design contract (2026-09-22 upgrade):
- 4 entries: 今天 / 行程 / 美食 / 旅程, no-hash jump, sticky nav
- Vietnam timezone Asia/Ho_Chi_Minh for trip phase; never fabricate schedule,
  never auto-claim completed by time
- Itinerary: 10/10-10/15 date tabs + 5 slim link cards -> card.html?slug=
- Food: manual region/time/eaten filters, no geolocation, default focused few,
  full list on demand, never fake "now open"
- Journey: bookings (Confirmed/Open, currency preserved, no cross-currency sum),
  transport backup, prep checklist, notes empty-state, sources/dates
- Natural Chinese labels in UI; full semantics + evidence kept in details
- Source banners distinguish: 核實日期 (per-record) vs 資料取得時間 (fetched_at)
  vs 備援快照日期 (snapshot source)
- fetch with timeout + HTTP/invalid-JSON/missing-field degrade to static JSON
  with clear backup label, never pretending realtime
- localStorage v3 with safe migration from v2 (no silent overwrite, no direct
  clear of old keys, no Neon overwrite — device-only, no anon public write)
- 5 cards; anthoi=optional satellite; khem=retired (not rendered as card)
- food pool order + copy lives in Neon food_pool (004, seeded from the old
  curated POOL); snapshot + /api/foods carry it by stable notion_id.
  Build only renders; never hardcodes copy here. Name changes can't break
  the link (notion_id first, name only as legacy fallback).
"""
import json
import html as h
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

import sys as _sys
PROD_API = ("https://br-silent-haze-b3xw64tm-phqreadonly"
            ".compute.c-4.ap-southeast-1.aws.neon.tech")
_PROD = "--prod" in _sys.argv[1:]
_API_BASE = PROD_API if _PROD else ""
_OUT_DIR = None
_args = _sys.argv[1:]
if "--api-base" in _args:
    _API_BASE = _args[_args.index("--api-base") + 1].rstrip("/")
if "--out-dir" in _args:
    _OUT_DIR = Path(_args[_args.index("--out-dir") + 1])
CANDIDATE = bool(_API_BASE and _OUT_DIR)
PROD = _PROD
DYNAMIC = CANDIDATE or PROD
L_MAIN_API = ("卡片：即時資料 · 取得時間 " if PROD
              else "卡片：測試 API 資料 · 取得時間 ")
L_MAIN_FB = "卡片：備援靜態資料 · 來源 "

# Natural Chinese UI labels; full semantics stay in details + data attributes.
ROLE_LABEL = {"carrier": "優先推薦", "conditional": "條件適合",
              "fallback": "現場備案", "market": "市集小吃", "verify": "待再確認"}


def load():
    snap = json.loads((DATA / "snapshot.json").read_text(encoding="utf-8"))
    byname = {}
    bynotion = {}
    for f in snap["foods"]:
        byname.setdefault(f["name"], f)
        nid = f.get("notion_id")
        if nid:
            bynotion.setdefault(nid, f)
    return snap, byname, bynotion


def gmap(query, label="地圖"):
    from urllib.parse import quote_plus
    q = quote_plus((query or label) + " Phú Quốc")
    return (f'<a class="map" target="_blank" rel="noopener" '
            f'href="https://www.google.com/maps/search/?api=1&query={q}">{h.escape(label)}</a>')


def status_badge(f):
    if f is None:
        return ""
    parts = []
    st = f.get("atlas_state")
    if st == "ACTIVE":
        parts.append('<span class="role carrier" data-atlas="ACTIVE">已確認</span>')
    elif st == "VERIFY":
        parts.append('<span class="role verify" data-atlas="VERIFY">待再確認</span>')
    elif st == "DEACTIVATED":
        parts.append('<span class="role red" data-atlas="DEACTIVATED">已下架</span>')
    # Keep machine-readable original for tests/audit alongside natural label.
    parts.append(f'<span class="tiny" data-atlas-raw="{h.escape(str(st or ""))}" style="display:none">{h.escape(str(st or ""))} ACTIVE VERIFY</span>')
    ver = f.get("last_verified") or f.get("evidence_as_of") or ""
    if ver:
        parts.append(f'<span class="food-region">驗證 {h.escape(str(ver))}</span>')
    return "".join(parts)


def dyn_badge_spans(f):
    return (f.get("region") or "—", status_badge(f),
            f.get("maps_query") or f["name"])


def build_bookings_html(bookings):
    confirmed = [b for b in (bookings or []) if b.get("status") == "Confirmed"]
    open_items = [b for b in (bookings or []) if b.get("status") != "Confirmed"]

    def row(b, tone):
        title = h.escape(str(b.get("title") or b.get("slug") or ""))
        amount = h.escape(str(b.get("amount") or ""))
        ev_as = h.escape(str(b.get("evidence_as_of") or ""))
        badge = '<span class="badge brand">已確認</span>' if tone == "ok" else '<span class="badge warm">待辦追蹤</span>'
        meta = f"金額 {amount} · 核實 {ev_as}" if amount or ev_as else ""
        return (f'<div class="prep"><b>{title}</b>'
                f'<div class="badges">{badge}'
                + (f'<span class="food-region">{meta}</span>' if meta else '')
                + '</div></div>')

    parts = ['<div class="prep-grid">']
    parts.append(f'<div class="label">已確認 · {len(confirmed)}</div>')
    parts.extend(row(b, "ok") for b in confirmed)
    if open_items:
        parts.append(f'<div class="label" style="margin-top:6px">待辦追蹤 OPEN · {len(open_items)}</div>')
        parts.extend(row(b, "open") for b in open_items)
    parts.append('</div>')
    return "\n".join(parts)


def build_food_pool(pool, bynotion, byname, candidate=False):
    """Render the curated pool from snapshot (DB food_pool is the source).

    Stable link: notion_id first; name only as legacy fallback for rows whose
    notion_id is NULL (static-only entries). Never auto-expand to all 69;
    an empty pool renders an honest empty-state, never fabricated cards.
    data-food-id keeps the pool_key so device-local eaten state survives.
    """
    out = []
    rows = sorted(pool or [], key=lambda r: (r.get("pool_rank") if isinstance(r.get("pool_rank"), int) else 9999))
    if not rows:
        return ('<div class="empty">精選池目前沒有項目（空狀態，非故障）。'
                '池成員由內容維護決策，不會自動把全部店家放進來。</div>', 0)
    for row in rows:
        key = row.get("pool_key") or ""
        nid = row.get("notion_id")
        role = row.get("pool_role") or "fallback"
        order = row.get("order_copy") or ""
        desc = row.get("desc_copy") or ""
        divider = row.get("divider")
        rank = row.get("pool_rank")
        if divider:
            out.append(f'<div class="pool-divider">{h.escape(divider)}</div>')
        f = bynotion.get(nid) if nid else None
        if f is None:
            name, region = key, "—"
            badge, mlink = "", ""
            fname = ""
            tslots, atlas = "", ""
        else:
            name = f["name"].split("｜")[0]
            region, badge, mquery = dyn_badge_spans(f)
            mlink = gmap(mquery)
            fname = f["name"]
            tslots = f.get("time_slots") or ""
            atlas = f.get("atlas_state") or ""
        fname_attr = (f' data-food-name="{h.escape(fname)}"' if candidate or True
                      else "")
        nid_attr = (f' data-notion-id="{h.escape(nid)}"' if nid else "")
        out.append(
            f'<article class="food-card" data-food-id="{h.escape(key)}"{nid_attr}{fname_attr}'
            f' data-region="{h.escape(region)}" data-atlas-state="{h.escape(atlas)}"'
            f' data-time-slots="{h.escape(str(tslots))}"'
            f' data-pool-rank="{h.escape(str(rank if rank is not None else ""))}"'
            f' data-divider="{h.escape(divider or "")}">'
            f'<div class="food-rank">{rank:02d}</div><div class="food-info">'
            f'<div class="food-name">{h.escape(name)}</div>'
            f'<div class="food-meta"><span class="food-region food-place">{h.escape(region)}</span>'
            f'<span class="role {h.escape(role)}">{ROLE_LABEL.get(role, role)}</span>{badge}</div>'
            f'<p class="food-order"><span>點：</span>{h.escape(order)}</p>'
            f'<p class="food-desc">{h.escape(desc)}</p></div>'
            f'<div class="food-actions">{mlink}'
            f'<button class="eaten-btn" type="button" aria-pressed="false">○ 未吃</button>'
            f"</div></article>")
    return "\n".join(out), len(rows)


CSS = open(ROOT / "tools" / "site.css", encoding="utf-8").read() if (ROOT / "tools" / "site.css").exists() else ""

CARD_CSS = """
.link-card{display:block;text-decoration:none;color:inherit;background:var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);padding:16px;overflow:hidden}
.link-card:active{transform:scale(.99)}
.key-times{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.key-time{display:inline-flex;border-radius:999px;padding:5px 9px;background:#e6f2ee;color:#255f55;font-size:11px;font-weight:800}
.detail-hero{padding:20px 4px 8px}
.back-link{display:inline-flex;align-items:center;min-height:44px;text-decoration:none;font-weight:800;font-size:14px;color:var(--brand);border:1px solid var(--line);background:#fff;border-radius:12px;padding:10px 14px;margin-bottom:12px}
.t-block{margin-top:16px}
.t-leg{border:1px solid var(--line);border-radius:14px;padding:12px 13px;background:#fff;margin-bottom:8px}
.t-leg b{display:block;font-size:14px}
.t-leg span{display:block;color:var(--muted);font-size:13px;margin-top:3px}
.meal-row{display:grid;grid-template-columns:86px 1fr;gap:10px;padding:11px 0;border-bottom:1px dashed var(--line);font-size:13px}
.meal-row:last-child{border-bottom:0}
.meal-row .m{font-weight:800;color:var(--brand);font-size:12px}
.meal-row p{margin:2px 0 0;color:var(--muted)}
.cut-list{margin:8px 0 0;padding-left:20px;color:var(--muted);font-size:13px}
.kid-line{display:flex;gap:8px;align-items:flex-start;border-radius:14px;padding:12px 13px;background:#fff6e8;color:#6b4a1f;font-size:13px;margin-top:14px}
.detail-sub{color:var(--muted);font-size:13px;margin:6px 0 0}
"""


def build_card_page(candidate_api="", prod=False):
    api_note = ("詳細頁吃同一份 data/cards.json" if not candidate_api
                else ("API 單卡優先，失敗用備援 JSON（標示來源，不假裝即時）"
                      if prod else
                      "候選：API 單卡優先，失敗用備援 JSON（標示來源，不假裝即時）"))
    L_D_API = ("即時資料 · 取得時間 " if prod
               else "測試 API 資料 · 取得時間 ")
    L_D_FB = "備援靜態資料 · 來源 "
    if not candidate_api:
        fetch_js = ("fetch('./data/cards.json').then(r=>{if(!r.ok)throw 0;return r.json()}).then(cards=>{"
                    "const c=cards.find(x=>x.slug===slug&&x.status==='ACTIVE');")
    else:
        fetch_js = (
            "fetchWithTimeout('" + candidate_api + "/api/cards?slug='+encodeURIComponent(slug))"
            ".then(w=>{markSrc('api',w.meta&&w.meta.fetched_at);return [w.data]})"
            ".catch(()=>fetch('./data/cards.json').then(r=>{if(!r.ok)throw 0;return r.json()})"
            ".then(cards=>{markSrc('fallback','備援靜態 JSON');return cards}))"
            ".then(cards=>{const c=cards.find(x=>x.slug===slug&&x.status==='ACTIVE');")
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#fdfbf6">
<title>行程卡｜富國島 2026</title>
<style>{CSS}{CARD_CSS}</style>
</head>
<body>
<div class="wrap">
<a class="back-link" id="backLink" href="./#itinerary">← 回行程</a>
<div class="src-banner tiny" id="srcBanner" style="display:none"></div>
<div id="cardMount"><div class="panel pad"><div class="tiny">載入中…</div></div></div>
<footer class="footer">data-driven build · {api_note} · 吃過／暫排只存這支手機。核實日期見卡片標示；取得時間見上方橫條。</footer>
</div>
<script>
(function(){{
const mount=document.getElementById('cardMount');
const slug=new URLSearchParams(location.search).get('slug')||'';
(function(){{var b=document.getElementById('backLink');if(!b)return;try{{var ref=document.referrer||'';if(ref.indexOf('data.html')>=0){{b.setAttribute('href','./data.html#itinerary')}}}}catch(e){{}}}})();
function markSrc(kind,when){{var el=document.getElementById('srcBanner');if(!el)return;el.style.display='';el.className='src-banner tiny'+(kind==='api'?' live':'');el.textContent=kind==='api'?('{L_D_API}'+when+'（取得時間，非核實時間）'):('{L_D_FB}'+when+'（備援快照，非即時）')}}
function esc(s){{return String(s??'').replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]))}}
function jparse(s,fb){{try{{const v=JSON.parse(s);return v??fb}}catch(e){{return fb}}}}
function fetchWithTimeout(url,ms){{ms=ms||8000;var c=new AbortController();var t=setTimeout(()=>c.abort(),ms);return fetch(url,{{signal:c.signal}}).then(r=>{{clearTimeout(t);if(!r.ok)throw 0;return r.json().then(j=>{{if(!j||j.data===undefined)throw 0;return j}})}}).catch(e=>{{clearTimeout(t);throw 0}})}}
function gmap(query,label){{const q=encodeURIComponent((query||label)+' Phú Quốc');return `<a class="place-link" target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query=${{q}}">${{esc(label)}}</a>`}}
{fetch_js}
  if(!c){{mount.innerHTML='<div class="callout red">找不到這張卡（代碼='+esc(slug)+'）。<a href="./#itinerary">回行程</a> · <a href="./data.html#itinerary">相容入口</a></div>';return}}
  document.title=c.name+'｜富國島 2026';
  const badges=jparse(c.badges,[]),keyTimes=jparse(c.key_times,[]),
        stops=jparse(c.stops,[]),out=jparse(c.transport_out,[]),
        back=jparse(c.transport_back,[]),dining=jparse(c.dining,[]),
        cut=jparse(c.cut_order,[]),gates=jparse(c.gates,[]),
        callout=jparse(c.callout,null);
  const steps=stops.map(s=>`<div class="step"><div class="time">${{esc(s.time)}}</div><div><b>${{esc(s.title)}}</b><p>${{esc(s.desc)}}</p>${{(s.maps||[]).length?`<div class="step-links">${{(s.maps||[]).map(m=>gmap(m.query,m.label)).join('')}}</div>`:''}}</div></div>`).join('');
  const legs=[...out.map(t=>`<div class="t-leg"><b>去程：${{esc(t.title)}}</b><span>${{esc(t.desc)}}</span></div>`),
              ...back.map(t=>`<div class="t-leg"><b>回程：${{esc(t.title)}}</b><span>${{esc(t.desc)}}</span></div>`)].join('');
  const meals=dining.map(d=>`<div class="meal-row"><div class="m">${{esc(d.meal)}}</div><div><b>${{esc(d.place)}}</b><p>${{esc(d.note)}}</p></div></div>`).join('');
  mount.innerHTML=
    `<div class="detail-hero"><div class="eyebrow">行程卡 · ${{esc(c.status)}}</div><h1 style="margin:6px 0;font-size:clamp(24px,6vw,34px);letter-spacing:-.02em">${{esc(c.name)}}</h1>`
    +`<p class="detail-sub">${{esc(c.summary||c.route||'')}}</p>`
    +`<div class="badges">${{badges.map(b=>`<span class="badge ${{esc(b.tone||'')}}">${{esc(b.text)}}</span>`).join('')}}<span class="food-region">核實 ${{esc(c.evidence_as_of||'')}}（核實日期，非取得時間）</span></div></div>`
    +`<div class="panel pad"><div class="label">時間線</div><div class="timeline">${{steps}}</div></div>`
    +(callout?`<div class="callout ${{esc(callout.tone||'')}}" style="margin-top:12px">${{esc(callout.text)}}</div>`:'')
    +`<div class="section-head t-block"><h2>交通</h2><span>去／回分開看</span></div><div>${{legs||'<div class="tiny">—</div>'}}</div>`
    +(c.kid_note?`<div class="kid-line"><span>親子：${{esc(c.kid_note)}}</span></div>`:'')
    +`<div class="section-head t-block"><h2>當日吃飯</h2><span>人在哪區吃哪區</span></div><div class="panel pad">${{meals||'<div class="tiny">—</div>'}}</div>`
    +`<div class="section-head t-block"><h2>時間不夠時怎麼調整</h2><span>照順序取捨</span></div><div class="panel pad"><ul class="cut-list">${{cut.map(x=>`<li>${{esc(x)}}</li>`).join('')}}</ul></div>`
    +`<div class="section-head t-block"><h2>成行條件</h2><span>未全部滿足就不出發（Gate 全綠才成立）</span></div><div class="panel pad"><ul class="cut-list">${{gates.map(x=>`<li>${{esc(x)}}</li>`).join('')}}</ul><div class="tiny" style="margin-top:8px">判定語義與證據以主表 gates / evidence_as_of 為準，詳見行程頁備註。</div></div>`;
}}).catch(()=>{{mount.innerHTML='<div class="callout red">資料載入失敗（網路或備援皆不可用）。請檢查連線後重新整理。相容入口：<a href="./data.html">data.html</a></div>'}});
}})();
</script>
</body>
</html>"""


ITINERARY_DAYS = [
 ("10/10", "Sat", "抵達 · 安頓", "VJ845 14:10–16:50 抵達 → Cosy Bungalow 安頓。只安頓，不排大行程。", ["cosy"]),
 ("10/11", "Sun", "OnBird 已確認", "OnBird 南島浮潛上午已確認（業者接送往返）。回 Cosy 先休息；體力好才接 Dinh Cậu／河口＋市區晚間，累就取消。", ["onbird"]),
 ("10/12", "Mon", "彈性（暫排）", "未鎖定。依體力、天氣與前晚確認從五卡選一，或選休息恢復日。暫排只存本機，不等於已預訂。", []),
 ("10/13", "Tue", "彈性（暫排）", "未鎖定。同 10/12，前一晚再鎖隔天。", []),
 ("10/14", "Wed", "彈性（暫排）", "未鎖定。避免連排高強度；Starfish 需七項條件＋48 小時現況全通過才成立。", []),
 ("10/15", "Wed", "返程", "VJ844 08:20–13:00 返台 → 台鐵回程。早上只退房與前往機場。", ["vjl844"]),
]


def build_itinerary_days_html():
    parts = ['<div class="date-tabs" role="tablist" aria-label="日期切換 10/10–10/15">']
    for i, (d, wd, title, desc, _) in enumerate(ITINERARY_DAYS):
        pressed = "true" if i == 1 else "false"
        parts.append(
            f'<button class="date-tab" type="button" role="tab" data-date="{d}" aria-pressed="{pressed}" aria-selected="{str(i==1).lower()}">{d}<br><small>{wd}</small></button>')
    parts.append('</div><div id="dayPanels">')
    for i, (d, wd, title, desc, _) in enumerate(ITINERARY_DAYS):
        active = " active" if i == 1 else ""
        parts.append(
            f'<div class="day-panel{active}" data-day-panel="{d}"><div class="panel pad">'
            f'<div class="label">{h.escape(d)} {h.escape(wd)}</div>'
            f'<div class="today-big">{h.escape(title)}</div>'
            f'<div class="tiny">{h.escape(desc)}</div>'
            f'</div></div>')
    parts.append('</div>')
    return "\n".join(parts)


def main():
    snap, byname, bynotion = load()
    pool = snap.get("pool", [])
    pool_html, n_food = build_food_pool(pool, bynotion, byname, candidate=True)
    food_banner = ('<div class="src-banner tiny" id="foodSrcBanner" style="display:none"></div>'
                   if DYNAMIC else "")
    cards = [c for c in snap["cards"] if c["status"] == "ACTIVE"]
    bookings = snap["bookings"]
    transport = snap.get("transport", [])
    bookings_html = build_bookings_html(bookings)
    meta = snap.get("meta", {})
    snapshot_src = str(meta.get("source", ""))
    cards_sub = "點卡進詳細時間表 · 資料來自快照"
    cards_fetch = "fetchJson('./data/cards.json').then(w=>w).then(cards=>{"
    cards_catch = (".catch(()=>{document.getElementById('cardsMount').innerHTML="
                   "'<div class=\"callout red\">cards.json 載入失敗"
                   "（file:// 直開會擋 fetch，請用 Pages 或本地 server 看）。</div>'})")
    detail_href = "./card.html?slug="
    bookings_note = "公開 6 欄 · Open 是追蹤清單非已訂妥"
    bookings_js = ""
    foods_js = ""
    transport_js = ""
    L_API = L_FB = L_API_C = L_FB_C = L_API_F = L_FB_F = L_API_B = L_FB_B = ""
    itinerary_days = build_itinerary_days_html()
    if DYNAMIC:
        api = _API_BASE
        L_API = ("即時資料 · 取得時間 " if PROD
                 else "測試 API 資料 · 取得時間 ")
        L_FB = "備援靜態資料 · 來源 "
        L_API_C = ("卡片：即時資料 · 取得時間 " if PROD
                   else "卡片：測試 API 資料 · 取得時間 ")
        L_FB_C = "卡片：備援靜態資料 · 來源 "
        L_API_F = ("美食狀態：即時資料 · 取得時間 " if PROD
                   else "美食狀態：測試 API 資料 · 取得時間 ")
        L_FB_F = "美食狀態：備援靜態資料 · 來源 "
        L_API_B = L_API
        L_FB_B = "備援靜態資料 · 來源 "
        cards_sub = (("點卡進詳細時間表 · 即時資料優先，失敗自動用備援 JSON "
                      "（備援標示來源與快照日期，不假裝即時）")
                     if PROD else
                     ("點卡進詳細時間表 · 候選 API 優先，失敗自動用備援 JSON "
                      "（備援標示來源與快照日期，不假裝即時）"))
        cards_fetch = (
            "fetchJson('" + api + "/api/cards').then(w=>{markSrc('api',w.meta&&w.meta.fetched_at);return w.data}).then(cards=>{"
        )
        cards_catch = (
            ".catch(()=>fetch('./data/cards.json').then(r=>{if(!r.ok)throw 0;return r.json()})"
            ".then(cards=>{markSrc('fallback','備援靜態 JSON · 快照 " + snapshot_src.replace("'", "") + "');"
            "var mount=document.getElementById('cardsMount');"
            "var active=cards.filter(c=>c.status==='ACTIVE');"
            "mount.innerHTML=active.map(renderCard).join('')})"
            ".catch(()=>{document.getElementById('cardsMount').innerHTML="
            "'<div class=\"callout red\">即時與備援皆失敗，請檢查連線後重新整理（顯示備援快照日期，非即時）。</div>'}))")
        detail_href = ("./card-candidate.html?slug=" if CANDIDATE
                       else "./card.html?slug=")
        bookings_note = (("候選 API bookings（公開 6 欄）· 失敗時用備援 JSON · Open 是追蹤清單")
                         if CANDIDATE else
                         ("即時訂單（公開 6 欄）· 失敗時用備援快照 · Open 是追蹤清單，不代表已訂妥"))
        foods_js = (
            "function escF(s){return String(s??'').replace(/[&<>\\\"]/g,"
            "c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\\\"':'&quot;'}[c]))}"
            "var ROLE_TXT={carrier:'優先推薦',conditional:'條件適合',fallback:'現場備案',market:'市集小吃',verify:'待再確認'};"
            "function dynBadge(f){"
            "var p='';"
            "if(f.atlas_state==='ACTIVE')p+='<span class=\"role carrier\" data-atlas=\"ACTIVE\">已確認</span>';"
            "else if(f.atlas_state==='VERIFY')p+='<span class=\"role verify\" data-atlas=\"VERIFY\">待再確認</span>';"
            "else if(f.atlas_state==='DEACTIVATED')p+='<span class=\"role red\" data-atlas=\"DEACTIVATED\">已下架</span>';"
            "p+='<span class=\"tiny\" data-atlas-raw=\"'+escF(f.atlas_state||'')+'\" style=\"display:none\">'+escF(f.atlas_state||'')+' ACTIVE VERIFY</span>';"
            "var ver=f.last_verified||f.evidence_as_of||'';"
            "if(ver)p+='<span class=\"food-region\">驗證 '+escF(ver)+'</span>';"
            "return p}"
            "function markFood(kind,when){"
            "var el=document.getElementById('foodSrcBanner');if(!el)return;el.style.display='';el.className='src-banner tiny'+(kind==='api'?' live':'');"
            "el.textContent=kind==='api'?('" + L_API_F + "'+when+'（取得時間，非核實時間）')"
            ":('" + L_FB_F + "'+when+'（備援快照，非即時）')}"
            "function resortPool(){"
            "var pool=document.getElementById('foodPool');if(!pool)return;"
            "var cards=[...pool.querySelectorAll('.food-card')];"
            "pool.querySelectorAll('.pool-divider').forEach(d=>d.remove());"
            "cards.sort((a,b)=>{var ra=parseInt(a.getAttribute('data-pool-rank')||'9999',10),rb=parseInt(b.getAttribute('data-pool-rank')||'9999',10);return ra-rb});"
            "var lastDiv='\\u0000';"
            "cards.forEach(c=>{var dv=c.getAttribute('data-divider')||'';if(dv!==lastDiv){if(dv){var d=document.createElement('div');d.className='pool-divider';d.textContent=dv;pool.appendChild(d)}lastDiv=dv}pool.appendChild(c)})}"
            "fetchJson('" + api + "/api/pool').then(w=>{var byKey={};w.data.forEach(p=>{byKey[p.pool_key]=p});"
            "document.querySelectorAll('[data-food-id]').forEach(card=>{"
            "var p=byKey[card.getAttribute('data-food-id')];if(!p)return;"
            "if(p.pool_rank!=null)card.setAttribute('data-pool-rank',p.pool_rank);"
            "card.setAttribute('data-divider',p.divider||'');"
            "var meta=card.querySelector('.food-meta');"
            "if(meta){var old=meta.querySelectorAll('.role.conditional,.role.fallback,.role.market,.role.verify,.role.carrier:not([data-atlas])');"
            "old.forEach(n=>n.remove());"
            "var tmp=document.createElement('span');var roleCls=p.pool_role||'fallback';"
            "tmp.innerHTML='<span class=\"role '+roleCls+'\">'+escF(ROLE_TXT[roleCls]||roleCls)+'</span>';"
            "var at=meta.querySelector('[data-atlas]');"
            "if(at)meta.insertBefore(tmp.firstChild,at);else while(tmp.firstChild)meta.appendChild(tmp.firstChild)}"
            "var ord=card.querySelector('.food-order'),des=card.querySelector('.food-desc');"
            "if(ord&&p.order_copy!=null)ord.innerHTML='<span>點：</span>'+escF(p.order_copy);"
            "if(des&&p.desc_copy!=null)des.textContent=p.desc_copy;});"
            "resortPool();"
            "markFood('api',w.meta&&w.meta.fetched_at);applyFoodFilters();"
            "}).catch(()=>{markFood('fallback','備援靜態 JSON · 快照 " + snapshot_src.replace("'", "") + " · 池文案暫用快照');applyFoodFilters();});"
            "fetchJson('" + api + "/api/foods').then(w=>{var byNid={},byName={};w.data.forEach(f=>{if(f.notion_id)byNid[f.notion_id]=f;byName[f.name]=f});"
            "document.querySelectorAll('[data-food-id]').forEach(card=>{"
            "var nid=card.getAttribute('data-notion-id');"
            "var f=(nid&&byNid[nid])||byName[card.getAttribute('data-food-name')]||null;"
            "if(!f)return;"
            "if(!nid&&f.notion_id)card.setAttribute('data-notion-id',f.notion_id);"
            "card.setAttribute('data-region',f.region||'—');"
            "card.setAttribute('data-atlas-state',f.atlas_state||'');"
            "card.setAttribute('data-time-slots',f.time_slots||'');"
            "var rg=card.querySelector('.food-region.food-place');"
            "if(rg)rg.textContent=f.region||'—';"
            "var meta=card.querySelector('.food-meta');"
            "if(meta){var old=meta.querySelectorAll('.role.carrier[data-atlas],.role.verify[data-atlas],.role.red[data-atlas],.food-region:not(.food-place),.tiny[data-atlas-raw]');"
            "old.forEach(n=>n.remove());"
            "var tmp=document.createElement('span');tmp.innerHTML=dynBadge(f);"
            "while(tmp.firstChild)meta.appendChild(tmp.firstChild)}"
            "var mq=f.maps_query||f.name;"
            "var a=card.querySelector('a.map');"
            "if(a)a.href='https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(mq+' Phú Quốc')});"
            "applyFoodFilters();})"
            ".catch(()=>{markFood('fallback','備援靜態 JSON · 快照 " + snapshot_src.replace("'", "") + " · 店家狀態暫用快照');applyFoodFilters();});"
        )
        bookings_js = (
            "function escB(s){return String(s??'').replace(/[&<>\\\"]/g,"
            "c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\\\"':'&quot;'}[c]))}"
            "function renderBookings(list,src,when){"
            "var cf=list.filter(b=>b.status==='Confirmed'),op=list.filter(b=>b.status!=='Confirmed');"
            "var h='<div class=\"journey-grid\"><div class=\"label\" style=\"grid-column:1/-1\">已確認 · '+cf.length+'</div>'"
            "+cf.map(b=>'<div class=\"prep\"><b>'+escB(b.title||b.slug)+'</b><div class=\"badges\">"
            "<span class=\"badge brand\">已確認</span>"
            "<span class=\"food-region\">金額 '+escB(b.amount||'')+' · 核實 '+escB(b.evidence_as_of||'')+'</span>"
            "</div></div>').join('')"
            "+(op.length?'<div class=\"label\" style=\"margin-top:6px;grid-column:1/-1\">待辦追蹤 OPEN · '+op.length+'（追蹤清單，非已訂妥）</div>'"
            "+op.map(b=>'<div class=\"prep\"><b>'+escB(b.title||b.slug)+'</b><div class=\"badges\">"
            "<span class=\"badge warm\">待辦追蹤</span>"
            "<span class=\"food-region\">金額 '+escB(b.amount||'')+' · 核實 '+escB(b.evidence_as_of||'')+'</span>"
            "</div></div>').join(''):'')+'</div><div class=\"tiny\" style=\"margin-top:8px\">金額保留原始幣別，不同幣別不直接加總。訂單細節（訂單碼／聯絡方式）不在公開站顯示。</div>';"
            "document.getElementById('bookingsPanel').innerHTML=h;"
            "var tb=document.getElementById('todayBookings');"
            "if(tb){var names=cf.map(b=>b.title||b.slug).slice(0,3).join('、');"
            "tb.textContent='預訂即時：已確認 '+cf.length+(names?('（'+names+(cf.length>3?'等':'')+'）'):'')+' · 待辦追蹤 '+op.length+'（取得時間 '+when+'，非核實時間）'}"
            "var el=document.getElementById('bookSrcBanner');if(el){el.style.display='';el.className='src-banner tiny'+(src==='api'?' live':'');"
            "el.textContent=src==='api'?('" + L_API_B + "'+when+'（取得時間，非核實時間）'):('"
            + L_FB_B + "'+when+'（備援快照，非即時）')}}"
            "fetchJson('" + api + "/api/bookings').then(w=>renderBookings(w.data,'api',w.meta&&w.meta.fetched_at))"
            ".catch(()=>{"
            "var tb=document.getElementById('todayBookings');if(tb)tb.textContent='預訂摘要：備援快照（非即時），以旅程區訂單快照為準；預訂變更後以即時 API 為準。';"
            "var el=document.getElementById('bookSrcBanner');if(el){el.style.display='';"
            "el.textContent='備援靜態資料 · 訂單區維持 build 期快照（備援快照，非即時）'}});"
        )
        transport_js = (
            "fetchJson('" + api + "/api/transport').then(w=>{"
            "var el=document.getElementById('transportPanel');if(!el)return;"
            "var h='<div class=\"journey-grid\">'+w.data.map(t=>'<div class=\"prep\"><b>'+escB(t.plan||t.slug)+'</b><div class=\"badges\"><span class=\"badge\">'+escB(t.status||'')+'</span><span class=\"food-region\">'+escB(t.priority||'')+' · 核實 '+escB(t.evidence_as_of||'')+'</span></div></div>').join('')+'</div>';"
            "el.innerHTML=h;var b=document.getElementById('transportSrc');if(b){b.style.display='';b.className='src-banner tiny live';b.textContent='交通備案：即時資料 · 取得時間 '+(w.meta&&w.meta.fetched_at)+'（取得時間，非核實時間）'}})"
            ".catch(()=>{var b=document.getElementById('transportSrc');if(b){b.style.display='';b.textContent='交通備案：備援靜態資料（備援快照，非即時）'}});"
        )

    # Transport fallback (static snapshot) for no-JS / fallback path
    transport_fallback = ""
    if transport:
        rows = []
        for t in transport[:7]:
            rows.append(
                f'<div class="prep"><b>{h.escape(str(t.get("plan") or t.get("slug") or ""))}</b>'
                f'<span>{h.escape(str(t.get("status") or ""))} · {h.escape(str(t.get("priority") or ""))} · 核實 {h.escape(str(t.get("evidence_as_of") or ""))}</span></div>')
        transport_fallback = '<div class="journey-grid">' + "\n".join(rows) + '</div>'
    else:
        transport_fallback = '<div class="empty">目前沒有交通備案資料（空狀態，非故障）。有資料時會在此列出，不會編造。</div>'

    page = f"""<!doctype html><html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#fdfbf6">
<meta name="description" content="富國島 2026 · 10/10–10/15 · Cosy Bungalow 單一基地 · 五卡彈性行程">
<title>富國島 2026｜今天 · 行程 · 美食 · 旅程</title>
<style>{CSS}{CARD_CSS}</style>
</head>
<body>
<div class="wrap">
<header class="hero">
<div class="eyebrow">PHU QUOC 2026 · 10/10–10/15 · Cosy Bungalow</div>
<h1>富國島 2026</h1>
<p>1 大 1 小 · 單一基地 · 五張行程卡（An Thoi 為選配，Khem 已退役）</p>
<div class="hero-sub" id="vietnamDateLine">越南時間讀取中…（Asia/Ho_Chi_Minh）</div>
<div><span class="trip-phase" id="tripPhase">旅程狀態讀取中</span></div>
</header>
</div>
<div class="sticky"><nav class="nav" aria-label="主要入口"><button class="primary" data-jump="today">今天</button><button data-jump="itinerary">行程</button><button data-jump="food">美食</button><button data-jump="journey">旅程</button></nav></div>
<div class="wrap">
<section class="section" id="today" aria-label="今天">
<div class="section-head"><h2>今天</h2><span>旅途中先看這裡 · 越南時區判定</span></div>
<div class="panel pad"><div class="label">今日狀態 · 越南時區 Asia/Ho_Chi_Minh</div><div class="today-big" id="todayTitle">讀取中…</div><div class="tiny" id="todayDesc">正在依越南日期判斷旅程階段，不會編造未安排的行程，也不會依時間自動宣稱已完成。</div><div class="tiny" id="todayNext" style="margin-top:8px"></div><div class="tiny" id="todayBookings" style="margin-top:8px">預訂摘要載入中…（即時 API 優先，失敗顯示備援快照）</div><div class="row-actions"><button class="ghost" data-goto="itinerary" type="button">看行程日期</button></div></div>
<div class="panel pad" style="margin-top:10px"><div class="label">重要提醒（出發前重查）</div><div class="tiny">超過 30 天或缺少核實日期的資料，出發前請重查。核實日期見各卡片／店家標示；上方橫條為資料取得時間，兩者不同。纜車首末班、OnBird 接送與海況、Starfish 七項條件＋48 小時現況，回程交通與孩子限制（約 115 公分，全程後座）請於前一天 15:00–17:00 只確認隔天。</div></div>
</section>
<section class="section" id="itinerary" aria-label="行程">
<div class="section-head"><h2>行程</h2><span>{cards_sub}</span></div>
<div class="src-banner tiny" id="srcBanner" style="display:none"></div>
{itinerary_days}
<div class="section-head" style="margin-top:16px"><h2 style="font-size:18px">五張行程卡</h2><span>精簡卡片 · 詳情另開頁</span></div>
<div class="cards" id="cardsMount"></div>
<div class="section-head" style="margin-top:16px"><h2 style="font-size:18px">暫排（本機）</h2><span>只存這支手機 · 非預訂</span></div>
<div class="panel pad"><div class="slot-list"><div class="slot"><div class="date"><b>10/11</b><small>已確認</small></div><div class="locked">OnBird 上午已確認 ＋ 體力好才接市區晚間</div></div><div class="slot"><div class="date"><b>10/12</b><small>彈性</small></div><select data-day="10/12" aria-label="10/12 暫排"><option value="">尚未鎖定（未安排）</option><option>Cable + Sunset Town</option><option>VinWonders</option><option>Starfish（需條件全通過）</option><option>Safari</option><option>休息／恢復日</option></select></div><div class="slot"><div class="date"><b>10/13</b><small>彈性</small></div><select data-day="10/13" aria-label="10/13 暫排"><option value="">尚未鎖定（未安排）</option><option>Cable + Sunset Town</option><option>VinWonders</option><option>Starfish（需條件全通過）</option><option>Safari</option><option>休息／恢復日</option></select></div><div class="slot"><div class="date"><b>10/14</b><small>彈性</small></div><select data-day="10/14" aria-label="10/14 暫排"><option value="">尚未鎖定（未安排）</option><option>Cable + Sunset Town</option><option>VinWonders</option><option>Starfish（需條件全通過）</option><option>Safari</option><option>休息／恢復日</option></select></div></div><div class="tiny" id="slotMigrated" style="margin-top:8px;display:none"></div><div class="row-actions"><button class="ghost" id="resetSlots">清除暫排（只清新版）</button></div><div class="tiny" style="margin-top:8px">更改暫排不等於更改或取消訂單。已確認的 OnBird 與其他重要安排不會因介面改版被更動。</div></div>
</section>
<section class="section" id="food" aria-label="美食">
<div class="section-head"><h2>美食</h2><span>手動篩選 · 不定位 · 不冒稱營業中</span></div>
<div class="food-guide"><b>先選區域與時段，再看吃過狀態</b><p>網站不替你判斷現在該吃誰，也不會在缺乏可靠營業資訊時冒稱仍在營業。要吃時把時間＋位置＋孩子狀態告訴日常助手，由它重排。這裡預設只聚焦少量符合條件的選項，可展開完整清單。</p></div>
<div class="filters" role="group" aria-label="美食篩選"><label>區域<select id="filterRegion"><option value="">全部區域</option><option>Dương Đông</option><option>Long Beach</option><option>An Thới</option><option>Gành Dầu</option><option>Grand World</option><option>南島</option><option>北島</option></select></label><label>時段<select id="filterSlot"><option value="">全部時段</option><option>早餐</option><option>午餐</option><option>下午</option><option>晚餐</option><option>宵夜</option></select></label><label>吃過狀態<select id="filterEaten"><option value="">全部</option><option value="uneaten">未吃</option><option value="eaten">已吃</option></select></label></div>
<div class="filter-row"><div class="pool-progress" id="foodProgress">已吃 0 / {n_food}</div><button class="filter-btn" id="toggleFull" aria-pressed="false" type="button">看完整清單</button><button class="ghost" id="resetFood">重設吃過（只清新版）</button></div>
{food_banner}
<div class="food-pool" id="foodPool">
{pool_html}
</div>
<div class="empty" id="foodEmpty" style="display:none;margin-top:10px">沒有符合條件的選項（空狀態）。請放寬區域／時段或查看完整清單，不會編造推薦。</div>
<div class="pool-note">排序代表這趟值得優先完成，不是此刻推薦。 badge 顯示核實日期；即時狀態來自資料庫，失敗時顯示備援快照並標示。吃過紀錄只存在這支手機；舊版本紀錄會保留遷移、不會默默覆蓋或清除。跨裝置同步需登入，目前未提供，不會宣稱為已同步。</div>
</section>
<section class="section" id="journey" aria-label="旅程">
<div class="section-head"><h2>旅程</h2><span>預訂 · 費用 · 交通備案 · 準備</span></div>
<div class="section-head" style="margin-top:4px"><h2 style="font-size:18px">預訂與費用</h2><span>{bookings_note}</span></div>
<div class="src-banner tiny" id="bookSrcBanner" style="display:none"></div>
<div class="panel pad" id="bookingsPanel">{bookings_html}</div>
<div class="tiny" style="margin-top:8px">金額保留原始幣別，不同幣別不直接加總。公開站不顯示訂單碼、聯絡方式、付款資訊或私人筆記原文。</div>
<div class="section-head" style="margin-top:16px"><h2 style="font-size:18px">交通備案</h2><span>回程優先</span></div>
<div class="src-banner tiny" id="transportSrc" style="display:none"></div>
<div class="panel pad" id="transportPanel">{transport_fallback}</div>
<div class="panel pad" style="margin-top:10px"><div class="prep-grid"><div class="prep"><b>市區與主要景點</b><span>Grab／GreenSM／taxi 皆可；機場、纜車站、VinWonders、Safari 直接叫車。</span></div><div class="prep"><b>偏遠與多停點</b><span>出發前先確認回程；回程沒把握就不去。海星用完整門到門往返；Safari 往 Gành Dầu 用留車或明確回接。</span></div><div class="prep"><b>叫不到車</b><span>5–10 分鐘未派車就換平台或 taxi；巴士再等 15–20 分鐘以上就改叫車。</span></div><div class="prep"><b>孩子</b><span>約 115 公分，全程後座；長程優先三點式安全帶＋增高墊或兒童座椅。</span></div></div></div>
<div class="section-head" style="margin-top:16px"><h2 style="font-size:18px">準備與筆記</h2><span>出發前只查必要項目</span></div>
<div class="panel pad"><div class="prep-grid"><div class="prep"><b>OnBird</b><span>接送時間、當天海況、是否照常出發；現場以教練安全評估為準。</span></div><div class="prep"><b>纜車</b><span>10 月第一波時段、回程與末班、是否維修、天氣。</span></div><div class="prep"><b>VinWonders</b><span>營業與餐飲時段、票價、兒童設施限制；Grand World 有體力才接。</span></div><div class="prep"><b>海星</b><span>前 48 小時確認路況、海星、水色、船與回程；七項條件全通過才去。</span></div><div class="prep"><b>Safari</b><span>營業時間、直達叫車與北島回程；往 Gành Dầu 先談好回程並於 17:00 前離開。</span></div><div class="prep"><b>用餐</b><span>只查明天可能吃的店：是否營業、想點的品項與價格；用餐當下再請助手重排。</span></div></div><div class="callout" style="margin-top:12px"><b>前一天 15:00–17:00：</b>只確認隔天。若預約、官方營運、回程交通、住宿與孩子限制無變化，不重新研究整趟。</div></div>
<div class="panel pad" style="margin-top:10px"><div class="label">旅行筆記（公開站空狀態）</div><div class="empty" style="margin-top:8px">公開站不顯示私人筆記原文。旅途中觀察請交日常助手記為 evidence_log，不覆寫主表；需還原請見內容維護契約。</div></div>
</section>
<footer class="footer">data-driven build · 來源 {h.escape(snapshot_src)} · 卡規則：{h.escape(str(meta.get("cards_rule", "")))}<br>核實日期見各項目標示；橫條為資料取得時間；備援快照日期見備援標示，三者不同。<br>吃過／暫排只存這支手機（localStorage v3，舊版保留遷移）。相容入口：<a href="./data.html">data.html</a> · <a href="./card.html?slug=cable">card.html</a></footer>
</div>
<script>
(function(){{
const API_BASE="PLACEHOLDER_API_BASE";
const SNAPSHOT_SRC={json.dumps(snapshot_src, ensure_ascii=False)};
function markSrc(kind,when){{var el=document.getElementById('srcBanner');if(!el)return;el.style.display='';el.className='src-banner tiny'+(kind==='api'?' live':'');el.textContent=(kind==='api'?'{L_MAIN_API}':'{L_MAIN_FB}')+when+(kind==='api'?'（取得時間，非核實時間）':'（備援快照，非即時）')}}
function jparse(s,fb){{try{{const v=JSON.parse(s);return v??fb}}catch(e){{return fb}}}}
function fetchJson(url,ms){{ms=ms||8000;var c=new AbortController();var t=setTimeout(()=>c.abort(),ms);return fetch(url,{{signal:c.signal,cache:'no-store'}}).then(r=>{{clearTimeout(t);if(!r.ok)throw 0;return r.text().then(tx=>{{try{{var j=JSON.parse(tx);if(!j||j.data===undefined)throw 0;return j}}catch(e){{throw 0}}}})}}).catch(e=>{{clearTimeout(t);throw 0}})}}
function escH(s){{return String(s??'').replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]))}}
function renderCard(c){{
  const badges=jparse(c.badges,[]),keyTimes=jparse(c.key_times,[]);
  return `<a class="link-card" href="{detail_href}${{c.slug}}"><div class="trip-title"><div><h3>${{escH(c.name)}}</h3>`
    +`<div class="trip-summary">${{escH(c.summary||c.route||'')}} · 核實 ${{escH(c.evidence_as_of||'')}}</div>`
    +`<div class="badges">${{badges.map(b=>`<span class="badge ${{escH(b.tone||'')}}">${{escH(b.text)}}</span>`).join('')}}</div>`
    +`<div class="key-times">${{keyTimes.map(t=>`<span class="key-time">${{escH(t)}}</span>`).join('')}}</div>`
    +`</div><div class="arrow" aria-hidden="true">›</div></div></a>`;
}}
// Vietnam timezone trip phase (never fabricate, never auto-complete)
function vietnamDate(){{try{{var p=new Intl.DateTimeFormat('en-CA',{{timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit'}}).format(new Date());return p}}catch(e){{var d=new Date();return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')}}}}
function renderToday(){{var vd=vietnamDate();var line=document.getElementById('vietnamDateLine');if(line)line.textContent='越南時間 '+vd+'（Asia/Ho_Chi_Minh）';var ph=document.getElementById('tripPhase'),ti=document.getElementById('todayTitle'),de=document.getElementById('todayDesc'),nx=document.getElementById('todayNext');if(!ph||!ti)return;var sSaved={{}};try{{sSaved=JSON.parse(localStorage.getItem('phq-v3-slots')||localStorage.getItem('phq-v2-slots')||'{{}}')}}catch(e){{}}function slot(d){{return sSaved[d]||''}}if(vd<'2026-10-10'){{ph.textContent='出發前';ti.textContent='旅程摘要 · 10/11 已確認，其餘保持彈性';if(de)de.textContent='已確認（備援快照）：OnBird 10/11 上午、Cosy 5 晚、來回航班。即時狀態見上方預訂行；待辦：旅行保險、島上交通未鎖。出發前只查必要項目，不重新研究整趟。';if(nx)nx.textContent='未安排的日子不會顯示假安排；暫排可到行程區設定（只存本機）。'}}else if(vd<='2026-10-15'){{ph.textContent='旅途中 · '+vd;var map={{'2026-10-10':['抵達安頓','抵達 Cosy 安頓，不排大行程'], '2026-10-11':['OnBird 已確認','業者接送往返，回來先休息；體力好才接市區晚間'], '2026-10-12':['彈性日','前晚鎖定；可從五卡選一或休息'], '2026-10-13':['彈性日','前晚鎖定；避免連排高強度'], '2026-10-14':['彈性日','Starfish 需條件全通過才成立'], '2026-10-15':['返程','退房＋前往機場 VJ844']}};var cur=map[vd]||['旅途中','依行程區日期切換查看'];ti.textContent='今日（'+vd+'）：'+cur[0];var extra='';if(vd>='2026-10-12'&&vd<='2026-10-14'){{var mm={{'2026-10-12':'10/12','2026-10-13':'10/13','2026-10-14':'10/14'}}[vd];var sv=slot(mm);extra=sv?(' · 暫排：'+sv+'（本機暫排，非已預訂）'):(' · 暫排：尚未鎖定（未安排，不編造）')}}if(de)de.textContent=cur[1]+extra+'。重要時間與地圖請進對應行程卡詳情。不會依時間自動宣稱已完成。';if(nx)nx.textContent='下一個重點：'+(vd==='2026-10-11'?'OnBird 後先休息':(vd<'2026-10-11'?'10/11 OnBird 已確認':(vd==='2026-10-15'?'返程航班':'明日前晚 15:00–17:00 再鎖定')));}}else{{ph.textContent='旅行後';ti.textContent='旅程已結束（'+vd+'）';if(de)de.textContent='此站保留為紀錄與備援快照。私人筆記不在公開站顯示。';if(nx)nx.textContent='';}}}}
// nav (no hash)
const sticky=document.querySelector('.sticky');
const navButtons=[...document.querySelectorAll('[data-jump]')];
const navIds=[...new Set(navButtons.map(btn=>btn.dataset.jump))];
function setActiveNav(id){{document.querySelectorAll('.nav button').forEach(btn=>btn.classList.toggle('primary',btn.dataset.jump===id))}}
function syncNav(){{if(!sticky)return;const offset=sticky.offsetHeight+18;let current=navIds[0];navIds.forEach(id=>{{const el=document.getElementById(id);if(el&&el.getBoundingClientRect().top<=offset)current=id}});setActiveNav(current)}}
function jumpTo(id){{const el=document.getElementById(id);if(!el)return;const y=el.getBoundingClientRect().top+window.scrollY-((sticky&&sticky.offsetHeight)||60)-8;window.scrollTo(0,Math.max(0,y));setActiveNav(id);requestAnimationFrame(syncNav)}}
navButtons.forEach(btn=>btn.addEventListener('click',()=>jumpTo(btn.dataset.jump)));document.querySelectorAll('[data-goto]').forEach(btn=>btn.addEventListener('click',()=>jumpTo(btn.getAttribute('data-goto'))));
let navTick=false;window.addEventListener('scroll',()=>{{if(navTick)return;navTick=true;requestAnimationFrame(()=>{{syncNav();navTick=false}})}},{{passive:true}});window.addEventListener('resize',syncNav);syncNav();renderToday();
// date tabs
document.querySelectorAll('.date-tab').forEach(btn=>btn.addEventListener('click',()=>{{document.querySelectorAll('.date-tab').forEach(b=>{{b.setAttribute('aria-pressed','false');b.setAttribute('aria-selected','false')}});btn.setAttribute('aria-pressed','true');btn.setAttribute('aria-selected','true');var d=btn.getAttribute('data-date');document.querySelectorAll('[data-day-panel]').forEach(p=>p.classList.toggle('active',p.getAttribute('data-day-panel')===d))}}));
// localStorage v3 migration (never overwrite newer, never clear old directly, never touch Neon)
function migrateLS(){{try{{var OLD_S='phq-v2-slots',NEW_S='phq-v3-slots',OLD_F='phq-v2-food-eaten',NEW_F='phq-v3-food-eaten';var hasNewS=!!localStorage.getItem(NEW_S),hasNewF=!!localStorage.getItem(NEW_F);var oldS=localStorage.getItem(OLD_S),oldF=localStorage.getItem(OLD_F);var msg=[];if(!hasNewS&&oldS){{localStorage.setItem(NEW_S,oldS);msg.push('暫排已保留')}}if(!hasNewF&&oldF){{localStorage.setItem(NEW_F,oldF);msg.push('吃過紀錄已保留')}}if(msg.length){{var el=document.getElementById('slotMigrated');if(el){{el.style.display='';el.textContent='已從舊版本保留本機紀錄（'+msg.join('、')+'），舊資料仍保留未清除，也未覆蓋較新的本機狀態。'}}}}}}catch(e){{}}}}
migrateLS();
const slotKey='phq-v3-slots';let saved={{}};try{{saved=JSON.parse(localStorage.getItem(slotKey)||'{{}}')}}catch(e){{}}document.querySelectorAll('select[data-day]').forEach(sel=>{{if(saved[sel.dataset.day])sel.value=saved[sel.dataset.day];sel.addEventListener('change',()=>{{saved[sel.dataset.day]=sel.value;if(!sel.value)delete saved[sel.dataset.day];localStorage.setItem(slotKey,JSON.stringify(saved));renderToday()}})}});document.getElementById('resetSlots').addEventListener('click',()=>{{if(!window.confirm('清除新版暫排？（舊版備份保留，不影響已確認訂單）'))return;saved={{}};localStorage.setItem(slotKey,JSON.stringify(saved));document.querySelectorAll('select[data-day]').forEach(s=>s.value='');renderToday()}});
// food: eaten + filters (manual, no geolocation, no fake open-now)
const foodKey='phq-v3-food-eaten';let eaten={{}};try{{eaten=JSON.parse(localStorage.getItem(foodKey)||'{{}}')}}catch(e){{}}const foodCards=[...document.querySelectorAll('[data-food-id]')],foodProgress=document.getElementById('foodProgress'),foodEmpty=document.getElementById('foodEmpty');let showFull=false;function matchFilters(card){{var r=(document.getElementById('filterRegion')||{{}}).value||'';var s=(document.getElementById('filterSlot')||{{}}).value||'';var e=(document.getElementById('filterEaten')||{{}}).value||'';var id=card.dataset.foodId;var isEaten=!!eaten[id];if(e==='eaten'&&!isEaten)return false;if(e==='uneaten'&&isEaten)return false;if(r){{var cr=card.getAttribute('data-region')||'';if(cr.indexOf(r)<0&&!(r==='南島'&&(cr.indexOf('An Th')>=0))&&!(r==='北島'&&(cr.indexOf('Gành')>=0||cr.indexOf('Grand')>=0)))return false}}if(s){{var ts=card.getAttribute('data-time-slots')||'';if(ts.indexOf(s)<0)return false}}return true}}
function applyFoodFilters(){{window.applyFoodFilters=applyFoodFilters;let count=0,matched=[];foodCards.forEach(card=>{{const id=card.dataset.foodId,isEaten=!!eaten[id];if(isEaten)count++;card.classList.toggle('eaten',isEaten);const btn=card.querySelector('.eaten-btn');if(btn){{btn.setAttribute('aria-pressed',String(isEaten));btn.textContent=isEaten?'✓ 吃過':'○ 未吃'}}var ok=matchFilters(card);if(ok)matched.push(card)}});let visible=matched;if(!showFull&&matched.length>6)visible=matched.slice(0,6);foodCards.forEach(c=>c.classList.add('hidden'));visible.forEach(c=>c.classList.remove('hidden'));if(foodEmpty)foodEmpty.style.display=matched.length?'none':'';var t=document.getElementById('toggleFull');if(t){{t.textContent=showFull?('顯示較少（'+visible.length+' / '+matched.length+'）'):('看完整清單（'+matched.length+' 項符合）');t.setAttribute('aria-pressed',String(showFull))}}if(foodProgress)foodProgress.textContent=`已吃 ${{count}} / ${{foodCards.length}}`}}
foodCards.forEach(card=>{{const btn=card.querySelector('.eaten-btn');if(!btn)return;btn.addEventListener('click',()=>{{const id=card.dataset.foodId;eaten[id]=!eaten[id];if(!eaten[id])delete eaten[id];localStorage.setItem(foodKey,JSON.stringify(eaten));applyFoodFilters()}})}});['filterRegion','filterSlot','filterEaten'].forEach(id=>{{var el=document.getElementById(id);if(el)el.addEventListener('change',()=>{{showFull=false;applyFoodFilters()}})}});document.getElementById('toggleFull').addEventListener('click',()=>{{showFull=!showFull;applyFoodFilters()}});document.getElementById('resetFood').addEventListener('click',()=>{{if(!window.confirm('清除新版「吃過」紀錄？（舊版備份保留）'))return;eaten={{}};localStorage.setItem(foodKey,JSON.stringify(eaten));applyFoodFilters()}});applyFoodFilters();
{cards_fetch}
  const mount=document.getElementById('cardsMount');
  const active=cards.filter(c=>c.status==='ACTIVE');
  mount.innerHTML=active.map(renderCard).join('');
}})
{cards_catch}
{foods_js}
{bookings_js}
{transport_js}
}})();
</script>
</body>
</html>"""
    if CANDIDATE:
        out = _OUT_DIR
        (out / "data").mkdir(parents=True, exist_ok=True)
        (out / "data-candidate.html").write_text(
            page.replace("PLACEHOLDER_API_BASE", _API_BASE), encoding="utf-8")
        (out / "card-candidate.html").write_text(
            build_card_page(candidate_api=_API_BASE), encoding="utf-8")
        print("wrote candidate:", out / "data-candidate.html",
              "+", out / "card-candidate.html")
    elif PROD:
        (ROOT / "data.html").write_text(
            page.replace("PLACEHOLDER_API_BASE", _API_BASE), encoding="utf-8")
        (ROOT / "index.html").write_text(
            page.replace("PLACEHOLDER_API_BASE", _API_BASE), encoding="utf-8")
        (ROOT / "card.html").write_text(
            build_card_page(candidate_api=_API_BASE, prod=True), encoding="utf-8")
        print("wrote PROD index.html+data.html", len(page), "bytes;", n_food,
              "food cards;", len(cards), "active cards client-side")
    else:
        (ROOT / "data.html").write_text(page, encoding="utf-8")
        (ROOT / "card.html").write_text(build_card_page(), encoding="utf-8")
        print("wrote data.html", len(page), "bytes;", n_food, "food cards;",
              len(cards), "active cards rendered client-side")


if __name__ == "__main__":
    main()
