# Food Atlas display update — 2026-10-11

## Scope

State-aware presentation for existing itinerary meal references and associated
transfers, also applied to Today. VERIFY/unknown references are pending and
paused; DEACTIVATED references are excluded from recommendations. Original
labels, times, routes and booking records are retained. Superseded recommendation
notes remain available in a closed disclosure rather than competing with the
current status.

`last_verified` is shown as operating verification; `evidence_as_of` is source
review. Missing operating verification stays unknown. Long research/source text
is preserved using textContent in a closed native details disclosure; no raw
HTML is interpreted. The historic priority divider is rendered as a neutral
candidate heading. Empty group headings follow the existing filters. Stable
pool IDs/ranks and device-only `phq-v4-food-eaten` are unchanged.

## Public fallback provenance

Production read-only Function API (`neon-prod`, `production`) fetched
2026-10-11T16:53:50Z: foods 74, pool 20, cards 7, points 48, bookings 8,
transport 7, and the six-day public itinerary envelope. Carriers were read from
production using only the existing nine public columns. The existing exporter
was supplied those read-only results through an in-memory adapter; no database
credentials, database writes, schema changes or ETL changes were needed.

Public food columns follow export_json.py; API-only pool join fields were
removed from foods.json. Booking detail/evidence, row versions, audit tables,
locked constraints, and personal eaten history are absent. Unchanged cards,
points, bookings and transport retain their previous ordering.

Itinerary content revision:
`phq1:e643fb08830eb42ca05128044a952c0cb0415485a860c21db15428c0ebd16c01`.
Segments, alternatives, routes and time values match the production API; an
already-existing production public-note update is included in the fresh export.
The export timestamp does not alter the content revision.

## Verification

- Regression tests reproduced five reader issues and two generator issues before
  the fix, then passed.
- 32 local Node unit/contract tests and 3 Python food display tests pass.
- Generated HTML syntax, module syntax, Python compilation and git diff whitespace
  checks pass; generated pages come from the source generator, never hand-edited.
- Public-field and secret/private-history scan: passed.
- Local browser suite could not start Chromium because the execution environment
  disallows required sockets; the cloud browser blocks localhost. No restriction
  was bypassed. DB tests require the pre-existing isolated PG18 fixture, absent
  here; production was never used as a test database.
- The existing data-smoke workflow now includes field-specific date assertions
  plus live/API-failure mobile coverage at 320/390/430px, closed/expanded evidence,
  held meal references, filter headings and synthetic device-only eaten state.
  Deployment/runtime results must be checked for the exact release commit.
