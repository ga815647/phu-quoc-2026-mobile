# AGENTS.md — phu-quoc-2026-mobile

## Canonical site (don't guess)
- Production = GitHub Pages `https://ga815647.github.io/phu-quoc-2026-mobile/`, source `main` / root (per `README.md`).
- `*.chatgpt.site` refs are rollback-only history. `MIGRATION_MANIFEST.json` / `SITE_SYNC_MANIFEST.json` / `PARITY_CHECK.md` are dated evidence, not current truth.
- `v2.html` is an unaccepted candidate. `index.html` + `data.html` + `card.html` are generated pages. Never hand-edit them — edit `tools/build_site.py` + `tools/site.css`.

## Source of truth (Neon cutover 2026-09-22)
- Travel data SSOT = Neon Postgres, project `phu-quoc-2026` (`holy-fog-65935796`,
  `aws-ap-southeast-1`, PG 18), branch `production` (`br-silent-haze-b3xw64tm`),
  database `neondb`. The website is one execution interface reading from it, not the maintenance center. `data/phuquoc.db` (SQLite) is the migration-frozen
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

## Content split (2026-09-23, user-approved)
- Private preparation lives in the Notion page `富國島 2026｜出發準備（私人）`: payment/cancellation tracking, private costs, cash estimates, packing and retained price comparisons. Find by title with the authenticated connector; never put its URL, private amounts or source documents in this public repo/site.
- Existing Notion Trip SSOT/research/handoffs/Food Atlas remain historical reference; their titles do not override Neon. Do not restart Notion ETL or copy the old tree. One maintenance location per field, no automatic two-way sync.
- Chat handles research and explicitly requested content updates in the appropriate destination; OpenCode handles engineering and fallback publication. Transient questions stay in chat. `Confirmed` is not paid; public `bookings.amount` is not a private expense ledger. Neon trip-time freeze does not freeze private Notion checklists.
- Keep the five cards, food shortlist and device-only state. Do not build packing, private accounting, login or cross-device sync to duplicate Notion; the old `user_state` proposal is deferred.

## Commands (Windows PowerShell 5.1, Python 3.14; VPS: python3 + PYTHONUTF8=1)
- `$env:PYTHONUTF8=1; $env:DATABASE_URL='<prod-owner-DSN-from-Neon-Console>'; python tools/export_json.py` — required; default source is now Neon. Without `PYTHONUTF8=1` it crashes on `cp950`.
- `python tools/build_site.py --prod` — regenerates `index.html` + `data.html` + `card.html` with the production Function API base + formal labels. Never run bare `build_site.py` for formal output; candidate builds always use `--api-base/--out-dir` into an isolated dir. UI-only changes need no DB write or JSON re-export.
- `python tools/etl_points.py` — historical points ETL; do not run against the formal dataset or reactivate Notion food/carrier ETL without separate approval.
- Verify: `SELECT slug,kind,amount,status FROM bookings` and reload `data/bookings.json` after export.

## Gotchas
- 2026-09-24 查證狀態：Neon 正式庫唯讀重查（各表筆數、ACL、ro 欄級 78／整表 0、
  Function deployment 5 行為）與契約一致；正式庫零寫入，寫入驗證走測試分支。
  舊 `connectors.md` 不存在；Chat 實測待驗（見 `docs/ops/CHAT_ACCEPT.md`）；
  舊站未退役（見 `docs/ops/RETIREMENT.md`）；搬遷對照見 `docs/ops/MIGRATION_MAP.md`。
- Workdir `E:\CS\projects\富國島` contains CJK; `glob` may return nothing — use `read` on directories and `bash` with `workdir` instead of `cd`.
- Console is `cp950`: printing `↔`/CJK from sqlite crashes; set `PYTHONUTF8=1` and avoid bare `print(row)` with wide chars.
- `git status` shows repo-wide LF→CRLF warnings; ignore the noise — real diffs are `data/bookings.json`, `data/phuquoc.db`, `data/snapshot.json`.
- CI `data-smoke.yml` (Playwright, 390px mobile) asserts: 5 `a.link-card` (`cable/vinwonders/onbird/starfish/safari`), food pool count, `ACTIVE`/`VERIFY` badges, touch targets ≥41px, no-hash nav, `localStorage` eaten/slots persistence, no horizontal overflow. Keep these green.
- `.agents/skills/frontend-design` is vendored (pinned). The proprietary Product Design plugin must NOT be copied into the repo.
