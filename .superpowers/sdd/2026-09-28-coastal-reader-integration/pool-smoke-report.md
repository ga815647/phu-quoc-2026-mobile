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

## Follow-up: generic null-ID display (same task continuation)

- `tools/build_site.py` now uses an unmatched pool row's existing `order_copy`, then `desc_copy`, then stable key as its visible name. Runtime `/api/pool` hydration likewise updates only a null-ID card's visible name from that response; `data-food-id` and eaten storage remain keyed by the unchanged `pool_key`. No map link or research badge is fabricated.
- `tools/itinerary-reader.mjs` resolves null-ID pool references from the same public copy fields, rather than exposing the stable key in the six-day route/Today. `tools/verify/site-check-browser.mjs` uses the same rule to compare actual visible copy against the consumed API payload.
- Focused tests: `python3 -m unittest tools/verify/test_food_pool_generic.py` passed (human names, two stable IDs, no invented map); `node --test tools/verify/test_itinerary_reader.mjs` passed (13 tests, including null-ID rendered segment/name/map regression). The generator test initially failed on slug output before the fix.
- Added a real-reader B2 site-check fixture variant for null-ID pool copy and preserved reference ID. **Browser execution remains blocked on this VPS:** Playwright Chromium cannot start because `libatk-1.0.so.0` is missing; `node --test --test-name-pattern='generic pool' tools/verify/test_site_check_browser.mjs` exits before page setup. Existing real-B2 browser check likewise cannot be claimed as passing here. Run it in CI / a browser-equipped environment before release.
- Retried both existing and new real-B2 cases with `node --test --test-name-pattern='real B2 reader renders' tools/verify/test_site_check_browser.mjs`: both stopped at the same missing Chromium shared library, before assertions. `node --check` of both site-check modules and scoped `git diff --check` passed.
- No source JSON, remote data, deploy or maps were changed. The two distinct park labels remain the private initializer's responsibility; if `order_copy` is the same generic string in both records, both visible labels will be the same until content changes.
