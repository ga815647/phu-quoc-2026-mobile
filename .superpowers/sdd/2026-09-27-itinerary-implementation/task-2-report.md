# Task A2 — local implementation report

Base: `e997f92`. Scope: only 006 migration, DB test support, update tests, this report. No remote Neon, GitHub, production data, or deployment mutations.

## Delivered

- `itinerary_update` (SECURITY INVOKER, fixed search path): canonical full-request hash and receipt dedupe under itinerary row lock; stale private version and source fingerprint failures; candidate validation; fixed-order `FOR SHARE` source locks with pool→food closure recheck; full protected/explicit-decision checks; per-day version/audit; one itinerary version increment and receipt from post-write public view, all in one transaction. PUBLIC execute revoked; no change to A1 projection or its dependency expansion.
- Support: candidate from current fixture day (preserving non-activity segments/meal/transfer), UUID helper, update helper. Failure assertions use rollback/release savepoints. Committed per-test fixture for real two-session races cleans only named fixture IDs.
- Tests cover dedupe/hash changes, rollback on invalid second day, restore audit, UTF-8 byte limit, bad shapes/times, stale base/source, protected OnBird/booking, explicit choice decisions, web-role ACL, distinct/same request races and locked pool reassignment.

## Evidence (isolated PG18 Unix-socket `itinerary_test` only)

- RED: `python3 -m unittest discover -s tools/verify -p test_itinerary_update.py -v` → `FAILED (failures=6, errors=3)`; undefined `itinerary_update` (`42883`), before implementing SQL.
- Local migration applied with `python3 -c "import sys,pathlib,psycopg2;sys.path.insert(0,'tools/verify');from itinerary_db_support import test_dsn; db=psycopg2.connect(test_dsn());db.cursor().execute(pathlib.Path('tools/migrate_neon/006_itinerary_model.sql').read_text());db.commit();db.close();print('local migration applied')"` → `local migration applied`. `psql` was unavailable (`psql: command not found`), so used guarded psycopg2 DSN. Rerunnable migration applied again after SQL fixes.
- GREEN targeted: `python3 -m unittest discover -s tools/verify -p test_itinerary_update.py -v` → `Ran 9 tests in 9.382s`, `OK`.
- GREEN full suite (once after final changes): `python3 -m unittest discover -s tools/verify -p 'test_itinerary_*.py' -v` → `Ran 26 tests in 12.589s`, `OK`.
- `git diff --check` → exit 0, no output.

## Decisions / concerns for controller

- No generic temporary table or independent projection copy: `itinerary_dependency_ids` extracts source IDs from current + candidate plans, expands pool food, and compares the locked closure. New candidate references are validated against *current* locked rows; old fingerprint is not asserted to cover previously unreferenced facts.
- `locked_constraints.days[date]` may pin `day_kind`/`main_card_slug`; booked base refs already present on a date must stay on that date. Fixture fixes approved 10/11 OnBird; deployment still needs reviewed, populated flight/lodging locked constraints (not seeded by this migration). This does not certify all trip content.
- Explicit decisions are operation declarations, not proof of user authorization. `time.source_refs` remain shape-only strings, not a citation registry. No remote or production ACL/migration verification attempted.

## A2 review fix round 1/5 (following `task-2-review.md`)

- Protected booking bases present on the old main route must remain on the candidate **main route**, with the same segment kind and transfer-edge direction. An alternative-only booking or unrelated rest mention cannot satisfy the lock; a renamed/re-timed main transfer to the booked base remains allowed. This checks existing protected booking associations only, without freezing the whole day.
- The explicit-choice comparison now checks segment location (main vs the same alternative), kind (especially meal), selection and ref. Moving an explicit primary meal to an alternative or changing it to a non-meal requires the matching `remove` declaration even with the same ID/ref. Both required- and supplied-decision checks use the same classification helper; an authorized demotion succeeds.
- New regression tests actually swap two seeded days' distinct main cards, meal references and transfer modes/from-refs, with all four other days unchanged. A separate test confirms OnBird's breakfast/dinner can change without moving its protected main activity.
- Focused RED before SQL fix: `PYTHONPATH=tools/verify python3 -m unittest -v test_itinerary_update.UpdateTests.test_protected_booking_must_remain_on_main_route test_itinerary_update.UpdateTests.test_explicit_meal_demotion_to_alternative_or_non_meal_requires_decision test_itinerary_update.UpdateTests.test_two_day_activity_meal_transport_swap test_itinerary_update.UpdateTests.test_onbird_protects_activity_not_breakfast_or_evening` → `Ran 4 tests in 4.145s`, `FAILED (failures=2)` (both review bypasses accepted). After booking fix, `Ran 2 tests in 2.050s`, `FAILED (failures=1)` (only explicit bypass remained).
- Local PG18 migration reapplied via the guarded psycopg2 command above (`local migration applied`). Focused GREEN same 4-test command → `Ran 4 tests in 6.770s`, `OK`. Full A suite after the last SQL/test change: `python3 -m unittest discover -s tools/verify -p 'test_itinerary_*.py' -v` → `Ran 30 tests in 19.798s`, `OK`.
- Remaining concern unchanged: migration does not seed real production protected bookings/flight/lodging associations; those require A3 review and explicit content approval. No remote or production mutation.
