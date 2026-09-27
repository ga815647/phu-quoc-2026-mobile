# Task A1 report — 2026-09-27

## Outcome

- Added additive `006_itinerary_model.sql`: three private itinerary/request tables, nullable indexed audit `request_id`, fixed `itinerary_public` view, deterministic SHA-256 `phq1:` identity, owner-backed public projection, invoker-only private edit read, and validator with fixed SQLSTATE `22023` error.
- The projection uses explicitly listed source columns, referenced rows only, stable sorting, pool→food expansion (NULL food allowed), and booking/transport dependencies from locked constraints. It returns no private versions, audit rows, request IDs, booking detail/evidence, or point condition_note.
- Validator rejects unknown nested keys, invalid day IDs/dates, malformed refs/times/zones/ranges, negative minutes, invalid condition/alternative links, duplicate segment IDs, nested alternatives, activity without its main-card segment, overlong candidate days, and malformed transfer shapes.
- Added local-PG18, socket-guarded, rollback-per-test harness and synthetic source/itinerary fixture; no historical 004 content seed used. Fixture prelude initializes minimal source structures and local read role before migration; migration is applied manually to the isolated DB, never implicitly by the harness.

## Exact RED / GREEN evidence

- RED: `python3 -m unittest discover -s tools/verify -p test_itinerary_projection.py -v` → `Ran 9 tests in 0.037s`, `FAILED (errors=9)`; all failed because `relation "public.itinerary_public" does not exist`, not due to DSN/dependency.
- Additional RED: after migration, `test_activity_requires_matching_card_segment` and `test_validator_rejects_large_day_and_non_string_conditions` failed with `AssertionError: Error not raised`; then added the guards.
- GREEN: same target command → `Ran 13 tests in 2.322s`, `OK` on local PostgreSQL 18; actual `phq_web_ro` role could read public view but not raw version/private read function. An intermediate run after the first correction had `Ran 12 tests in 1.453s`, `OK`.
- Wider `python3 -m unittest discover -s tools/verify -v` → `Ran 13 tests in 2.232s`, `OK`; root `python3 -m unittest discover -v` → `Ran 0 tests`, `NO TESTS RAN` (exit 5; repository does not expose tests to root discovery). No unrelated suite was observed failing.

## Boundaries / concerns for controller

- This is local synthetic-schema PG18 validation, **not** a Neon test-branch or production migration and not actual trip content. Test schema mirrors relevant columns of existing schema plus 003/004, not the full historical 004 dataset. Controller should verify migration and ACL against the full isolated production-shaped schema before any remote application.
- `itinerary_validate_day` accepts either a full public day (id/date optional in candidate) or day-kind/main-card/plan; Task B's update procedure must enforce immutable day ID/date against stored values, locked constraints, complete six-day invariants, the whole request's 128 KiB limit, and actor permissions. This task does not introduce an update function.
- `source_refs` has an array-of-strings contract here because the approved schema does not specify source-ref object shape/registry. It does not assert the truth/privacy of free-form public copy or source citations. If Task B needs structured references, decide jointly before promising validated citations.
- Public view materializes its payload CTE so digest and payload use a single evaluation/snapshot. Function security/owner/role grants were exercised locally with a no-login `phq_web_ro`, not against Neon's existing role hierarchy.
- Other concurrent/untracked working tree paths (`docs/ops/REDESIGN_SCOPE.md`, the implementation plan, `node_modules`) were not staged, edited, or removed by this task.

## Review round 1/5 — three Important findings fixed

- **Fixed trip at schema level:** named `CHECK` constraints on `itineraries` require `phuquoc-2026`, 2026-10-10…15, `Asia/Ho_Chi_Minh`; named `CHECK` on `itinerary_days` requires the same itinerary ID and each date within that range (existing day-ID/date check still applies). The additive `DO` block adds both checks to an already-installed 006 schema when rerun; it does not silently accept an incompatible existing row. Test checks failed writes leave the valid view readable.
- **Only used bases contribute dependencies:** collect `base` refs in main/replacement segment refs and transfer endpoints, then resolve only those keys through `locked_constraints.bases` into booking/point rows. Explicit protected `locked_constraints.bookings` are still included independently. Regression proves inserting unused approved booking/point bases, then changing their public source rows, preserves payload and revision; using one in a transfer includes its booking.
- **No recursive alternative links:** condition validation now tracks whether the segment belongs to the main line or a replacement. Replacement segment and replacement transfer `condition_refs` cannot target any day alternative ID (own or another); main-line alternative condition refs remain legal and approved card gate refs retain their existing behavior.

### Exact local PG18 commands and results

1. RED, before changes, using the local socket guard in `/tmp/opencode/phq-pg18-test-env` (the harness reads it without printing values):

   `PYTHONPATH=tools/verify python3 -m unittest -v test_itinerary_projection.ProjectionTests.test_schema_rejects_other_trip_dates_and_timezone_without_poisoning_view test_itinerary_projection.ProjectionTests.test_only_referenced_bases_contribute_to_public_refs_and_revision test_itinerary_projection.ProjectionTests.test_replacement_conditions_cannot_activate_self_or_other_alternative test_itinerary_projection.ProjectionTests.test_replacement_transfer_conditions_cannot_activate_alternatives`

   Output: `Ran 4 tests in 0.513s` / `FAILED (failures=9)` — five schema writes, unused-base hash, self/cross replacement refs, and replacement transfer ref all failed with `AssertionError: Error not raised` / revision mismatch. A preceding exploratory RED (`Ran 3 tests in 0.500s`, `FAILED (failures=8, errors=1)`) exposed a misplaced test savepoint block; corrected the test structure and reran the clean RED above before changing implementation.

2. Applied the revised `tools/migrate_neon/006_itinerary_model.sql` in a guarded psycopg2 transaction to **only** the local Unix-socket PostgreSQL 18 instance (checked both server version and socket host before SQL). Output: `local PG18: 006 applied (including existing-table constraints)`.

3. GREEN, the same four-test command: `Ran 4 tests in 1.313s` / `OK`.

4. A1 suite once after the focused green: `python3 -m unittest discover -s tools/verify -p test_itinerary_projection.py -v` → `Ran 17 tests in 3.208s` / `OK`.

No remote DB, GitHub, deployment, or production mutation. A2's update procedure remains out of scope; it still must enforce immutability and atomic update invariants. The earlier synthetic-schema/production-shaped-schema limitation remains.
