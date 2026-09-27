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
