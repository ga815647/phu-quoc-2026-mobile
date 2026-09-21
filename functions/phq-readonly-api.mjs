/* Phu Quoc 2026 — read-only API (Neon Functions, Node.js 24).
 *
 * Deployment selects the dataset via env:
 * - PHQ_META_SOURCE / PHQ_META_ENV default to 'neon-prod' / 'production'.
 *   Test branch deployments override both to 'neon-test' / 'candidate'.
 *   (Previously hardcoded test labels; fixed at production cutover.)
 *
 * Design (approved round 3, corrected):
 * - GET + OPTIONS only. Fixed endpoint table; no arbitrary table/SQL names.
 * - DB role: restricted LOGIN role via PHQ_READONLY_DATABASE_URL (secret).
 *   Missing env => fail closed. NEVER falls back to owner DATABASE_URL.
 * - Explicit column lists identical to the public projection contract
 *   (export_json.py default). No SELECT *.
 * - Row-level last_verified/evidence_as_of stay on each record; meta carries
 *   only fetched_at/source/environment (never a blended verification date).
 * - Errors are fixed strings; never leak SQL/DSN/stack.
 * - CORS: explicit allowlist + Vary: Origin. Errors use no-store.
 */
import pkg from 'pg';
const { Pool } = pkg;
import { attachDatabasePool } from '@neon/functions';

const DSN = process.env.PHQ_READONLY_DATABASE_URL;
if (!DSN) {
  throw new Error('PHQ_READONLY_DATABASE_URL is required (no owner fallback).');
}

const pool = new Pool({ connectionString: DSN, max: 3 });
attachDatabasePool(pool);

const API_ORIGIN = 'https://ga815647.github.io';
const LOCAL_ORIGINS = new Set(['http://localhost:8000', 'http://127.0.0.1:8000']);

function corsHeaders(origin) {
  let allow = null;
  if (origin === API_ORIGIN || LOCAL_ORIGINS.has(origin)) allow = origin;
  const h = {};
  if (allow) {
    h['Access-Control-Allow-Origin'] = allow;
    h['Vary'] = 'Origin';
  }
  h['Access-Control-Allow-Headers'] = 'content-type';
  h['Access-Control-Allow-Methods'] = 'GET, OPTIONS';
  return h;
}

const QUERIES = {
  cards: `SELECT slug,name,status,route,gates,transport,notes,summary,key_times,
    badges,stops,transport_out,transport_back,kid_note,dining,cut_order,callout,
    evidence_as_of FROM cards ORDER BY slug`,
  card_one: `SELECT slug,name,status,route,gates,transport,notes,summary,key_times,
    badges,stops,transport_out,transport_back,kid_note,dining,cut_order,callout,
    evidence_as_of FROM cards WHERE slug=$1`,
  foods: `SELECT notion_id,name,region,housing,cluster,time_slots,hours_text,
    maps_query,price_text,cuisine,worth,convenience,local_idx,pq_feature,kid_fit,
    grade,op_status,op_conf,atlas_state,data_conf,research_date,last_verified,
    evidence,neg_warn,summary,dish_ids,evidence_as_of FROM food_places
    ORDER BY CASE atlas_state WHEN 'ACTIVE' THEN 0 WHEN 'VERIFY' THEN 1 ELSE 2 END,
    grade NULLS FIRST, name`,
  points: `SELECT slug,name,area,interest,mandatory,trip_priority,condition_gate,
    returnability,play_mode,durable_note,status,evidence_as_of FROM points
    ORDER BY slug`,
  bookings: `SELECT slug,kind,title,amount,status,evidence_as_of FROM bookings
    ORDER BY kind, title`,
  transport: `SELECT slug,direction,plan,station,status,priority,note,evidence_as_of
    FROM transport_options ORDER BY slug`,
};

const SLUG_RE = /^[a-z0-9-]{1,40}$/;
const ROUTES = {
  '/health': 'health',
  '/api/cards': 'cards',
  '/api/foods': 'foods',
  '/api/points': 'points',
  '/api/bookings': 'bookings',
  '/api/transport': 'transport',
};

function json(body, status, extra) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...extra },
  });
}

export default {
  async fetch(request) {
    const cors = corsHeaders(request.headers.get('origin'));
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors });
    }
    if (request.method !== 'GET') {
      return json({ error: { code: 'METHOD_NOT_ALLOWED' } }, 405,
        { ...cors, 'Cache-Control': 'no-store' });
    }
    const url = new URL(request.url);
    const route = ROUTES[url.pathname];
    if (!route) {
      return json({ error: { code: 'NOT_FOUND' } }, 404,
        { ...cors, 'Cache-Control': 'no-store' });
    }
    const meta = () => ({
      fetched_at: new Date().toISOString(),
      source: process.env.PHQ_META_SOURCE || 'neon-prod',
      environment: process.env.PHQ_META_ENV || 'production',
    });
    const okHeaders = {
      ...cors,
      'Cache-Control': 'public, max-age=300',
    };
    try {
      if (route === 'health') {
        return json({ ok: true, meta: meta() }, 200, okHeaders);
      }
      if (route === 'cards' && url.searchParams.has('slug')) {
        const slug = url.searchParams.get('slug');
        if (!SLUG_RE.test(slug || '')) {
          return json({ error: { code: 'BAD_SLUG' } }, 400,
            { ...cors, 'Cache-Control': 'no-store' });
        }
        const { rows } = await pool.query(QUERIES.card_one, [slug]);
        if (!rows.length) {
          return json({ error: { code: 'NOT_FOUND' } }, 404,
            { ...cors, 'Cache-Control': 'no-store' });
        }
        return json({ data: rows[0], meta: meta() }, 200, okHeaders);
      }
      const { rows } = await pool.query(QUERIES[route]);
      return json({ data: rows, meta: meta() }, 200, okHeaders);
    } catch {
      return json({ error: { code: 'UPSTREAM_DB' } }, 502,
        { ...cors, 'Cache-Control': 'no-store' });
    }
  },
};
