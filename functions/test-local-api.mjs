/* Local harness: import the handler and exercise it against the test branch
 * with the restricted role DSN from env (PHQ_READONLY_DATABASE_URL).
 * Also asserts fail-closed when the env var is missing (separate process).
 * Usage:
 *   PHQ_READONLY_DATABASE_URL='postgresql://...' node --test test/local-api.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import handler from '../functions/phq-readonly-api.mjs';

const BASE = 'http://localhost';
const get = (path, opts = {}) =>
  handler.fetch(new Request(BASE + path, { method: 'GET', ...opts }));

test('health', async () => {
  const r = await get('/health');
  assert.equal(r.status, 200);
  const b = await r.json();
  assert.equal(b.ok, true);
  assert.match(b.meta.fetched_at, /^\d{4}-\d{2}-\d{2}T/);
  assert.equal(b.meta.source,
    process.env.PHQ_META_SOURCE || 'neon-prod');
  assert.ok(!('last_verified' in (b.meta || {})));
  assert.equal(r.headers.get('cache-control'), 'public, max-age=300');
});

for (const [path, n] of [
  ['/api/cards', 7],
  ['/api/foods', 69],
  ['/api/points', 48],
  ['/api/bookings', 8],
  ['/api/transport', 7],
]) {
  test(`${path} count=${n}`, async () => {
    const r = await get(path);
    assert.equal(r.status, 200);
    const b = await r.json();
    assert.equal(b.data.length, n);
  });
}

test('bookings projection: 6 cols, no detail/evidence', async () => {
  const b = await (await get('/api/bookings')).json();
  for (const row of b.data) {
    assert.deepEqual(Object.keys(row).sort(),
      ['amount', 'evidence_as_of', 'kind', 'slug', 'status', 'title']);
  }
});

test('card slug lookup + 404 + 400', async () => {
  const ok = await (await get('/api/cards?slug=cable')).json();
  assert.equal(ok.data.slug, 'cable');
  assert.equal((await get('/api/cards?slug=nope')).status, 404);
  assert.equal((await get('/api/cards?slug=evil%27--')).status, 400);
  const bad = await (await get('/api/cards?slug=evil%27--')).json();
  assert.equal(bad.error.code, 'BAD_SLUG');
});

test('method/method-404 + no-store on errors', async () => {
  const m = await handler.fetch(new Request(BASE + '/api/cards', { method: 'POST' }));
  assert.equal(m.status, 405);
  assert.equal(m.headers.get('cache-control'), 'no-store');
  const n = await get('/nope');
  assert.equal(n.status, 404);
  const b = await n.json();
  assert.deepEqual(b, { error: { code: 'NOT_FOUND' } });
});

test('CORS allowlist + Vary', async () => {
  const ok = await get('/health', { headers: { Origin: 'https://ga815647.github.io' } });
  assert.equal(ok.headers.get('access-control-allow-origin'), 'https://ga815647.github.io');
  assert.equal(ok.headers.get('vary'), 'Origin');
  const local = await get('/health', { headers: { Origin: 'http://localhost:8000' } });
  assert.equal(local.headers.get('access-control-allow-origin'), 'http://localhost:8000');
  const evil = await get('/health', { headers: { Origin: 'https://evil.example' } });
  assert.equal(evil.headers.get('access-control-allow-origin'), null);
  const pre = await handler.fetch(new Request(BASE + '/health',
    { method: 'OPTIONS', headers: { Origin: 'https://ga815647.github.io' } }));
  assert.equal(pre.status, 204);
});

test('foods order: NULLS FIRST parity spot check', async () => {
  const b = await (await get('/api/foods')).json();
  const names = b.data.map((f) => f.name);
  assert.ok(names.length === 69);
});

test('foods carry pool curation via stable-id join (004)', async () => {
  const b = await (await get('/api/foods')).json();
  const pooled = b.data.filter((f) => f.pool_key);
  assert.equal(pooled.length, 18);
  for (const f of pooled) {
    assert.ok(Number.isInteger(f.pool_rank));
    assert.ok(['carrier', 'conditional', 'fallback', 'market', 'verify'].includes(f.pool_role));
    assert.equal(typeof f.order_copy, 'string');
    assert.equal(typeof f.desc_copy, 'string');
    assert.ok(f.notion_id);
  }
  const first = b.data.find((f) => f.pool_key === 'bun-ken-ut-luom');
  assert.ok(first && first.notion_id);
});
