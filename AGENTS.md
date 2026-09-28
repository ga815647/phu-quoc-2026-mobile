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

## Experience redesign scope (2026-09-26)
- Before redesign work or subagent dispatch, read `docs/ops/REDESIGN_SCOPE.md` for agreed product decisions, allowed paths, content ownership, and stage status. Maintain it with changes affecting those boundaries.
- UI/design approval does not itself apply content decisions to Neon or change confirmed bookings. Six-day defaults and meal/transport-following behavior still need an approved data design; don't introduce an independently maintained hardcoded travel-data copy.
- Give every subagent explicit writable paths, data-write scope, and acceptance criteria. Keep live data updates, fallback publication, preview deployment, and Chat capability verification as separate outcomes.
- Chat's selected read route is GitHub for rules/code/published evidence and Neon for current travel content. Direct Chat HTTP access to the production site is not a required capability; OpenCode/CI and the user's phone validate runtime behavior. GitHub JSON remains a dated fallback, not live Neon data.
- Six-day itinerary release was explicitly authorized 2026-09-28. Production 006, six-day draft initialization and Function deployment6 are applied; site/Actions/target-Chat acceptance are individually recorded in `docs/ops/ITINERARY_RELEASE_20260928.md`. Follow `CONTENT_CONTRACT.md` §10 and `docs/ops/CHAT_ITINERARY_RUNBOOK.md`; do not confuse engineering evidence with target-Chat readback. Keep legacy phone edits until accepted.
- Approved future scope: Chat may update the new daily itinerary and meal/transport assignments during the trip via its validated controlled entry point; existing research tables and confirmed bookings keep current freeze/authorization rules. This is not permission to run a migration or use an unimplemented entry point. See CONTENT_CONTRACT.md §9.

## Agent skills

### Issue tracker
GitHub Issues is the user-selected decision tracker. Read `docs/agents/issue-tracker.md` for the current Wayfinder map, native dependencies, claiming and resolution procedures.

### Domain docs
Single-context glossary in `CONTEXT.md`; see `docs/agents/domain.md`. Keep terminology separate from permission contracts and implementation specs.

## Commands (Windows PowerShell 5.1, Python 3.14; VPS: python3 + PYTHONUTF8=1)
- `$env:PYTHONUTF8=1; $env:DATABASE_URL='<prod-owner-DSN-from-Neon-Console>'; python tools/export_json.py` — required; default source is now Neon. Without `PYTHONUTF8=1` it crashes on `cp950`.
- `python tools/build_site.py --prod --itinerary-mode candidate` — current transitional formal build: production Function API + A six-day reader, retaining legacy phone editing until target-Chat acceptance. Regenerates `index.html` + `data.html` + `card.html`, assets and site-version. The internal `candidate` mode is a compatibility mode, not a test-DB target. Do not omit this flag (default legacy drops the reader). Never run bare `build_site.py` for formal output; isolated builds use `--api-base/--out-dir`. UI-only changes need no DB write or JSON re-export.
- `python tools/etl_points.py` — historical points ETL; do not run against the formal dataset or reactivate Notion food/carrier ETL without separate approval.
- Verify: `SELECT slug,kind,amount,status FROM bookings` and reload `data/bookings.json` after export.

## Gotchas
- 2026-09-24 查證狀態：Neon 正式庫唯讀重查（各表筆數、ACL、ro 欄級 78／整表 0、
  Function deployment 5 行為）與契約一致；正式庫零寫入，寫入驗證走測試分支。
  2026-09-27 Chat 實測依使用者回報：GitHub／Notion 與正式 Neon row-returning 讀取通過，指定測試分支受控更新／還原／衝突通過；Chat HTTP／畫面仍未驗，六天模型尚未實作（見 `docs/ops/CHAT_ACCEPT.md`）；
  舊站未退役（見 `docs/ops/RETIREMENT.md`）；搬遷對照見 `docs/ops/MIGRATION_MAP.md`。
- Workdir `E:\CS\projects\富國島` contains CJK; `glob` may return nothing — use `read` on directories and `bash` with `workdir` instead of `cd`.
- Console is `cp950`: printing `↔`/CJK from sqlite crashes; set `PYTHONUTF8=1` and avoid bare `print(row)` with wide chars.
- `git status` shows repo-wide LF→CRLF warnings; ignore the noise — real diffs are `data/bookings.json`, `data/phuquoc.db`, `data/snapshot.json`.
- CI `data-smoke.yml` (Playwright, 390px mobile) asserts: 5 `a.link-card` (`cable/vinwonders/onbird/starfish/safari`), food pool count, `ACTIVE`/`VERIFY` badges, touch targets ≥41px, no-hash nav, `localStorage` eaten/slots persistence, no horizontal overflow. Keep these green.
- `.agents/skills/frontend-design` is vendored (pinned). The proprietary Product Design plugin must NOT be copied into the repo.
