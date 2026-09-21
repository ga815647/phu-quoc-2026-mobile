"""Candidate UI acceptance (headless Chromium, isolated outputs only).

Covers the 10-item PASS/FAIL table: 3-zone API success, 3 single-zone
failures (route abort, other APIs live), full fallback, foods dynamic
refresh via response override (no Neon writes), 5 cards detail+back,
8 bookings, localStorage persistence across reload, 390px overflow.
Writes screenshots + results.json to the shots dir. No repo writes.
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

SHOTS = "/tmp/opencode/phuquoc-candidate/verify-shots"
SITE = "http://127.0.0.1:8000/data-candidate.html"
SITE_FAIL = "http://127.0.0.1:8001/data-candidate.html"
CARD = "http://127.0.0.1:8000/card-candidate.html?slug="
FUNC = ("https://br-wispy-paper-b3b7t06k-phqreadonly."
        "compute.c-4.ap-southeast-1.aws.neon.tech")

results = []


def check(name, ok, detail=""):
    results.append({"item": name, "pass": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + (" | " + detail if detail else ""))


def banner_text(page, bid):
    el = page.locator(f"#{bid}")
    if el.count() == 0:
        return ""
    try:
        return (el.inner_text() or "").strip()
    except Exception:
        return ""


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # --- 1. all API success (desktop) ---
        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(SITE, wait_until="networkidle")
        pg.wait_for_timeout(2500)
        sb, bb, fb = (banner_text(pg, "srcBanner"),
                      banner_text(pg, "bookSrcBanner"),
                      banner_text(pg, "foodSrcBanner"))
        cards = pg.locator("#cardsMount .link-card").count()
        check("1-all-api-success", "測試 API 資料" in sb and cards == 5
              and "測試 API 資料" in bb and "測試 API 資料" in fb,
              f"cards={cards} src={sb[:14]} book={bb[:14]} food={fb[:14]}")
        # bookings content
        panel = pg.locator("#bookingsPanel").inner_text()
        check("8-bookings", "CONFIRMED" in panel and "OPEN" in panel,
              f"panel_len={len(panel)}")
        pg.screenshot(path=f"{SHOTS}/1-all-success.png")
        pg.close()

        # --- single-zone failures via route abort ---
        for name, block, zone in [
            ("2-fail-bookings", "/api/bookings", "book"),
            ("3-fail-cards", "/api/cards", "cards"),
            ("4-fail-foods", "/api/foods", "foods"),
        ]:
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            ctx.route(f"**{block}*",
                      lambda r: r.abort())
            pg = ctx.new_page()
            pg.goto(SITE, wait_until="networkidle")
            pg.wait_for_timeout(2500)
            sb, bb, fbb = (banner_text(pg, "srcBanner"),
                           banner_text(pg, "bookSrcBanner"),
                           banner_text(pg, "foodSrcBanner"))
            cards = pg.locator("#cardsMount .link-card").count()
            if zone == "book":
                ok = ("備援靜態資料" in bb and "測試 API 資料" in sb
                      and "測試 API 資料" in fbb and cards == 5)
            elif zone == "cards":
                ok = ("備援靜態資料" in sb and cards == 5
                      and "測試 API 資料" in bb and "測試 API 資料" in fbb)
            else:
                ok = ("備援靜態資料" in fbb and "測試 API 資料" in sb
                      and "測試 API 資料" in bb and cards == 5)
            check(name, ok, f"cards={cards} src={sb[:10]} book={bb[:10]} food={fbb[:10]}")
            pg.screenshot(path=f"{SHOTS}/{name}.png")
            pg.close()
            ctx.close()

        # --- 5. full fallback (site-fail) ---
        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(SITE_FAIL, wait_until="networkidle")
        pg.wait_for_timeout(2500)
        sb, bb, fbb = (banner_text(pg, "srcBanner"),
                       banner_text(pg, "bookSrcBanner"),
                       banner_text(pg, "foodSrcBanner"))
        cards = pg.locator("#cardsMount .link-card").count()
        panel = pg.locator("#bookingsPanel").inner_text()
        check("5-full-fallback", "備援靜態資料" in sb and cards == 5
              and "備援靜態資料" in bb and "CONFIRMED" in panel
              and "備援靜態資料" in fbb,
              f"cards={cards} src={sb[:10]} book={bb[:10]} food={fbb[:10]}")
        pg.screenshot(path=f"{SHOTS}/5-full-fallback.png")
        pg.close()

        # --- 6. foods dynamic refresh via fixture override (no Neon write) ---
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})

        def override(route):
            resp = route.fetch()
            data = resp.json()
            for f in data["data"]:
                if "Bún Kèn" in (f.get("name") or ""):
                    f["region"] = "FIXTURE-REGION"
                    f["atlas_state"] = "VERIFY"
            route.fulfill(response=resp, json=data)

        ctx.route(f"**/api/foods", override)
        pg = ctx.new_page()
        pg.goto(SITE, wait_until="networkidle")
        pg.wait_for_timeout(2500)
        card = pg.locator('[data-food-id="bun-ken-ut-luom"]')
        region = card.locator(".food-region").first.inner_text()
        badges = card.locator(".food-meta").inner_text()
        check("6-foods-refresh", "FIXTURE-REGION" in region and "VERIFY" in badges,
              f"region={region} badges={badges[:40]}")
        pg.screenshot(path=f"{SHOTS}/6-foods-refresh.png")
        pg.close()
        ctx.close()

        # --- 7. five cards detail + back ---
        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        slugs = ["onbird", "vinwonders", "cable", "starfish", "safari"]
        ok_all, detail = True, []
        for s in slugs:
            pg.goto(CARD + s, wait_until="networkidle")
            pg.wait_for_timeout(1500)
            body = pg.locator("body").inner_text()
            hit = s in pg.url and "找不到這張卡" not in body
            ok_all = ok_all and hit
            detail.append(f"{s}={'ok' if hit else 'BAD'}")
        pg.goto(CARD + "cable", wait_until="networkidle")
        pg.wait_for_timeout(1500)
        back = pg.locator('a[href="./data-candidate.html#cards"]')
        ok_all = ok_all and back.count() >= 1
        check("7-cards-detail-back", ok_all, " ".join(detail)
              + f" backlinks={back.count()}")
        pg.screenshot(path=f"{SHOTS}/7-card-detail.png")
        pg.close()

        # --- 9. localStorage persistence across reload ---
        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(SITE, wait_until="networkidle")
        pg.wait_for_timeout(2000)
        pg.locator('[data-food-id="bun-ken-ut-luom"] .eaten-btn').click()
        pg.select_option('select[data-day="10/12"]', index=1)
        pg.wait_for_timeout(500)
        pg.reload(wait_until="networkidle")
        pg.wait_for_timeout(2000)
        eaten = pg.locator('[data-food-id="bun-ken-ut-luom"] .eaten-btn').inner_text()
        slot = pg.locator('select[data-day="10/12"]').input_value()
        check("9-localstorage", "吃過" in eaten and slot != "",
              f"eaten={eaten} slot={slot}")
        # cleanup: reset so later runs start clean
        pg.evaluate("localStorage.removeItem('phq-v2-food-eaten');"
                    "localStorage.removeItem('phq-v2-slots');")
        pg.close()

        # --- 10. 390px overflow (mobile) ---
        pg = browser.new_page(viewport={"width": 390, "height": 844},
                              device_scale_factor=2, is_mobile=True)
        pg.goto(SITE, wait_until="networkidle")
        pg.wait_for_timeout(2500)
        overflow = pg.evaluate(
            "() => document.documentElement.scrollWidth - "
            "document.documentElement.clientWidth")
        pg.screenshot(path=f"{SHOTS}/10-mobile-390.png", full_page=True)
        check("10-390px", overflow <= 0, f"overflow_px={overflow}")
        pg.close()

        browser.close()

    json.dump(results, open(f"{SHOTS}/results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    fails = [r for r in results if not r["pass"]]
    print(f"TOTAL {len(results)} FAIL {len(fails)}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    os.makedirs(SHOTS, exist_ok=True)
    run()
