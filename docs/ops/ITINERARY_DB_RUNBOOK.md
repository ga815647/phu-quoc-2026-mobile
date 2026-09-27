# Itinerary 006: database candidate and release runbook

**Status:** local PG18 engineering verification only. Neither production migration nor
six-day initialization is authorized by this file. `006_itinerary_model.sql` is
additive and contains **no itinerary rows**. Synthetic `fixture-*` content belongs
only in an isolated test database, never in Neon or published JSON.

## Approval and evidence record

Maintain one record per target application (private release record, no credentials):

| Field | Required value |
| --- | --- |
| Migration path / SHA256 | `tools/migrate_neon/006_itinerary_model.sql` / output of `sha256sum tools/migrate_neon/006_itinerary_model.sql` |
| Target project / branch ID | Verify in Neon console immediately before use; write the actual **branch ID**, not just `production` |
| Approver / approved scope | Explicit authorization for this branch, migration, ACL and, separately, approved six-day content |
| Operator / role | Verify `session_user`, `current_user`, function owner and existing maintenance identity; no guessed GRANT |
| `applied_at` (UTC) | DB `clock_timestamp()` observed **after commit**, with commit/result noted |
| Test result | Local 33-test suite, isolated branch ACL/update/projection/schema rerun outcomes, counts/hash and date |
| Release and rollback | API/UI revision, public revision, six-day validation and separately authorized publication evidence |

Never record DSNs, tokens, private Notion details, or sample credentials in this
runbook, commits, CI logs or screenshots. The `phq_web_ro` role may SELECT only
`itinerary_public`'s three projected columns; `itinerary_payload(text)` needs
EXECUTE to service that view. It is fixed/read-only; no new raw itinerary table,
private version, request or audit grant is allowed. `itinerary_update` and edit
helpers are **not** web-role callable. Existing legacy source column allowlists
remain unchanged. Database owners can bypass an invoker-only procedure: Chat's
content rules still apply to maintenance identities.

## 1. Preflight (read-only against proposed target)

1. Get explicit approval for the **specified** isolated branch and the exact
   migration SHA256. Confirm target project `holy-fog-65935796`, actual target
   branch ID, PG18 and schema baseline 003–005; do not infer target from DSN
   labels. For production, obtain a **separate** explicit migration/ACL approval.
2. Verify role and owner using SQL `SELECT current_database(), current_user,
   session_user, current_setting('server_version');` and `SELECT
   pg_get_userbyid(proowner) FROM pg_proc WHERE oid =
   'public.content_update(text,text,text,text,integer,text,text,text)'::regprocedure;`.
   Compare with the approved maintainer; do not grant EXECUTE to a guessed role.
3. Capture counts and content/version hashes for existing source, food_pool and
   `content_revisions` before migration, plus grants on existing sources. Capture
   `sha256sum tools/migrate_neon/006_itinerary_model.sql` in the release record.
   No direct migration of the production branch is part of local testing.

## 2. Local and isolated-branch qualification

In this repository's **local** private-socket PG18 fixture only, run:

```sh
source /tmp/opencode/phq-pg18-test-env
python3 -m unittest discover -s tools/verify -p 'test_itinerary_acl.py' -v
python3 -m unittest discover -s tools/verify -p 'test_itinerary_*.py' -v
```

The ACL suite creates/drops its own additional *local* database, loads
`neon_schema_candidate.sql` + 003 + the **DDL and function only** of 004 + 005
(004's real food-pool seed is intentionally excluded), applies 006 without
initialization, then uses rollback-safe synthetic rows to verify a second 006
keeps full schema dump, table row counts/hashes and the public content hash.
It tests `SET LOCAL ROLE phq_web_ro` and actual permission-denied SQL. This
recreates full legacy **table shapes**, but cannot substitute for an isolated
Neon branch ACL check with its real legacy column grants, owner and data.

After local PASS, have the authorized operator repeat 006 in a **named isolated
Neon test branch** with a prepared, reviewed execution plan. Use transaction
wrapping (`psql -X -v ON_ERROR_STOP=1 -1 -f
tools/migrate_neon/006_itinerary_model.sql`) through their secure connection
mechanism; never print connection settings. In that branch only, verify zero
new itinerary rows immediately after 006, re-run 006, compare schema/ACL,
source counts/hashes and content revisions, and test the real web role's view
read plus denied raw/request/audit/version/update calls. Confirm maintenance
role can execute the invoker function without giving web role write privileges.
Failures block promotion; do not repair by broad GRANT.

## 3. Approved release and separate content initialization

Only after isolated results, review and **explicit production authorization**:

1. Confirm production branch ID `br-silent-haze-b3xw64tm` in Neon against the
   approved release record, plus current schema/counts/maintainer identity and
   migration SHA. Run the exact reviewed 006 as **one** fail-fast transaction
   (`psql -X -v ON_ERROR_STOP=1 -1 -f
   tools/migrate_neon/006_itinerary_model.sql`, using an operator-managed secure
   connection). No automatic seed, Function deployment or frontend switch.
2. Read back definition/ACL and counts; all three itinerary tables must still
   have zero rows. Log target branch ID, SHA256, UTC `applied_at`, operator,
   before/after schema and ACL result. If identity or ACL mismatches, stop.
3. **Separate approval gate:** obtain the accepted six-day timeline with
   evidence-backed meals, transfers, source dates and locked flight/lodging/
   10/11 OnBird constraints. An operator reviews a *separate* initialization
   script; never paste test fixtures or infer itinerary defaults from schema.
   In one transaction insert the fixed trip (`version=1`), six stable day IDs
   for 2026-10-10…15 (`version=1`) and reviewed `locked_constraints`, preserving
   confirmed booking references and only approved card choices. Validate all
   plans via `itinerary_validate_day` and require exactly one row for each
   date, a protected OnBird activity on 10/11, protected booking IDs all
   present and Confirmed, activity main-card segments aligned, and a successful
   six-day `itinerary_public` read/revision **before COMMIT**; on any mismatch
   ROLLBACK. Store the approved script and validation results in the private
   release evidence, not the migration. Initialization is not authorized by
   migration approval alone.
4. After separate API/export/frontend approvals, verify live production
   projection, offline JSON publication and phone/UI/CI results individually.
   Do not point formal Pages at the test branch. Chat's runtime capability
   validation is another outcome, not implied by local or DB tests.

## Failure and rollback

- An error in the atomic 006 transaction means **ROLLBACK**, investigate in the
  isolated branch and require a revised approved artifact; do not retry with a
  broad privilege grant. Re-running the identical 006 after a completed commit
  is safe only after comparing counts, hashes and grants.
- If API/frontend consumption fails after schema deployment, revert the **API
  and frontend read route** to the previous known-good version, retaining the
  previous fallback. Do **not** DROP populated tables, audit or requests and do
  not repoint production to SQLite/test Neon or overwrite live content with Git.
- If accepted six-day *content* must be restored, read the latest private
  versions/revision, submit a newly authorized `itinerary_update` with a new
  request ID and full affected days, check the returned receipt and audit, then
  re-export/publish via the normal approved flow. A Git revert is not a data
  restore; deletion/truncation of history is not a rollback.
