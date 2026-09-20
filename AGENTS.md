# AGENTS.md — phu-quoc-2026-mobile

## Canonical site (don't guess)
- Production = GitHub Pages `https://ga815647.github.io/phu-quoc-2026-mobile/`, source `main` / root (per `README.md`).
- `*.chatgpt.site` refs are rollback-only history. `MIGRATION_MANIFEST.json` / `SITE_SYNC_MANIFEST.json` / `PARITY_CHECK.md` are dated evidence, not current truth.
- `v2.html` is an unaccepted candidate. `data.html` + `card.html` are the data-driven pages. Never hand-edit generated `data.html`/`card.html` — edit `tools/build_site.py` + `tools/site.css`.

## Source of truth
- `data/phuquoc.db` (SQLite, WAL) is the only truth; Notion is frozen/archive. Pages consume `data/*.json` snapshots, never the DB directly.
- After any DB write: `export_json.py` → `snapshot.json`/`bookings.json` etc., then `build_site.py` if UI changed.
- Trip rule: 5 cards `onbird/vinwonders/cable/starfish/safari`; `anthoi`=OPTIONAL satellite, `khem`=RETIRED (never render as card). `bookings.status`: `Confirmed` vs `Open` (`Open` = tracking list). Mid-trip: only `INSERT INTO evidence_log`, don't rewrite main tables (per `data/AGENT_QUERY.md`).
- Answers about places/cards must carry `last_verified` / `evidence_as_of`; >30 days → mark 出發前重查.

## Commands (Windows PowerShell 5.1, Python 3.14)
- `$env:PYTHONUTF8=1; python tools/export_json.py` — required; without it `export_json.py` crashes on `cp950` (`open(p,"w")` has no encoding).
- `$env:PYTHONUTF8=1; python tools/build_site.py` — regenerates `data.html` + `card.html` from `data/snapshot.json`.
- `python tools/etl_points.py` — points ETL only; food/carrier need Notion query first (usually skip; Notion frozen).
- Verify: `SELECT slug,kind,amount,status FROM bookings` and reload `data/bookings.json` after export.

## Gotchas
- Workdir `E:\CS\projects\富國島` contains CJK; `glob` may return nothing — use `read` on directories and `bash` with `workdir` instead of `cd`.
- Console is `cp950`: printing `↔`/CJK from sqlite crashes; set `PYTHONUTF8=1` and avoid bare `print(row)` with wide chars.
- `git status` shows repo-wide LF→CRLF warnings; ignore the noise — real diffs are `data/bookings.json`, `data/phuquoc.db`, `data/snapshot.json`.
- CI `data-smoke.yml` (Playwright, 390px mobile) asserts: 5 `a.link-card` (`cable/vinwonders/onbird/starfish/safari`), food pool count, `ACTIVE`/`VERIFY` badges, touch targets ≥41px, no-hash nav, `localStorage` eaten/slots persistence, no horizontal overflow. Keep these green.
- `.agents/skills/frontend-design` is vendored (pinned). The proprietary Product Design plugin must NOT be copied into the repo.
