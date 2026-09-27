# Consolidated final-review fix wave — base `ee97af3`

Status: local engineering candidate corrected; **not** a release/production acceptance. No remote DB, production content, schedule seed, workflow push, preview or formal site write in this wave.

## Decisions and changes

1. `006_itinerary_model.sql` now admits a main card only from `onbird/vinwonders/cable/starfish/safari` when its source row is `ACTIVE`, and meal references only `food/pool` in both main and replacement segments. The public JS validator also rejects non-active main cards. Rejected requests leave day/version, audit count and request count unchanged; accepted PostgreSQL projections are passed through the actual Node `validateEnvelope`.
2. Initialization, not a Chat edit or the migration, must provide `locked_constraints.onbird_core` with **exactly** `date,segment_id,kind,ref,time_kind,start_window,day_offset,timezone,duration_minutes`. The main OnBird 10/11 activity must match operative ID/kind/card and reviewed scheduled local window/timezone/duration. Absence/malformed core blocks all ordinary edits; 10/11 unrelated breakfast/evening edits remain allowed. Only synthetic fixtures contain `08:00–09:00`; **no real morning time was chosen here**.
3. Separately reviewed initialization must provide `locked_constraints.starfish` with `conditions` (at least two machine keys including `return`, each value the exact existing public Starfish `cards.gates` text) and `return_base` (approved `bases` key). The projection exposes only public `condition_labels` on that card; the reader displays mapped source gate text, not private lock fields. Missing/malformed configuration prevents Starfish selection. Its main activity must carry every condition; the first actual Starfish-origin main-route return transfer must occur after the activity, lead to the approved base, use `charter` or `operator_pickup`, and carry the `return` condition. Grab-first plus an unrelated or later charter cannot satisfy this. Other default cards need no Starfish config. The DB/Chat runbooks and `CONTENT_CONTRACT.md` document initialization/protection precisely; no independent long-term travel-fact copy was added.
4. The production browser verifier opens each day’s backups and checks count, visible trigger/action/targets and replacement labels/stable refs/transfers. It clicks an actual five-card href, requires a 200 HTML card with visible heading, returns to the page within the existing bounded watchdog and requires the live revision on return. The original page-consumed response is drained/validated **before** navigation, never replaced by a verifier fetch. Local browser fixtures include omitted backups and a 404 card; the local e2e helper now serves the real card-one API shape when a slug is specified.

## Red → green evidence

Environment: `source /tmp/opencode/phq-pg18-test-env`, local PG18.6 private socket; `006` was re-applied **only** to this guarded local test database, never remote. Rollback fixtures clean up synthetic rows. No source/prod schedule seed.

| Phase | Command / result |
| --- | --- |
| Red, after new DB regression tests and before SQL correction | `python3 -m unittest discover -s tools/verify -p 'test_itinerary_update.py' -v` → 17 tests, **6 failures**: retired/optional main cards, card-valued meal, missing core, altered OnBird core, and unconfigured Starfish were accepted. The test helper compared full before/after snapshots including audit and request counts. |
| Green DB / ACL / projection / export / update | `python3 -m unittest discover -s tools/verify -p 'test_itinerary_*.py'` → **47/47 passed** on final SQL (including migration rerun and private web-role denials). Rejected attempts are savepoint-rolled back and compare receipt/audit/version snapshots; valid cable/Starfish projections pass actual JS `validateEnvelope`. |
| Green Node reader/contract/publish/browser | `node --test tools/verify/test_itinerary_reader.mjs tools/verify/test_site_check_browser.mjs tools/verify/test_site_check_contract.mjs tools/verify/test_site_check_publish.mjs` → **36/36 passed**. Negative omitted-backup and 404-card cases return `CONTENT_MISMATCH`, not `PASS`; bounded pending navigation/body and real reader cases pass. Browser negatives were not separately executed against the pre-fix verifier; the whole-branch review supplied that counterexample. |
| Green integrated local chain | `node tools/verify/itinerary_e2e_candidate.mjs` → **LOCAL FIXTURE PASS**, rollback PG18 edit/audit → public export → generated candidate → Chromium verifier → fake immutable GitHub result. Local helper’s card-one route was corrected while exercising the real navigation. |
| Diff hygiene | `git diff --check` → clean. |

## Remaining risks / release gates

- The actual approved OnBird timing/operative segment and Starfish key-to-source-gate/return-base mapping **do not exist in this commit**; a separately authorized, reviewed initialization is necessary. If content cannot be verified, fail closed; do not use the synthetic times, gate strings or base.
- The invoker update never changes `locked_constraints`, and the web role cannot access private rows. A privileged DB owner can still bypass procedure/ACL controls; an exceptional lock correction needs separate review. SQL cannot prove geographic route feasibility or actual operator availability merely from stable refs, modes and order; content/operator review remains essential.
- Isolated Neon role ownership/ACL, real Function/Pages deployment, genuine Chat readback, formal browser CI and phone acceptance remain distinct release gates. No production migration, writes, fallback publication, preview or release was attempted.

## Narrow corrective pass after `final-rereview.md` (base `4b141ea`)

The re-review found two remaining Important gaps and one Minor gap in this wave's paths. This pass changes only their accepted behavior: SQL checks each segment/transfer condition key against cards actually referenced **on that segment/transfer**, matching the JS validator; it no longer borrows the Starfish main-card gate for an unrelated meal. A single invoker-only `itinerary_starfish_route_ok` helper validates the reviewed configuration, all required activity conditions and first ordered, conditioned return for both main segments and each flat executable `use_alternative.replacement_segments` route containing Starfish. Other alternatives do not require Starfish configuration or gain nesting. The web role cannot execute the helper. The browser verifier follows **all five** card hrefs, checks HTTP 200/visible heading and live-revision return under its existing single watchdog; original consumed response evidence is preserved. No real gate text, time, base or content was seeded.

### Focused red → green (local private-socket PG18 and isolated Chromium only)

| Check | Before fix (`4b141ea` SQL/verifier) | After fix |
| --- | --- | --- |
| `source /tmp/opencode/phq-pg18-test-env; python3 -m unittest discover -s tools/verify -p 'test_itinerary_update.py' -k 'test_unrelated_meal_cannot_borrow_starfish_condition_key' -v` | **FAIL**, `AssertionError: Error not raised`: unrelated meal `return` key admitted; no rejection. | **OK**, 1 test; `INVALID_PLAN`, snapshot equality includes itinerary version, public revision, audit and request counts; a corrected plan is accepted and passes JS `validateEnvelope`. |
| Same command, `-k 'test_cable_backup_starfish_requires_conditions_and_ordered_return'` | **FAIL**, `AssertionError: Error not raised`: cable backup with unconditioned Starfish and Grab-only return admitted. | **OK**, 1 test; rejects missing gate/Grab, accepts a synthetic conditioned charter branch, validates projected envelope, then rejects removed gate/Grab regression with unchanged snapshot. |
| `source /tmp/opencode/phq-pg18-test-env; node --test --test-name-pattern='non-first 404' tools/verify/test_site_check_browser.mjs` | **FAIL**, actual status `PASS` rather than expected `CONTENT_MISMATCH` when only cable's card returns 404. | **PASS**; both success and non-first-404 fixtures assert the browser visited all five slugs. |

The migration was re-applied **only** to the guarded local PG18 socket before green DB runs. During the full run, the existing gate-drift test needed to assert `INVALID_PLAN` before the now-invalid source projection is read: changing a used card gate invalidates the current envelope immediately; the test restores source text and verifies the original snapshot. This is fail-closed behavior, not a production data change.

### Full affected suite output (final pass)

Commands use `source /tmp/opencode/phq-pg18-test-env` (no remote credentials). Full output from the final Python run:

```text
$ python3 -m unittest discover -s tools/verify -p 'test_itinerary_*.py'
.................................................
----------------------------------------------------------------------
Ran 49 tests in 33.025s

OK
source: neon (DATABASE_URL host redacted)
foods 2 bytes -> /tmp/tmpllz4k_l7/foods.json
points 2 bytes -> /tmp/tmpllz4k_l7/points.json
cards 2 bytes -> /tmp/tmpllz4k_l7/cards.json
bookings 2 bytes -> /tmp/tmpllz4k_l7/bookings.json
pool 2 bytes -> /tmp/tmpllz4k_l7/pool.json
snapshot 374 bytes -> /tmp/tmpllz4k_l7/snapshot.json
itinerary 1552 bytes -> /tmp/tmpllz4k_l7/itinerary.json
counts: {'foods': 0, 'carriers': 0, 'points': 0, 'cards': 0, 'bookings': 0, 'transport': 0, 'pool': 0}
source: neon (DATABASE_URL host redacted)
foods 2 bytes -> /tmp/tmp5pfubdln/foods.json
points 2 bytes -> /tmp/tmp5pfubdln/points.json
cards 2 bytes -> /tmp/tmp5pfubdln/cards.json
bookings 2 bytes -> /tmp/tmp5pfubdln/bookings.json
pool 2 bytes -> /tmp/tmp5pfubdln/pool.json
source: neon (DATABASE_URL host redacted)
```

The Python exporter paths above are synthetic temporary test artifacts, not public data or an export publication. `neon` is a mocked source label, not a remote write.

```text
$ node --test --test-reporter=dot tools/verify/test_itinerary_reader.mjs tools/verify/test_site_check_browser.mjs tools/verify/test_site_check_contract.mjs tools/verify/test_site_check_publish.mjs
....................
..................
```

The same Node suite under the detailed default reporter returned **38 tests, 38 pass, 0 fail**. The dot reporter's two lines above represent all 38 tests. The integrated check also returned:

```text
$ node tools/verify/itinerary_e2e_candidate.mjs
LOCAL FIXTURE PASS: PG18 rollback update/audit -> public view/export -> generated candidate -> Chromium verifier -> fake GitHub immutable result
```

The original outstanding release/authorization gates above are unchanged. No production or remote/network write, published site change, real schedule or gate mapping was attempted.
