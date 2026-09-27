import { test } from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import pg from 'pg';
import { itineraryResponse } from './itinerary-response.mjs';

const meta = { source: 'neon-test', environment: 'candidate', fetched_at: '2026-09-27T00:00:00Z' };
const revision = 'phq1:' + 'a'.repeat(64);
const payload = { schema_version: 1,
  itinerary_id: 'phuquoc-2026', start_date: '2026-10-10', end_date: '2026-10-15', timezone: 'Asia/Ho_Chi_Minh',
  days: Array.from({length: 6}, (_, i) => ({id: `phuquoc-2026:2026-10-${10 + i}`, date: `2026-10-${10 + i}`, day_kind: 'free', main_card_slug: null, plan: {segments: [], alternatives: []}})),
  refs: { cards: [], foods: [], pool: [], points: [], bases: [], bookings: [], transport: [] } };

test('fixed statement, parameter, shape, CORS and no-store on success', async () => {
  let called = 0;
  const response = await itineraryResponse(async (sql, params) => {
    called++;
    assert.match(sql, /^SELECT payload,content_revision FROM public\.itinerary_public WHERE itinerary_id=\$1$/);
    assert.deepEqual(params, ['phuquoc-2026']);
    return { rows: [{payload, content_revision: revision}] };
  }, meta, {'Access-Control-Allow-Origin': 'http://localhost:8000'});
  assert.equal(called, 1);
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.equal(response.headers.get('access-control-allow-origin'), 'http://localhost:8000');
  assert.deepEqual(await response.json(), {data: payload, meta: {...meta, schema_version: 1, content_revision: revision}});
});

test('missing or incomplete projection is unavailable, never successful empty itinerary', async () => {
  for (const rows of [[], [{payload: {...payload, days: payload.days.slice(0, 5)}, content_revision: revision}],
    [{payload: {...payload, days: payload.days.slice(0, 5).concat(payload.days[0])}, content_revision: revision}]]) {
    const response = await itineraryResponse(async () => ({rows}), meta, {});
    assert.equal(response.status, 503);
    assert.equal(response.headers.get('cache-control'), 'no-store');
    assert.deepEqual(await response.json(), {error: {code: 'ITINERARY_UNAVAILABLE'}});
  }
});

test('DB errors are fixed and not leaked', async () => {
  const response = await itineraryResponse(async () => {throw new Error('secret DSN');}, meta, {});
  assert.equal(response.status, 502);
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.deepEqual(await response.json(), {error: {code: 'UPSTREAM_DB'}});
});

test('isolated PG18 rollback fixture: actual view API and Python export share payload/revision',
  {skip: process.env.ITINERARY_TEST_ALLOW_WRITE !== '1'}, async () => {
    const dsn = process.env.ITINERARY_TEST_DSN || '';
    assert.match(dsn, /^host=\/tmp\/opencode\/phq-pg18\/socket port=55438 dbname=itinerary_test$/);
    const client = new pg.Client({host: '/tmp/opencode/phq-pg18/socket', port: 55438, database: 'itinerary_test'});
    await client.connect();
    try {
      const {rows: version} = await client.query('SHOW server_version_num');
      assert.equal(Math.floor(Number(version[0].server_version_num) / 10000), 18);
      await client.query('BEGIN');
      const seed = readFileSync(new URL('../tools/verify/fixtures/itinerary-test-seed.sql', import.meta.url), 'utf8');
      await client.query(seed.split('-- TEST SEED (rollback fixture)')[1]);
      const response = await itineraryResponse(client.query.bind(client), meta, {});
      assert.equal(response.status, 200);
      const api = await response.json();
      const exported = JSON.parse(execFileSync('python3', ['-c', `
import json,sys
from tools.itinerary_export import read_itinerary
row=json.load(sys.stdin)
print(json.dumps(read_itinerary(lambda sql: [row], 'neon-test', 'candidate', '2026-09-27T00:00:00Z')))
`], {input: JSON.stringify({payload: api.data, content_revision: api.meta.content_revision}), encoding: 'utf8'}));
      assert.deepEqual(api.data, exported.data);
      assert.equal(api.meta.content_revision, exported.meta.content_revision);
      assert.equal(api.data.days.length, 6);
    } finally {
      await client.query('ROLLBACK');
      await client.end();
    }
  });
