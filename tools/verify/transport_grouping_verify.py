"""Transport grouping verification (TDD RED-first for main/backup/history display).

Covers the journey transport redesign:
- history rows (歷史方案) are never rendered
- main rows render as拆段 main cards (no ｜ blob)
- backup rows render inside a collapsed <details>
- grouping works for both new Neon vocab (已確認/主線/臨時備援/歷史方案)
  and legacy snapshot vocab (已鎖定/首選/可行/待正式班表)

Usage: python tools/verify/transport_grouping_verify.py
Exit 1 on any FAIL. No repo writes, no network, no DB.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
FAIL = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


NEON_ROWS = [
    {"slug": "tw-out-207-shoufeng", "direction": "去程",
     "plan": "去程｜壽豐轉 4513→207｜前段:區間 4513｜光復 06:12 出發(壽豐 06:41)｜主車:壽豐 07:08 自強3000 207→臺北 10:08｜轉乘27分｜票種:花東實名優先",
     "station": "壽豐", "status": "已確認", "priority": "主線",
     "note": "10/10 已付款未取票：壽豐 07:08 自強3000 207 → 臺北 10:08。此列為目前去程主線；4513 光復→壽豐為前段接駁。",
     "evidence_as_of": "2026-09-20"},
    {"slug": "tw-out-405", "direction": "去程",
     "plan": "去程｜207 沒搭到 → 405｜前段:區間 4513｜光復 06:12 出發(花蓮 07:05)｜主車:花蓮 07:55 自強3000 405→臺北 10:25｜轉乘-分｜票種:一般對號",
     "station": "花蓮", "status": "臨時備援", "priority": "備援",
     "note": "207 已訂妥；僅在當日漏乘／異常時參考 405。班表仍需行前重查。",
     "evidence_as_of": "2026-08-25"},
    {"slug": "tw-out-207-zhixue", "direction": "去程",
     "plan": "去程｜志學轉 4513→207｜前段:區間 4513｜光復 06:12 出發(志學 06:49)｜主車:志學 07:14 自強3000 207→臺北 10:08｜轉乘25分｜票種:花東實名優先",
     "station": "志學", "status": "歷史方案", "priority": "非目前行程",
     "note": "已由壽豐 07:08 搭 207 定案；本列僅保留作歷史規劃／異常改票參考。",
     "evidence_as_of": "2026-08-25"},
    {"slug": "tw-out-207-jian", "direction": "去程",
     "plan": "去程｜吉安轉 4513→207｜前段:區間 4513｜光復 06:12 出發(吉安 06:59)｜主車:吉安 07:21 自強3000 207→臺北 10:08｜轉乘22分｜票種:花東實名優先",
     "station": "吉安", "status": "歷史方案", "priority": "非目前行程",
     "note": "已由壽豐 07:08 搭 207 定案；本列僅保留作歷史規劃／異常改票參考。",
     "evidence_as_of": "2026-08-25"},
    {"slug": "tw-out-207-hualien", "direction": "去程",
     "plan": "去程｜花蓮轉 4513→207｜前段:區間 4513｜光復 06:12 出發(花蓮 07:05)｜主車:花蓮 07:30 自強3000 207→臺北 10:08｜轉乘25分｜票種:花東實名優先",
     "station": "花蓮", "status": "歷史方案", "priority": "非目前行程",
     "note": "已由壽豐 07:08 搭 207 定案；本列僅保留作歷史規劃／異常改票參考。",
     "evidence_as_of": "2026-08-25"},
    {"slug": "tw-back-434", "direction": "回程",
     "plan": "回程｜434 臺北→光復（安全首選）｜前段:VJ844 13:00抵TPE T1→入境→機捷A12→A1臺北→步行台鐵(約15:43-15:48到月台)｜主車:臺北 16:02 自強3000 434→光復 19:14｜轉乘-分｜票種:花東實名優先",
     "station": "臺北", "status": "已確認", "priority": "主線",
     "note": "10/15 已付款未取票：臺北 16:02 自強3000 434 → 光復 19:14。VJ844 13:00 抵 TPE 後保留轉乘緩衝；此列為目前回程主線。",
     "evidence_as_of": "2026-09-20"},
    {"slug": "tw-back-432", "direction": "回程",
     "plan": "回程｜432 臺北→光復（較快但偏趕）｜前段:VJ844 13:00抵TPE T1→入境→機捷A12→A1臺北(約14:43-14:48到月台)｜主車:臺北 15:00 自強3000 432→光復 17:58｜轉乘-分｜票種:一般對號",
     "station": "臺北", "status": "臨時備援", "priority": "備援",
     "note": "434 已訂妥；432 僅供當天入境與轉乘非常順利、且決定改搭較早班時參考，不作預設。班表仍需行前重查。",
     "evidence_as_of": "2026-08-25"},
]

# Legacy snapshot vocab (data/transport.json pre-export): same shapes, old labels.
OLD_ROWS = [
    {"slug": "tw-out-207-shoufeng", "direction": "去程", "plan": NEON_ROWS[0]["plan"],
     "station": "壽豐", "status": "待正式班表", "priority": "首選",
     "note": "207為壽豐始發；轉車最從容。", "evidence_as_of": "2026-08-25"},
    {"slug": "tw-out-207-zhixue", "direction": "去程", "plan": NEON_ROWS[2]["plan"],
     "station": "志學", "status": "待正式班表", "priority": "可行",
     "note": "小站轉乘人較少。", "evidence_as_of": "2026-08-25"},
    {"slug": "tw-out-405", "direction": "去程", "plan": NEON_ROWS[1]["plan"],
     "station": "花蓮", "status": "待正式班表", "priority": "備援",
     "note": "同路徑下一班車。", "evidence_as_of": "2026-08-25"},
]


def main():
    try:
        import build_site as b
        for fn in ("classify_transport_row", "split_plan_segments",
                   "group_transport_rows", "build_transport_html",
                   "build_transport_js"):
            assert callable(getattr(b, fn, None)), f"missing {fn}"
    except Exception as e:
        check("helpers-import", False, str(e))
        print(f"TOTAL FAIL {len(FAIL)}")
        sys.exit(1)
    check("helpers-import", True, "grouping helpers present")

    cats = {t["slug"]: b.classify_transport_row(t) for t in NEON_ROWS}
    check("classify-new-main",
          cats.get("tw-out-207-shoufeng") == "main" and cats.get("tw-back-434") == "main",
          str(cats))
    check("classify-new-backup",
          cats.get("tw-out-405") == "backup" and cats.get("tw-back-432") == "backup",
          str(cats))
    check("classify-new-history",
          all(cats.get(s) == "history" for s in
              ("tw-out-207-zhixue", "tw-out-207-jian", "tw-out-207-hualien")),
          str(cats))

    old = {t["slug"]: b.classify_transport_row(t) for t in OLD_ROWS}
    check("classify-old-vocab",
          old.get("tw-out-207-shoufeng") == "main"
          and old.get("tw-out-207-zhixue") == "history"
          and old.get("tw-out-405") == "backup",
          str(old))

    segs = b.split_plan_segments(NEON_ROWS[0]["plan"])
    check("split-segments",
          all("｜" not in s for s in segs) and segs[0] != "去程"
          and any(s.startswith("主車") for s in segs),
          str(segs))

    html = b.build_transport_html(NEON_ROWS)
    check("fallback-main-cards",
          "壽豐 07:08" in html and "自強3000 207" in html
          and "已付款未取票" in html
          and "臺北 16:02" in html and "自強3000 434" in html,
          f"len={len(html)}")
    check("fallback-backup-details",
          "<details" in html and "備援班次" in html
          and "405" in html and "432" in html,
          "backup inside collapsed details")
    check("fallback-no-history",
          all(s not in html for s in ("志學轉", "吉安轉", "花蓮轉")),
          "history rows not rendered")
    check("fallback-no-blob",
          "｜" not in html,
          "plan strings split, no raw ｜ blob")

    check("fallback-empty",
          "目前沒有交通備案資料" in b.build_transport_html([]),
          "empty-state survives")

    js = b.build_transport_js("https://example.invalid")
    # build_transport_js is ASCII-safe: CJK travels as \u escapes, so assert
    # on the escapes (備援班次 / 歷史方案 / 主線) plus the live structure.
    check("transport-js-grouping",
          "<details" in js and "t-backup" in js and "t-main" in js
          and "\\u5099\\u63f4\\u73ed\\u6b21" in js  # 備援班次
          and "\\u6b77\\u53f2\\u65b9\\u6848" in js  # 歷史方案
          and "\\u4e3b\\u7dda" in js  # 主線
          and "segT" in js and "clsT" in js and "fetchJson" in js,
          f"len={len(js)}")

    css = (ROOT / "tools" / "site.css").read_text(encoding="utf-8")
    check("css-transport",
          ".t-main" in css and ".t-backup summary" in css
          and "min-height:44px" in css,
          "main/backup styles + touch target")

    print(f"TOTAL FAIL {len(FAIL)}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
