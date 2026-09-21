# Phu Quoc 2026 Mobile Itinerary

Current traveler-facing website:
- https://ga815647.github.io/phu-quoc-2026-mobile/

Deployment:
- repository: ga815647/phu-quoc-2026-mobile
- source: main / (root)
- GitHub Pages is the current/canonical website, per the user's explicit durable correction on 2026-09-14.
- Legacy `chatgpt.site` references are historical / rollback-only and are not the current website.

Historical manifests such as `MIGRATION_MANIFEST.json` and `SITE_SYNC_MANIFEST.json` preserve the evidence and state of their dated migration/staging runs. Their pre-cutover status fields are historical evidence and must not be treated as current canonical website truth.

Data backend (cutover 2026-09-22):
- SSOT: Neon Postgres `phu-quoc-2026` / production branch / `neondb`.
- Read-only API: Neon Function `phqreadonly`
  (`https://br-silent-haze-b3xw64tm-phqreadonly.compute.c-4.ap-southeast-1.aws.neon.tech/`),
  restricted role `phq_web_ro`, public-column contract only.
- `data/*.json` are the public-projection offline fallback, regenerated from Neon.
- SQLite `data/phuquoc.db` is the migration-frozen archive.

`v2.html` remains a separate UI/content candidate until it is explicitly accepted for promotion to the canonical GitHub Pages experience.
