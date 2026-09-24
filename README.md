# Phu Quoc 2026 — Notion／Neon／GitHub 分工下的旅行資料系統

> 已定案分工：Notion＝日常閱讀操作（行程、行李、預算、待辦）；
> Neon＝詳細可查旅遊資料（候選、研究、來源、查核）；GitHub＝程式、
> migration、正式契約與 instructions 原始檔。網站是旅途中執行介面之一，
> 不是維護中心；日常更新不依賴網站匯出與發布。

Traveler-facing website (one interface, not the maintenance center):
- https://ga815647.github.io/phu-quoc-2026-mobile/

Deployment:
- repository: ga815647/phu-quoc-2026-mobile
- source: main / (root)
- GitHub Pages is the current/canonical website, per the user's explicit durable correction on 2026-09-14.
- Legacy `chatgpt.site` references are historical / rollback-only and are not the current website.

Historical manifests such as `MIGRATION_MANIFEST.json` and `SITE_SYNC_MANIFEST.json` preserve the evidence and state of their dated migration/staging runs. Their pre-cutover status fields are historical evidence and must not be treated as current canonical website truth.

Data backend (cutover 2026-09-22):
- Website SSOT: Neon Postgres `phu-quoc-2026` / production branch / `neondb`.
- Read-only API: Neon Function `phqreadonly`
  (`https://br-silent-haze-b3xw64tm-phqreadonly.compute.c-4.ap-southeast-1.aws.neon.tech/`),
  restricted role `phq_web_ro`, public-column contract only.
- `data/*.json` are the public-projection offline fallback, regenerated from Neon.
- SQLite `data/phuquoc.db` is the migration-frozen archive.

Content split (2026-09-23): the website serves trip execution; private preparation (payment tracking, budgets, packing and retained comparisons) stays in private Notion, with no automatic two-way sync or private links/data in this public repo. Existing Notion research and Food Atlas remain historical reference. See `CONTENT_CONTRACT.md` §8 for maintenance boundaries.

`v2.html` remains a separate UI/content candidate until it is explicitly accepted for promotion to the canonical GitHub Pages experience.

Ops evidence (2026-09-24–25, read-only re-verified, zero prod writes):
- `docs/ops/MIGRATION_MAP.md` — 全量 ID 集合比對（SQLite／Neon／JSON 三源；未處置項另列，不計入無缺漏）。
- `docs/ops/RETIREMENT.md` — old site kept as recovery entry; retirement conditions not yet met.
- `docs/ops/CHAT_ACCEPT.md` — one-shot Chat acceptance prompt, marked 待 ChatGPT 驗證（三態判定＋有效權限＋隔離優先）。
- `docs/ops/LOCALSTATE_EXPORT.md` — device localStorage export/import steps (user-device action).
