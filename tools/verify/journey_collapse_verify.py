"""Journey regression: departure checklist collapsed + no stale insurance text.

Focused UI-only checks (no network, no DB, no repo writes):
- builds a candidate page into an isolated /tmp dir via
  `build_site.py --api-base/--out-dir` (existing convention: candidate
  builds never touch formal output)
- asserts the journey departure checklist (6 entries preserved) renders
  inside a native collapsed <details> (no `open`), with an accessible
  summary target (>=44px) and visible keyboard focus in tools/site.css
- asserts the stale hardcoded "pending insurance" copy is gone from
  renderToday; the pre-trip description must defer to the dynamic
  #todayBookings area instead

Usage: PYTHONUTF8=1 python3 tools/verify/journey_collapse_verify.py
Exit 1 on any FAIL.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = Path("/tmp/opencode/journey-verify/candidate")
FAIL = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_site.py"),
         "--api-base", "https://example.invalid",
         "--out-dir", str(OUT)],
        capture_output=True, text=True, cwd=str(ROOT))
    check("candidate-build", r.returncode == 0, (r.stderr or r.stdout)[-200:])
    if r.returncode != 0:
        print(f"TOTAL FAIL {len(FAIL)}")
        sys.exit(1)
    cand = OUT / "data-candidate.html"
    check("candidate-exists", cand.exists(), str(cand))
    html = cand.read_text(encoding="utf-8")

    # 1. departure checklist collapsed in native details (default closed)
    m = re.search(r"<details([^>]*)>\s*<summary[^>]*>(.*?)</summary>(.*?)</details>",
                  html, re.S)
    dep = None
    if m and "出發前確認" in m.group(2):
        dep = m
    else:
        for mm in re.finditer(r"<details([^>]*)>(.*?)</details>", html, re.S):
            if "出發前確認" in mm.group(2):
                dep = mm
                break
    check("departure-collapsed-details", dep is not None,
          "native <details> with 出發前確認 summary" if dep else "no such details")
    if dep is not None:
        attrs = dep.group(1) if len(dep.groups()) == 3 else dep.group(1)
        body = dep.group(0)
        check("departure-default-closed", "open" not in attrs.split(),
              f"details attrs=[{attrs.strip()}]")
        entries = ["OnBird", "纜車", "VinWonders", "海星", "Safari", "用餐"]
        missing = [e for e in entries if e not in body]
        check("departure-6-entries", not missing,
              f"missing={missing}" if missing else "all 6 preserved")
    else:
        check("departure-default-closed", False, "no details found")
        check("departure-6-entries", False, "no details found")

    # 2. accessible summary target + keyboard focus in CSS (existing conventions:
    # min-height:44px touch targets, :focus-visible outline)
    css = (ROOT / "tools" / "site.css").read_text(encoding="utf-8")
    check("departure-summary-target",
          re.search(r"\.depart-check summary\{[^}]*min-height:44px", css) is not None,
          ".depart-check summary min-height:44px")
    check("departure-focus-visible",
          ".depart-check summary:focus-visible" in css,
          "focus-visible covers departure summary")

    # 3. stale hardcoded insurance pending text eliminated; dynamic area referenced
    check("no-stale-insurance-pending", "待處理：旅行保險" not in html,
          "hardcoded booking status removed")
    check("today-defers-to-dynamic",
          "todayBookings" in html and "以今天區預訂摘要與下方旅程區為準" in html,
          "pre-trip copy points at dynamic bookings area (below, not above)")

    # 4. guardrails: 5 cards + food/localStorage/nav conventions untouched
    # (candidate builds use card-candidate.html?slug=; prod uses card.html?slug=)
    check("cards-intact", ("card.html?slug=" in html or "card-candidate.html?slug=" in html), "card link template present")
    check("booking-semantics-intact", "已確認" in html and "待處理" in html,
          "Confirmed/Open natural labels survive")
    check("no-sum-note-intact", "不同幣別不直接加總" in html, "audit note survives")

    print(f"TOTAL FAIL {len(FAIL)}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
