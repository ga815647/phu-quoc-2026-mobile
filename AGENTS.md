# AGENTS.md — phu-quoc-2026-mobile

## Canonical site (don't guess)
- Production = GitHub Pages `https://ga815647.github.io/phu-quoc-2026-mobile/`, source `main` / root (per `README.md`).
- `*.chatgpt.site` refs are rollback-only history. `MIGRATION_MANIFEST.json` / `SITE_SYNC_MANIFEST.json` / `PARITY_CHECK.md` are dated evidence, not current truth.
- `v2.html` is an unaccepted candidate. `data.html` + `card.html` are the data-driven pages. Never hand-edit generated `data.html`/`card.html` — edit `tools/build_site.py` + `tools/site.css`.

## Source of truth (Neon cutover 2026-09-22)
- SSOT = Neon Postgres, project `phu-quoc-2026` (`holy-fog-65935796`,
  `aws-ap-southeast-1`, PG 18), branch `production` (`br-silent-haze-b3xw64tm`),
  database `neondb`. `data/phuquoc.db` (SQLite) is the migration-frozen
  archive (`phuquoc-preprod-20260921.db` backup at repo parent); explicit
  opt-in only via `PHUQUOC_DB_SOURCE=sqlite`, never the default path.
- Website data flow: Pages → Neon Function `phqreadonly` (read-only,
  restricted role `phq_web_ro`) → Neon production; `data/*.json` (public
  projection) is the offline fallback, regenerated from Neon.
- After any Neon write: `export_json.py` (default source=neon) →
  `snapshot.json`/`bookings.json` etc., then `build_site.py --prod` if UI changed.
  Never point the formal site at the test branch; never fall back to SQLite silently.
- Trip rule: 5 cards `onbird/vinwonders/cable/starfish/safari`; `anthoi`=OPTIONAL satellite, `khem`=RETIRED (never render as card). `bookings.status`: `Confirmed` vs `Open` (`Open` = tracking list). Mid-trip: only `INSERT INTO evidence_log`, don't rewrite main tables (per `data/AGENT_QUERY.md`).
- Answers about places/cards must carry `last_verified` / `evidence_as_of`; >30 days → mark 出發前重查.

## Commands (Windows PowerShell 5.1, Python 3.14; VPS: python3 + PYTHONUTF8=1)
- `$env:PYTHONUTF8=1; $env:DATABASE_URL='<prod-owner-DSN-from-Neon-Console>'; python tools/export_json.py` — required; default source is now Neon. Without `PYTHONUTF8=1` it crashes on `cp950`.
- `python tools/build_site.py --prod` — regenerates `data.html` + `card.html` with the production Function API base + formal labels. Never run bare `build_site.py` for formal output; candidate builds always use `--api-base/--out-dir` into an isolated dir.
- `python tools/etl_points.py` — points ETL only; food/carrier need Notion query first (usually skip; Notion frozen).
- Verify: `SELECT slug,kind,amount,status FROM bookings` and reload `data/bookings.json` after export.

## Gotchas
- Workdir `E:\CS\projects\富國島` contains CJK; `glob` may return nothing — use `read` on directories and `bash` with `workdir` instead of `cd`.
- Console is `cp950`: printing `↔`/CJK from sqlite crashes; set `PYTHONUTF8=1` and avoid bare `print(row)` with wide chars.
- `git status` shows repo-wide LF→CRLF warnings; ignore the noise — real diffs are `data/bookings.json`, `data/phuquoc.db`, `data/snapshot.json`.
- CI `data-smoke.yml` (Playwright, 390px mobile) asserts: 5 `a.link-card` (`cable/vinwonders/onbird/starfish/safari`), food pool count, `ACTIVE`/`VERIFY` badges, touch targets ≥41px, no-hash nav, `localStorage` eaten/slots persistence, no horizontal overflow. Keep these green.
- `.agents/skills/frontend-design` is vendored (pinned). The proprietary Product Design plugin must NOT be copied into the repo.
