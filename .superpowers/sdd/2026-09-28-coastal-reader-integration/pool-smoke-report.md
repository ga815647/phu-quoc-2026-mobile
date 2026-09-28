# Pool smoke adaptation — 2026-09-28

## Change and scope

- `.github/workflows/data-smoke.yml` now reads `data/pool.json` from the trusted Actions checkout at the workflow commit and checks the live page against that count **and exact stable key set**, rather than learning an expected count from the live page. The deployment poll, initial progress, region/full-list checks and reset progress use `expectedPoolCount`.
- The checkout must retain at least 18 entries, valid unique `pool_key` values, and `bun-ken-ut-luom`; the rendered page must retain the named Bún Kèn Út Lượm. The 5-card, status/date, restaurant/filter, touch, storage and other original checks remain intact.
- No `tools/verify` smoke assertions required changes. `.github/workflows/v2-mobile-smoke.yml` also contains legacy literal 18 checks, but is outside the authorized writable paths and was not changed.
- No source JSON, generator, reader, CSS, database or remote deployment was modified by this task.

## Static validation

- Parsed `.github/workflows/data-smoke.yml` with PyYAML and extracted the embedded JavaScript; `node --check` passed.
- Exercised its checkout-pool preamble against the real 18-entry projection and a synthetic 20-entry projection containing `safari-inside` / `honthom-inside` (`notion_id: null`): accepted counts 18 / 20 respectively. Empty pool, removed Bún Kèn key, and duplicate key were rejected.
- `git diff --check -- .github/workflows/data-smoke.yml` passed.
- **Not run:** the live public Playwright smoke; the 20-entry checkout and matching site deployment are still pending. This static check is not deployment evidence.

## Read-only renderer compatibility finding

`tools/build_site.py:318-371` emits a food card per pool row, so null `notion_id` rows count toward progress and can be marked eaten by `pool_key`. However, for null IDs it assigns `name=pool_key`, region `—`, no research badge and no map link. The runtime `/api/foods` hydration (`tools/build_site.py:582-600`) matches by notion ID or the generated `data-food-name`; the null-ID card's empty name cannot match a normal foods record. `/api/pool` hydration only updates rank/divider/role/order/description, not the display name or map. **Thus the existing pool renderer can count/render the two generic rows but cannot display them as useful named park meal options with a map or verified restaurant details.** This is a release integration issue for the reader/generator owner, not addressed within this CI-only task.
