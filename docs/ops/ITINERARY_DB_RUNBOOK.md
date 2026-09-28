# Itinerary 006: database candidate and release runbook

**Status (2026-09-28):** authorized isolated Neon qualification and production 006 /
six-day initialization completed; evidence and subsequent site/Chat gates are in
`ITINERARY_RELEASE_20260928.md`. This runbook does not authorize later reinitialization.
The operator must verify target, artifact and stage authorization before execution.
`006_itinerary_model.sql` is
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
| Test result | Current local itinerary suite (51 tests at this follow-up), isolated branch ACL/update/projection/schema rerun outcomes, counts/hash and date |
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
    labels. Production is a separate gated operation under the scoped approval;
    record the release-specific target and reviewed artifact before applying it.
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

Only after isolated results, review and confirmation of the **scoped production authorization**:

1. Confirm production branch ID `br-silent-haze-b3xw64tm` in Neon against the
   approved release record, plus current schema/counts/maintainer identity and
   migration SHA. Run the exact reviewed 006 as **one** fail-fast transaction
   (`psql -X -v ON_ERROR_STOP=1 -1 -f
   tools/migrate_neon/006_itinerary_model.sql`, using an operator-managed secure
   connection). No automatic seed, Function deployment or frontend switch.
2. Read back definition/ACL and counts; all three itinerary tables must still
   have zero rows. Log target branch ID, SHA256, UTC `applied_at`, operator,
   before/after schema and ACL result. If identity or ACL mismatches, stop.
  3. **Separate content review gate:** obtain the accepted six-day timeline with
    honestly unknown meals, transfers or times where evidence is unavailable,
    source dates where known, and locked flight/lodging/
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
    The initialization review must fill these **exact private lock keys** from
    the accepted timeline, not from this runbook or a sample fixture:

    For every day kind, a non-null `main_card_slug` must have a matching
    operative main-route `activity` segment referencing that card. This does
    not forbid `light` days: they may remain without a main card or contain
    an actual main activity. `activity` days still require a main card.

     - `locked_constraints.onbird_core` has **one of two exact key shapes**.
       Both contain `date:"2026-10-11"`, `segment_id` (reviewed operative
       main-route activity ID), `kind:"activity"`,
       `ref:{"type":"card","id":"onbird"}`, `day_offset:0`,
       `timezone:"Asia/Ho_Chi_Minh"`, `time_kind`, `start_window`,
       `duration_minutes`. The legacy fully concrete form has **no** `period`,
       `time_kind:"scheduled"`, a non-null reviewed local clock interval
       `start_window:{"min":"HH:mm","max":"HH:mm"}`, and a reviewed numeric
       duration interval or null. For the approved fixed Morning activity with
       **unknown exact time**, add `period:"morning"`, set `time_kind:"unknown"`,
       `start_window:null`, `duration_minutes:null`. Example private lock shape
       (not an activity time or content seed):

       ```json
       {"date":"2026-10-11","segment_id":"<reviewed-main-id>","kind":"activity",
        "ref":{"type":"card","id":"onbird"},"period":"morning",
        "time_kind":"unknown","start_window":null,"day_offset":0,
        "timezone":"Asia/Ho_Chi_Minh","duration_minutes":null}
       ```

       The initial 10/11 main-route segment must match the lock's ID/kind/ref,
       timezone/day offset and unknown time (with its own valid public time
       fields). No fabricated start window: Morning is a classification, not
       a confirmed start value. Missing/malformed core blocks *all* ordinary
       edits; moving, renaming, demoting or changing the OnBird reference blocks
       10/11. Breakfast, evening and separately represented operator pickup
       transfer are not this protected activity; pickup remains editable with
       its own evidence under normal plan rules.

       A controlled `itinerary_update` may complete the pending activity with
       `kind:"scheduled"`, a source-backed local interval entirely before 12:00
       (`max` strictly less than `12:00`), nonempty `source_refs` and a valid
       `evidence_as_of` calendar date. A null duration may be filled at that time
       or later with evidence. The serialized persisted segment is compared under
       the itinerary row lock: once a window or duration is filled, ordinary
       updates cannot change/clear it; unrelated notes, meals and evening plans
       remain editable. The private initialization metadata is not rewritten.
       **First factual completion is not approval to reschedule**: correcting a
       filled value requires separate authorization and reviewed exceptional
       procedure outside the ordinary Chat entry. Do not copy synthetic fixture
       times into initialization or imply a concrete time from booking pickup.
    - `locked_constraints.starfish` is an object with exactly `conditions`
      (at least two reviewed machine keys including `return`, each mapped to
      the **exact visible public text already in** `cards.gates` for Starfish)
      and `return_base` (an existing approved `bases` key, booking/point).
      Review the actual card's gates and returnability before assigning keys;
      if its prose is insufficient, seek content approval rather than invent
      facts or put private lock data into the public site. This mapping is
      projected only as `refs.cards[].condition_labels` for Starfish so the
      reader can display the existing card text for each key. A card-gate
      text change that breaks the mapping blocks a Starfish edit. The
      Every executable Starfish route—main segments or a flat
      `use_alternative.replacement_segments` route that references Starfish—
      must contain a Starfish activity carrying **all** condition keys. Its
      first outbound transfer from Starfish in that *same route* must follow
      the activity, point directly to `return_base`, use `charter` or
      `operator_pickup`, and carry `return` as a transfer condition. A segment
      from another route cannot satisfy the return. Every segment/transfer
      condition key is valid only against card refs on that individual
      segment/transfer; an unrelated meal cannot borrow a Starfish gate from
      elsewhere on the day. Alternatives remain flat (no nested alternatives).
      Missing/malformed settings forbid selecting Starfish; default Vin/cable/
      Safari days do not require Starfish configuration.

    These private keys are created in the separately approved initialization
    INSERT, not in 006 or `itinerary_update`. The update function never writes
    them; the web role cannot edit or read the raw lock. A DB owner can still
    bypass invoker/ACL protections, so any later exceptional lock correction
    requires separate review, not an ordinary Chat edit. Verify before commit
    that the public projection/reader accepts the complete six days.
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
