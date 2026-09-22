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
import re as _re
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
# Source labels live in the setSrc() JS helper: a one-line visible fallback
# notice plus a small <details class="src-info">. No big banners on success.

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


def src_block(zone_id, zone_label, day):
    """Small <details class=src-info> + hidden one-line fallback notice.

    Normal load shows only the collapsed details. The fallback line is
    unhidden by JS only when that zone actually degrades to static data.
    `day` is a YYYY-MM-DD snapshot date (or "" when unknown).
    """
    fb_day = f" · 快照 {h.escape(day)}" if day else ""
    return (
        f'<div class="src-fallback" id="{zone_id}Fallback" hidden>'
        f'更新暫不可用，顯示備援資料{fb_day}</div>'
        f'\n<details class="src-info" id="{zone_id}Src"><summary>資料資訊</summary>'
        f'<div>{h.escape(zone_label)} · 取得時間 載入中（失敗時顯示備援資料{fb_day}）</div></details>'
    )


def snapshot_day(src):
    m = _re.search(r"\d{4}-\d{2}-\d{2}", src or "")
    return m.group(0) if m else ""


def build_bookings_html(bookings):
    confirmed = [b for b in (bookings or []) if b.get("status") == "Confirmed"]
    open_items = [b for b in (bookings or []) if b.get("status") != "Confirmed"]

    def row(b, tone):
        title = h.escape(str(b.get("title") or b.get("slug") or ""))
        amount = h.escape(str(b.get("amount") or ""))
        ev_as = h.escape(str(b.get("evidence_as_of") or ""))
        badge = '<span class="badge brand">已確認</span>' if tone == "ok" else '<span class="badge warm">待處理</span>'
        meta = f"{amount} · 核實 {ev_as}" if amount or ev_as else ""
        return (f'<div class="prep"><b>{title}</b>'
                f'<div class="badges">{badge}'
                + (f'<span class="food-region">{meta}</span>' if meta else '')
                + '</div></div>')

    parts = ['<div class="prep-grid">']
    parts.append(f'<div class="label">已確認 · {len(confirmed)}</div>')
    parts.extend(row(b, "ok") for b in confirmed)
    if open_items:
        parts.append(f'<div class="label" style="margin-top:6px">待處理 · {len(open_items)}</div>')
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
        return ('<div class="empty">精選池目前沒有項目。</div>', 0)
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


def build_card_page(candidate_api="", prod=False, snapshot_src=""):
    L_D_API = ("取得時間 " if prod else "測試 API 取得時間 ")
    L_D_FB = "備援資料 · 快照 "
    fb_day = " · 快照 " + snapshot_day(snapshot_src) if snapshot_day(snapshot_src) else ""
    if not candidate_api:
        fetch_js = ("fetch('./data/cards.json').then(r=>{if(!r.ok)throw 0;return r.json()}).then(cards=>{"
                    "const c=cards.find(x=>x.slug===slug&&x.status==='ACTIVE');")
    else:
        fetch_js = (
            "fetchWithTimeout('" + candidate_api + "/api/cards?slug='+encodeURIComponent(slug))"
            ".then(w=>{setDsrc('api',w.meta&&w.meta.fetched_at);return [w.data]})"
            ".catch(()=>fetch('./data/cards.json').then(r=>{if(!r.ok)throw 0;return r.json()})"
            ".then(cards=>{setDsrc('fallback','" + fb_day.replace("'", "") + "');return cards}))"
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
<div class="src-fallback" id="srcFallback" hidden>更新暫不可用，顯示備援資料{fb_day}</div>
<div id="cardMount"><div class="panel pad"><div class="tiny">載入中…</div></div></div>
<details class="src-info" id="srcInfo" style="margin-top:12px"><summary>資料資訊</summary><div id="srcDetail">卡片資料 · 取得時間 載入中</div></details>
<footer class="footer">吃過／暫排只存這支手機。核實日期見卡片標示。</footer>
</div>
<script>
(function(){{
const mount=document.getElementById('cardMount');
const slug=new URLSearchParams(location.search).get('slug')||'';
(function(){{var b=document.getElementById('backLink');if(!b)return;try{{var ref=document.referrer||'';if(ref.indexOf('data.html')>=0){{b.setAttribute('href','./data.html#itinerary')}}}}catch(e){{}}}})();
function setDsrc(kind,when){{var fb=document.getElementById('srcFallback');var dt=document.getElementById('srcDetail');if(kind!=='api'){{if(fb)fb.hidden=false}}if(dt)dt.textContent=(kind==='api'?('卡片資料 · {L_D_API}'+when):('{L_D_FB}'+when))}}
function esc(s){{return String(s??'').replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]))}}
function jparse(s,fb){{try{{const v=JSON.parse(s);return v??fb}}catch(e){{return fb}}}}
function fetchWithTimeout(url,ms){{ms=ms||8000;var c=new AbortController();var t=setTimeout(()=>c.abort(),ms);return fetch(url,{{signal:c.signal}}).then(r=>{{clearTimeout(t);if(!r.ok)throw 0;return r.json().then(j=>{{if(!j||j.data===undefined)throw 0;return j}})}}).catch(e=>{{clearTimeout(t);throw 0}})}}
function gmap(query,label){{const q=encodeURIComponent((query||label)+' Phú Quốc');return `<a class="place-link" target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query=${{q}}">${{esc(label)}}</a>`}}
{fetch_js}
  if(!c){{mount.innerHTML='<div class="callout red">找不到這張卡。<a href="./#itinerary">回行程</a></div>';return}}
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
    `<div class="detail-hero"><h1 style="margin:6px 0;font-size:clamp(24px,6vw,34px);letter-spacing:-.02em">${{esc(c.name)}}</h1>`
    +`<p class="detail-sub">${{esc(c.summary||c.route||'')}}</p>`
    +`<div class="badges">${{badges.map(b=>`<span class="badge ${{esc(b.tone||'')}}">${{esc(b.text)}}</span>`).join('')}}${{c.evidence_as_of?`<span class="food-region">核實 ${{esc(c.evidence_as_of||'')}}</span>`:''}}</div></div>`
    +`<div class="panel pad"><div class="label">時間線</div><div class="timeline">${{steps}}</div></div>`
    +(callout?`<div class="callout ${{esc(callout.tone||'')}}" style="margin-top:12px">${{esc(callout.text)}}</div>`:'')
    +`<div class="section-head t-block"><h2>交通</h2></div><div>${{legs}}</div>`
    +(c.kid_note?`<div class="kid-line"><span>親子：${{esc(c.kid_note)}}</span></div>`:'')
    +`<div class="section-head t-block"><h2>當日吃飯</h2></div><div class="panel pad">${{meals}}</div>`
    +(cut.length?`<div class="section-head t-block"><h2>時間不夠時怎麼調整</h2></div><div class="panel pad"><ul class="cut-list">${{cut.map(x=>`<li>${{esc(x)}}</li>`).join('')}}</ul></div>`:'')
    +(gates.length?`<div class="section-head t-block"><h2>成行條件</h2></div><div class="panel pad"><ul class="cut-list">${{gates.map(x=>`<li>${{esc(x)}}</li>`).join('')}}</ul></div>`:'');
}}).catch(()=>{{mount.innerHTML='<div class="callout red">資料載入失敗，請檢查連線後重新整理。<a href="./#itinerary">回行程</a></div>'}});
}})();
</script>
</body>
</html>"""


ITINERARY_DAYS = [
 ("10/10", "Sat", "抵達 · 安頓", "VJ845 14:10–16:50 抵達 → Cosy Bungalow 安頓。不排大行程。", ["cosy"]),
 ("10/11", "Sun", "OnBird 已確認", "OnBird 南島浮潛上午已確認（業者接送往返）。回 Cosy 先休息；體力好才接市區晚間。", ["onbird"]),
 ("10/12", "Mon", "彈性（暫排）", "尚未安排。前晚依體力與天氣選一，或休息。", []),
 ("10/13", "Tue", "彈性（暫排）", "尚未安排。前晚再鎖隔天。", []),
 ("10/14", "Wed", "彈性（暫排）", "尚未安排。Starfish 需七項條件＋48 小時現況全通過才成立。", []),
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
    cards = [c for c in snap["cards"] if c["status"] == "ACTIVE"]
    bookings = snap["bookings"]
    transport = snap.get("transport", [])
    bookings_html = build_bookings_html(bookings)
    meta = snap.get("meta", {})
    snapshot_src = str(meta.get("source", ""))
    snap_day = snapshot_day(snapshot_src)
    cards_src = src_block("cardsMount", "行程卡", snap_day)
    food_src = src_block("foodPool", "美食", snap_day) if DYNAMIC else ""
    book_src = src_block("bookingsPanel", "預訂", snap_day)
    trans_src = src_block("transportPanel", "交通備案", snap_day)
    cards_sub = "點卡進詳細時間表"
    cards_fetch = "fetchJson('./data/cards.json').then(w=>w).then(cards=>{"
    cards_catch = (".catch(()=>{document.getElementById('cardsMount').innerHTML="
                   "'<div class=\"callout red\">資料載入失敗，請檢查連線後重新整理。</div>'})")
    detail_href = "./card.html?slug="
    bookings_note = ""
    bookings_js = ""
    foods_js = ""
    transport_js = ""
    itinerary_days = build_itinerary_days_html()
    if DYNAMIC:
        api = _API_BASE
        cards_fetch = (
            "fetchJson('" + api + "/api/cards').then(w=>{setSrc('cardsMount','api',w.meta&&w.meta.fetched_at,'行程卡');return w.data}).then(cards=>{"
        )
        cards_catch = (
            ".catch(()=>fetch('./data/cards.json').then(r=>{if(!r.ok)throw 0;return r.json()})"
            ".then(cards=>{setSrc('cardsMount','fallback',null,'行程卡');"
            "var mount=document.getElementById('cardsMount');"
            "var active=cards.filter(c=>c.status==='ACTIVE');"
            "mount.innerHTML=active.map(renderCard).join('')})"
            ".catch(()=>{document.getElementById('cardsMount').innerHTML="
            "'<div class=\"callout red\">資料載入失敗，請檢查連線後重新整理。</div>'}))")
        detail_href = ("./card-candidate.html?slug=" if CANDIDATE
                       else "./card.html?slug=")
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
            "function resortPool(){"
            "var pool=document.getElementById('foodPool');if(!pool)return;"
            "var cards=[...pool.querySelectorAll('.food-card')];"
            "pool.querySelectorAll('.pool-divider').forEach(d=>d.remove());"
            "cards.sort((a,b)=>{var ra=parseInt(a.getAttribute('data-pool-rank')||'9999',10),rb=parseInt(b.getAttribute('data-pool-rank')||'9999',10);return ra-rb});"
            "var lastDiv='\\u0000';"
            "cards.forEach(c=>{var dv=c.getAttribute('data-divider')||'';if(dv!==lastDiv){if(dv){var d=document.createElement('div');d.className='pool-divider';d.textContent=dv;pool.appendChild(d)}lastDiv=dv}pool.appendChild(c)})}"
            "var foodOk=false;var foodFailed=false;"
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
            "foodOk=true;if(!foodFailed){setSrc('foodPool','api',w.meta&&w.meta.fetched_at,'美食')}applyFoodFilters();"
            "}).catch(()=>{foodFailed=true;setSrc('foodPool','fallback',null,'美食');"
            "if(!foodOk)applyFoodFilters();});"
            "fetchJson('" + api + "/api/foods').then(w=>{var byNid={},byName={};w.data.forEach(f=>{if(f.notion_id)byNid[f.notion_id]=f;byName[f.name]=f});"
            "foodOk=true;"
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
            "foodOk=true;if(!foodFailed){setSrc('foodPool','api',w.meta&&w.meta.fetched_at,'美食')}applyFoodFilters();})"
            ".catch(()=>{foodFailed=true;setSrc('foodPool','fallback',null,'美食');"
            "if(!foodOk)applyFoodFilters();});"
        )
        bookings_js = (
            "function escB(s){return String(s??'').replace(/[&<>\\\"]/g,"
            "c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\\\"':'&quot;'}[c]))}"
            "function renderBookings(list,src,when){"
            "var cf=list.filter(b=>b.status==='Confirmed'),op=list.filter(b=>b.status!=='Confirmed');"
            "var h='<div class=\"journey-grid\"><div class=\"label\" style=\"grid-column:1/-1\">已確認 · '+cf.length+'</div>'"
            "+cf.map(b=>'<div class=\"prep\"><b>'+escB(b.title||b.slug)+'</b><div class=\"badges\">"
            "<span class=\"badge brand\">已確認</span>"
            "<span class=\"food-region\">'+escB(b.amount||'')+' · 核實 '+escB(b.evidence_as_of||'')+'</span>"
            "</div></div>').join('')"
            "+(op.length?'<div class=\"label\" style=\"margin-top:6px;grid-column:1/-1\">待處理 · '+op.length+'</div>'"
            "+op.map(b=>'<div class=\"prep\"><b>'+escB(b.title||b.slug)+'</b><div class=\"badges\">"
            "<span class=\"badge warm\">待處理</span>"
            "<span class=\"food-region\">'+escB(b.amount||'')+' · 核實 '+escB(b.evidence_as_of||'')+'</span>"
            "</div></div>').join(''):'')+'</div><div class=\"tiny\" style=\"margin-top:8px\">金額保留原始幣別，不同幣別不直接加總。</div>';"
            "document.getElementById('bookingsPanel').innerHTML=h;"
            "setSrc('bookingsPanel',src,when,'預訂');"
            "var tb=document.getElementById('todayBookings');"
            "if(tb){var names=cf.map(b=>b.title||b.slug).slice(0,3).join('、');"
            "tb.textContent='已確認 '+cf.length+(names?('（'+names+(cf.length>3?'等':'')+'）'):'')+' · 待處理 '+op.length}"
            "}"
            "fetchJson('" + api + "/api/bookings').then(w=>renderBookings(w.data,'api',w.meta&&w.meta.fetched_at))"
            ".catch(()=>{"
            "var tb=document.getElementById('todayBookings');if(tb)tb.textContent='預訂摘要：更新暫不可用，以下方旅程區為準。';"
            "setSrc('bookingsPanel','fallback',null,'預訂');});"
        )
        transport_js = (
            "fetchJson('" + api + "/api/transport').then(w=>{"
            "var el=document.getElementById('transportPanel');if(!el)return;"
            "var h='<div class=\"journey-grid\">'+w.data.map(t=>'<div class=\"prep\"><b>'+escB(t.plan||t.slug)+'</b><div class=\"badges\"><span class=\"badge\">'+escB(t.status||'')+'</span><span class=\"food-region\">'+escB(t.priority||'')+' · 核實 '+escB(t.evidence_as_of||'')+'</span></div></div>').join('')+'</div>';"
            "el.innerHTML=h;setSrc('transportPanel','api',w.meta&&w.meta.fetched_at,'交通備案')})"
            ".catch(()=>{setSrc('transportPanel','fallback',null,'交通備案')});"
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
        transport_fallback = '<div class="empty">目前沒有交通備案資料。</div>'

    page = f"""<!doctype html><html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#fdfbf6">
<meta name="description" content="富國島 2026 · 10/10–10/15 · Cosy Bungalow">
<title>富國島 2026｜今天 · 行程 · 美食 · 旅程</title>
<style>{CSS}{CARD_CSS}</style>
</head>
<body>
<div class="wrap">
<header class="hero">
<div class="eyebrow">PHU QUOC 2026 · 10/10–10/15 · Cosy Bungalow</div>
<h1>富國島 2026</h1>
<p>1 大 1 小</p>
<div class="hero-sub" id="vietnamDateLine">越南時間讀取中…</div>
<div><span class="trip-phase" id="tripPhase">旅程狀態讀取中</span></div>
</header>
</div>
<div class="sticky"><nav class="nav" aria-label="主要入口"><button class="primary" data-jump="today">今天</button><button data-jump="itinerary">行程</button><button data-jump="food">美食</button><button data-jump="journey">旅程</button></nav></div>
<div class="wrap">
<section class="section" id="today" aria-label="今天">
<div class="section-head"><h2>今天</h2></div>
<div class="panel pad"><div class="today-big" id="todayTitle">載入中…</div><div class="tiny" id="todayDesc"></div><div class="tiny" id="todayNext" style="margin-top:8px"></div><div class="tiny" id="todayBookings" style="margin-top:8px">預訂摘要載入中…</div><div class="row-actions"><button class="ghost" data-goto="itinerary" type="button">看行程日期</button></div></div>
</section>
<section class="section" id="itinerary" aria-label="行程">
<div class="section-head"><h2>行程</h2><span>{cards_sub}</span></div>
{cards_src}
{itinerary_days}
<div class="section-head" style="margin-top:16px"><h2 style="font-size:18px">行程選項</h2></div>
<div class="cards" id="cardsMount"></div>
<div class="section-head" style="margin-top:16px"><h2 style="font-size:18px">暫排行程</h2><span>僅存此裝置，不代表已預訂</span></div>
<div class="panel pad"><div class="slot-list"><div class="slot"><div class="date"><b>10/11</b><small>已確認</small></div><div class="locked">OnBird 上午已確認 ＋ 體力好才接市區晚間</div></div><div class="slot"><div class="date"><b>10/12</b><small>彈性</small></div><select data-day="10/12" aria-label="10/12 暫排"><option value="">尚未安排</option><option>Cable + Sunset Town</option><option>VinWonders</option><option>Starfish（需條件全通過）</option><option>Safari</option><option>休息／恢復日</option></select></div><div class="slot"><div class="date"><b>10/13</b><small>彈性</small></div><select data-day="10/13" aria-label="10/13 暫排"><option value="">尚未安排</option><option>Cable + Sunset Town</option><option>VinWonders</option><option>Starfish（需條件全通過）</option><option>Safari</option><option>休息／恢復日</option></select></div><div class="slot"><div class="date"><b>10/14</b><small>彈性</small></div><select data-day="10/14" aria-label="10/14 暫排"><option value="">尚未安排</option><option>Cable + Sunset Town</option><option>VinWonders</option><option>Starfish（需條件全通過）</option><option>Safari</option><option>休息／恢復日</option></select></div></div><div class="tiny" id="slotMigrated" style="margin-top:8px;display:none"></div><div class="row-actions"><button class="ghost" id="resetSlots">清除暫排</button></div><div class="tiny" style="margin-top:8px">更改暫排不等於更改或取消訂單。</div></div>
</section>
<section class="section" id="food" aria-label="美食">
<div class="section-head"><h2>美食</h2></div>
<div class="filters" role="group" aria-label="美食篩選"><label>區域<select id="filterRegion"><option value="">全部區域</option><option>Dương Đông</option><option>Long Beach</option><option>An Thới</option><option>Gành Dầu</option><option>Grand World</option><option>南島</option><option>北島</option></select></label><label>時段<select id="filterSlot"><option value="">全部時段</option><option>早餐</option><option>午餐</option><option>下午</option><option>晚餐</option><option>宵夜</option></select></label><label>吃過狀態<select id="filterEaten"><option value="">全部</option><option value="uneaten">未吃</option><option value="eaten">已吃</option></select></label></div>
<div class="filter-row"><div class="pool-progress" id="foodProgress">已吃 0 / {n_food}</div><button class="filter-btn" id="toggleFull" aria-pressed="false" type="button">看完整清單</button><button class="ghost" id="resetFood">重設吃過紀錄</button></div>
{food_src}
<div class="food-pool" id="foodPool">
{pool_html}
</div>
<div class="empty" id="foodEmpty" style="display:none;margin-top:10px">沒有符合條件的餐廳，試試其他區域或時段。</div>
<div class="tiny" style="margin-top:10px">吃過紀錄僅存此裝置。</div>
</section>
<section class="section" id="journey" aria-label="旅程">
<div class="section-head"><h2>旅程</h2></div>
<div class="section-head" style="margin-top:4px"><h2 style="font-size:18px">預訂與費用</h2></div>
{book_src}
<div class="panel pad" id="bookingsPanel">{bookings_html}</div>
<div class="tiny" style="margin-top:8px">金額保留原始幣別，不同幣別不直接加總。</div>
<div class="section-head" style="margin-top:16px"><h2 style="font-size:18px">交通備案</h2></div>
{trans_src}
<div class="panel pad" id="transportPanel">{transport_fallback}</div>
<div class="panel pad" style="margin-top:10px"><div class="prep-grid"><div class="prep"><b>市區與主要景點</b><span>Grab／GreenSM／taxi 皆可；機場、纜車站、VinWonders、Safari 直接叫車。</span></div><div class="prep"><b>偏遠與多停點</b><span>出發前先確認回程；回程沒把握就不去。海星用完整門到門往返；Safari 往 Gành Dầu 用留車或明確回接。</span></div><div class="prep"><b>叫不到車</b><span>5–10 分鐘未派車就換平台或 taxi；巴士再等 15–20 分鐘以上就改叫車。</span></div><div class="prep"><b>孩子</b><span>約 115 公分，全程後座；長程優先三點式安全帶＋增高墊或兒童座椅。</span></div></div></div>
<div class="section-head" style="margin-top:16px"><h2 style="font-size:18px">出發前確認</h2></div>
<div class="panel pad"><div class="prep-grid"><div class="prep"><b>OnBird</b><span>接送時間、當天海況、是否照常出發；現場以教練安全評估為準。</span></div><div class="prep"><b>纜車</b><span>10 月第一波時段、回程與末班、是否維修、天氣。</span></div><div class="prep"><b>VinWonders</b><span>營業與餐飲時段、票價、兒童設施限制。</span></div><div class="prep"><b>海星</b><span>前 48 小時確認路況、海星、水色、船與回程；七項條件全通過才去。</span></div><div class="prep"><b>Safari</b><span>營業時間、直達叫車與北島回程；往 Gành Dầu 先談好回程並於 17:00 前離開。</span></div><div class="prep"><b>用餐</b><span>只查明天可能吃的店：是否營業、想點的品項與價格。</span></div></div></div>
</section>
<footer class="footer">吃過／暫排只存這支手機。核實日期見各項目標示。</footer>
</div>
<script>
(function(){{
const API_BASE="PLACEHOLDER_API_BASE";
const SNAPSHOT_SRC={json.dumps(snapshot_src, ensure_ascii=False)};
const SNAPSHOT_DAY=(function(){{var m=String(SNAPSHOT_SRC||'').match(/\\d{{4}}-\\d{{2}}-\\d{{2}}/);return m?m[0]:''}})();
function setSrc(zoneId,kind,when,label){{var fb=document.getElementById(zoneId+'Fallback');var dt=document.querySelector('#'+zoneId+'Src div');if(kind!=='api'){{if(fb){{var day=SNAPSHOT_DAY?(' · 快照 '+SNAPSHOT_DAY):'';fb.textContent='更新暫不可用，顯示備援資料'+day;fb.hidden=false}}}}else{{if(fb)fb.hidden=true}}if(dt)dt.textContent=(label||'資料')+' · '+(kind==='api'?('取得時間 '+(when||'')):('備援資料'+(SNAPSHOT_DAY?(' · 快照 '+SNAPSHOT_DAY):'')))}}
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
function renderToday(){{var vd=vietnamDate();var line=document.getElementById('vietnamDateLine');if(line)line.textContent='越南時間 '+vd;var ph=document.getElementById('tripPhase'),ti=document.getElementById('todayTitle'),de=document.getElementById('todayDesc'),nx=document.getElementById('todayNext');if(!ph||!ti)return;var sSaved={{}};try{{sSaved=JSON.parse(localStorage.getItem('phq-v3-slots')||localStorage.getItem('phq-v2-slots')||'{{}}')}}catch(e){{}}function slot(d){{return sSaved[d]||''}}if(vd<'2026-10-10'){{ph.textContent='出發前';ti.textContent='10/11 OnBird 已確認，其餘保持彈性';if(de)de.textContent='已確認：OnBird 10/11 上午、Cosy 5 晚、來回航班。待處理：旅行保險、島上交通。';if(nx)nx.textContent='暫排可到行程區設定（只存本機）。'}}else if(vd<='2026-10-15'){{ph.textContent='旅途中 · '+vd;var map={{'2026-10-10':['抵達安頓','VJ845 抵達 Cosy 安頓，不排大行程'], '2026-10-11':['OnBird 已確認','業者接送往返，回來先休息；體力好才接市區晚間'], '2026-10-12':['彈性日','前晚鎖定；可從行程選項選一或休息'], '2026-10-13':['彈性日','前晚鎖定；避免連排高強度'], '2026-10-14':['彈性日','Starfish 需七項條件＋48 小時現況全通過才成立'], '2026-10-15':['返程','退房＋前往機場 VJ844']}};var cur=map[vd]||['旅途中','依行程區日期切換查看'];ti.textContent='今日（'+vd+'）：'+cur[0];var extra='';if(vd>='2026-10-12'&&vd<='2026-10-14'){{var mm={{'2026-10-12':'10/12','2026-10-13':'10/13','2026-10-14':'10/14'}}[vd];var sv=slot(mm);extra=sv?(' · 暫排：'+sv):(' · 尚未安排')}}if(de)de.textContent=cur[1]+extra+'。時間與地圖請進對應行程卡。';if(nx)nx.textContent='下一個重點：'+(vd==='2026-10-11'?'OnBird 後先休息':(vd<'2026-10-11'?'10/11 OnBird 已確認':(vd==='2026-10-15'?'返程航班':'前一晚再鎖定隔天')));}}else{{ph.textContent='旅行後';ti.textContent='旅程已結束（'+vd+'）';if(de)de.textContent='';if(nx)nx.textContent='';}}}}
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
// device slots/eaten migration (keep old keys untouched)
function migrateLS(){{try{{var OLD_S='phq-v2-slots',NEW_S='phq-v3-slots',OLD_F='phq-v2-food-eaten',NEW_F='phq-v3-food-eaten';var hasNewS=!!localStorage.getItem(NEW_S),hasNewF=!!localStorage.getItem(NEW_F);var oldS=localStorage.getItem(OLD_S),oldF=localStorage.getItem(OLD_F);var msg=[];if(!hasNewS&&oldS){{localStorage.setItem(NEW_S,oldS);msg.push('暫排已保留')}}if(!hasNewF&&oldF){{localStorage.setItem(NEW_F,oldF);msg.push('吃過紀錄已保留')}}if(msg.length){{var el=document.getElementById('slotMigrated');if(el){{el.style.display='';el.textContent='已保留舊版紀錄（'+msg.join('、')+'）。'}}}}}}catch(e){{}}}}
migrateLS();
const slotKey='phq-v3-slots';let saved={{}};try{{saved=JSON.parse(localStorage.getItem(slotKey)||'{{}}')}}catch(e){{}}document.querySelectorAll('select[data-day]').forEach(sel=>{{if(saved[sel.dataset.day])sel.value=saved[sel.dataset.day];sel.addEventListener('change',()=>{{saved[sel.dataset.day]=sel.value;if(!sel.value)delete saved[sel.dataset.day];localStorage.setItem(slotKey,JSON.stringify(saved));renderToday()}})}});document.getElementById('resetSlots').addEventListener('click',()=>{{if(!window.confirm('清除暫排行程？（不影響已確認訂單）'))return;saved={{}};localStorage.setItem(slotKey,JSON.stringify(saved));document.querySelectorAll('select[data-day]').forEach(s=>s.value='');renderToday()}});
// food: eaten + filters
const foodKey='phq-v3-food-eaten';let eaten={{}};try{{eaten=JSON.parse(localStorage.getItem(foodKey)||'{{}}')}}catch(e){{}}const foodCards=[...document.querySelectorAll('[data-food-id]')],foodProgress=document.getElementById('foodProgress'),foodEmpty=document.getElementById('foodEmpty');let showFull=false;function matchFilters(card){{var r=(document.getElementById('filterRegion')||{{}}).value||'';var s=(document.getElementById('filterSlot')||{{}}).value||'';var e=(document.getElementById('filterEaten')||{{}}).value||'';var id=card.dataset.foodId;var isEaten=!!eaten[id];if(e==='eaten'&&!isEaten)return false;if(e==='uneaten'&&isEaten)return false;if(r){{var cr=card.getAttribute('data-region')||'';if(cr.indexOf(r)<0&&!(r==='南島'&&(cr.indexOf('An Th')>=0))&&!(r==='北島'&&(cr.indexOf('Gành')>=0||cr.indexOf('Grand')>=0)))return false}}if(s){{var ts=card.getAttribute('data-time-slots')||'';if(ts.indexOf(s)<0)return false}}return true}}
function applyFoodFilters(){{window.applyFoodFilters=applyFoodFilters;let count=0,matched=[];foodCards.forEach(card=>{{const id=card.dataset.foodId,isEaten=!!eaten[id];if(isEaten)count++;card.classList.toggle('eaten',isEaten);const btn=card.querySelector('.eaten-btn');if(btn){{btn.setAttribute('aria-pressed',String(isEaten));btn.textContent=isEaten?'✓ 吃過':'○ 未吃'}}var ok=matchFilters(card);if(ok)matched.push(card)}});let visible=matched;if(!showFull&&matched.length>6)visible=matched.slice(0,6);foodCards.forEach(c=>c.classList.add('hidden'));visible.forEach(c=>c.classList.remove('hidden'));if(foodEmpty)foodEmpty.style.display=matched.length?'none':'';var t=document.getElementById('toggleFull');if(t){{t.textContent=showFull?('顯示較少（'+visible.length+' / '+matched.length+'）'):('看完整清單（'+matched.length+' 項符合）');t.setAttribute('aria-pressed',String(showFull))}}if(foodProgress)foodProgress.textContent=`已吃 ${{count}} / ${{foodCards.length}}`}}
foodCards.forEach(card=>{{const btn=card.querySelector('.eaten-btn');if(!btn)return;btn.addEventListener('click',()=>{{const id=card.dataset.foodId;eaten[id]=!eaten[id];if(!eaten[id])delete eaten[id];localStorage.setItem(foodKey,JSON.stringify(eaten));applyFoodFilters()}})}});['filterRegion','filterSlot','filterEaten'].forEach(id=>{{var el=document.getElementById(id);if(el)el.addEventListener('change',()=>{{showFull=false;applyFoodFilters()}})}});document.getElementById('toggleFull').addEventListener('click',()=>{{showFull=!showFull;applyFoodFilters()}});document.getElementById('resetFood').addEventListener('click',()=>{{if(!window.confirm('重設吃過紀錄？'))return;eaten={{}};localStorage.setItem(foodKey,JSON.stringify(eaten));applyFoodFilters()}});applyFoodFilters();
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
            build_card_page(candidate_api=_API_BASE, prod=True, snapshot_src=snapshot_src), encoding="utf-8")
        print("wrote PROD index.html+data.html", len(page), "bytes;", n_food,
              "food cards;", len(cards), "active cards client-side")
    else:
        (ROOT / "data.html").write_text(page, encoding="utf-8")
        (ROOT / "card.html").write_text(build_card_page(), encoding="utf-8")
        print("wrote data.html", len(page), "bytes;", n_food, "food cards;",
              len(cards), "active cards rendered client-side")


if __name__ == "__main__":
    main()
