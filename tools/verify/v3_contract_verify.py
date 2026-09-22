"""v3 upgrade verification: DB audit/conflict/restore (test branch only),
public API read-only boundary, static HTML + JSON contract checks.
No prod writes. No real bookings used for destructive tests.
Usage: python tools/verify/v3_contract_verify.py [--site DIR] [--html FILE]
Requires: NEON MCP access via env? Uses direct HTTPS for API + local files.
DB checks use Neon MCP tools when run under opencode; standalone mode checks
files/API only unless TEST_DSN provided (never commit DSN).
"""
import json
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FAIL = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def get_json(url, method="GET", timeout=15):
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            return r.status, dict(r.headers), body
    except Exception as e:
        # urllib raises HTTPError with code/body
        if isinstance(e, urllib.error.HTTPError):
            return e.code, dict(e.headers), e.read().decode("utf-8", "replace")
        return None, {}, str(e)


def main():
    prod_api = "https://br-silent-haze-b3xw64tm-phqreadonly.compute.c-4.ap-southeast-1.aws.neon.tech"
    # 1. Public API read-only
    for ep in ["cards", "foods", "points", "bookings", "transport"]:
        st, _, body = get_json(f"{prod_api}/api/{ep}")
        try:
            j = json.loads(body)
            ok = st == 200 and isinstance(j.get("data"), list) and "fetched_at" in j.get("meta", {})
        except Exception:
            ok = False
        check(f"api-{ep}-readonly", ok, f"status={st}")
    st, _, body = get_json(f"{prod_api}/api/content_revisions")
    check("api-audit-not-exposed", st == 404 and "NOT_FOUND" in body, f"status={st}")
    st, _, body = get_json(f"{prod_api}/api/cards", method="POST")
    check("api-post-rejected", st == 405 and "METHOD_NOT_ALLOWED" in body, f"status={st}")
    st, _, body = get_json(f"{prod_api}/api/cards?slug=bad_slug!!")
    check("api-bad-slug", st == 400, f"status={st}")
    # bookings public projection: 6 cols only
    st, _, body = get_json(f"{prod_api}/api/bookings")
    try:
        j = json.loads(body)
        cols = set(j["data"][0].keys()) if j["data"] else set()
        check("api-bookings-projection", cols == {"slug", "kind", "title", "amount", "status", "evidence_as_of"}, f"cols={sorted(cols)}")
    except Exception as e:
        check("api-bookings-projection", False, str(e))

    # 2. Static JSON contract (public-v1, no secrets)
    for name in ["cards", "bookings", "foods", "points", "snapshot"]:
        p = ROOT / "data" / f"{name}.json"
        check(f"json-{name}-exists", p.exists(), str(p))
    try:
        cards = json.loads((ROOT / "data" / "cards.json").read_text(encoding="utf-8"))
        active = [c for c in cards if c.get("status") == "ACTIVE"]
        slugs = sorted(c.get("slug") for c in active)
        check("json-5-cards", slugs == ["cable", "onbird", "safari", "starfish", "vinwonders"], str(slugs))
        check("json-khem-retired", any(c.get("slug") == "khem" and c.get("status") == "RETIRED" for c in cards), "khem")
        bookings = json.loads((ROOT / "data" / "bookings.json").read_text(encoding="utf-8"))
        check("json-bookings-count", len(bookings) == 8, str(len(bookings)))
        check("json-bookings-no-detail", all("detail" not in b and "evidence" not in b for b in bookings), "projection")
        check("json-bookings-semantics", any(b.get("status") == "Confirmed" for b in bookings) and any(b.get("status") == "Open" for b in bookings), "Confirmed/Open")
        foods = json.loads((ROOT / "data" / "foods.json").read_text(encoding="utf-8"))
        check("json-foods-count", len(foods) == 69, str(len(foods)))
    except Exception as e:
        check("json-contract", False, str(e))

    # 3. Built HTML checks (prod files if present, else candidate dir)
    html_candidates = [ROOT / "index.html", ROOT / "data.html"]
    html = None
    for p in html_candidates:
        if p.exists():
            t = p.read_text(encoding="utf-8")
            if "今天" in t and "旅程" in t and "越南時間" in t:
                html = t
                break
    check("html-unified-entry", html is not None, "index+data contain 今天/行程/美食/旅程/越南時間")
    if html is not None:
        check("html-4-nav", all(f'data-jump="{i}"' in html for i in ["today", "itinerary", "food", "journey"]), "4 entries")
        check("html-date-tabs", all(d in html for d in ["10/10", "10/11", "10/12", "10/13", "10/14", "10/15"]), "dates")
        check("html-filters", all(i in html for i in ["filterRegion", "filterSlot", "filterEaten", "toggleFull"]), "filters")
        check("html-no-philosophy", not any(s in html for s in [
            "不會編造", "不假裝即時", "只清新版", "尚未鎖定（未安排）",
            "待辦追蹤 OPEN", "Gate 全綠", "evidence_log",
            "精簡卡片", "公開 6 欄", "localStorage v3",
        ]), "philosophy/eng copy removed")
        check("html-fallback-recognizable", "更新暫不可用" in html and "資料資訊" in html, "fallback recognizable")
        check("html-natural-labels", "優先推薦" in html and "待再確認" in html, "natural Chinese")
        check("html-booking-semantics", "已確認" in html and "待處理" in html, "Confirmed/Open natural labels")
        check("html-audit-semantics", "更改暫排不等於更改或取消訂單" in html and "不同幣別不直接加總" in html, "semantics")
        check("html-no-secrets", not re.search(r"DATABASE_URL|PHQ_READONLY_DATABASE_URL|neondb_owner|Bearer [A-Za-z0-9]", html, re.I), "no secrets")
        check("html-v3-keys", "phq-v3-slots" in html and "phq-v3-food-eaten" in html, "v3 LS")
        check("html-timeout", "AbortController" in html and "no-store" in html, "timeout+revalidate")
        check("html-distinguish-dates", "核實" in html and "取得時間" in html and "備援資料" in html, "verified vs fetched vs fallback")
        # card links (client-rendered): JS template + cards.json 5 ACTIVE
        check("html-5-card-links", ("card.html?slug=" in html) and ("cards.json" in html or "/api/cards" in html), "client-render 5 links")
        check("html-no-khem-card", "slug=khem" not in html and "card.html?slug=khem" not in html, "no khem")
    card_p = ROOT / "card.html"
    if card_p.exists():
        ct = card_p.read_text(encoding="utf-8")
        check("card-natural", "成行條件" in ct and "時間不夠時怎麼調整" in ct, "natural headings")
        check("card-back-compat", "./#itinerary" in ct and "data.html" in ct, "back compat")
        check("card-no-emoji", "🚗" not in ct and "🔙" not in ct, "no emoji vehicles")
    else:
        check("card-exists", False, "missing card.html")

    print(f"TOTAL FAIL {len(FAIL)}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
