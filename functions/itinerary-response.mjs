/* One fixed public projection, read in a single statement with its revision. */
const SQL = 'SELECT payload,content_revision FROM public.itinerary_public WHERE itinerary_id=$1';
const ID = 'phuquoc-2026';
const REVISION = /^phq1:[0-9a-f]{64}$/;

function valid(row) {
  const p = row?.payload;
  const trip = p?.itinerary;
  return p && typeof p === 'object' && !Array.isArray(p)
    && p.schema_version === 1 && trip && typeof trip === 'object' && !Array.isArray(trip)
    && trip.id === ID && trip.start_date === '2026-10-10' && trip.end_date === '2026-10-15'
    && trip.timezone === 'Asia/Ho_Chi_Minh'
    && Array.isArray(p.days) && p.days.length === 6
    && p.days.every((day, i) => day && day.date === `2026-10-${10 + i}`
      && day.id === `${ID}:${day.date}` && day.plan && typeof day.plan === 'object'
      && !Array.isArray(day.plan) && day.plan.schema_version === 1
      && Array.isArray(day.plan.segments) && Array.isArray(day.plan.alternatives))
    && p.refs && typeof p.refs === 'object' && !Array.isArray(p.refs)
    && Array.isArray(p.refs.bases)
    && REVISION.test(row.content_revision);
}

export async function itineraryResponse(query, meta, cors) {
  const headers = {'Content-Type': 'application/json; charset=utf-8', ...cors, 'Cache-Control': 'no-store'};
  try {
    const { rows } = await query(SQL, [ID]);
    if (!Array.isArray(rows) || rows.length !== 1 || !valid(rows[0])) {
      return new Response(JSON.stringify({error: {code: 'ITINERARY_UNAVAILABLE'}}), {status: 503, headers});
    }
    return new Response(JSON.stringify({data: rows[0].payload, meta: {
      ...meta, schema_version: 1, content_revision: rows[0].content_revision,
    }}), {status: 200, headers});
  } catch {
    return new Response(JSON.stringify({error: {code: 'UPSTREAM_DB'}}), {status: 502, headers});
  }
}
