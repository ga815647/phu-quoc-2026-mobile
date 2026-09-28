import unittest
import json
import builtins
import tempfile
import os
import subprocess
import uuid
from contextlib import closing, redirect_stdout
from io import StringIO
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from tools.itinerary_export import read_itinerary
from tools import export_json
from itinerary_db_support import SEED, test_dsn
import psycopg2
from psycopg2 import sql as pg_sql


REVISION = 'phq1:' + 'a' * 64
PAYLOAD = {
    'schema_version': 1,
    'itinerary': {'id': 'phuquoc-2026', 'start_date': '2026-10-10',
                  'end_date': '2026-10-15', 'timezone': 'Asia/Ho_Chi_Minh'},
    'days': [{'id': f'phuquoc-2026:2026-10-{d}', 'date': f'2026-10-{d}',
              'day_kind': 'light', 'main_card_slug': None, 'plan': {'schema_version': 1, 'segments': [], 'alternatives': []}}
             for d in range(10, 16)],
    'refs': {'cards': [], 'foods': [], 'pool': [], 'points': [],
             'bases': [], 'bookings': [], 'transport': []},
}


class ExportTests(unittest.TestCase):
    def test_missing_projection_fails_instead_of_old_snapshot(self):
        with self.assertRaisesRegex(ValueError, 'ITINERARY_UNAVAILABLE'):
            read_itinerary(lambda sql: [], 'neon-test', 'candidate', '2026-09-27T00:00:00Z')

    def test_same_wire_data_revision_and_export_time_outside_hash(self):
        def fetch(sql):
            self.assertIn("WHERE itinerary_id='phuquoc-2026'", sql)
            return [{'payload': PAYLOAD, 'content_revision': REVISION}]
        a = read_itinerary(fetch, 'neon-test', 'candidate', '2026-09-27T00:00:00Z')
        b = read_itinerary(fetch, 'neon-test', 'candidate', '2026-09-28T00:00:00Z')
        self.assertEqual(a['data'], PAYLOAD)
        self.assertEqual(a['meta']['content_revision'], REVISION)
        self.assertEqual(a['meta']['schema_version'], 1)
        self.assertEqual(a['meta']['source'], 'neon-test')
        self.assertEqual(a['meta']['environment'], 'candidate')
        self.assertEqual(a['meta']['content_revision'], b['meta']['content_revision'])
        self.assertNotEqual(a['meta']['exported_at'], b['meta']['exported_at'])

    def test_incomplete_or_invalid_revision_fails_closed(self):
        for payload, revision in [(dict(PAYLOAD, days=PAYLOAD['days'][:5]), REVISION),
                                  (PAYLOAD, 'bad')]:
            with self.subTest(revision=revision, day_count=len(payload['days'])):
                with self.assertRaisesRegex(ValueError, 'ITINERARY_UNAVAILABLE'):
                    read_itinerary(lambda sql: [{'payload': payload, 'content_revision': revision}],
                                   'neon-test', 'candidate', '2026-09-27T00:00:00Z')

    def test_malformed_plan_fails_closed(self):
        for plan in ({}, [], {'schema_version': 2, 'segments': [], 'alternatives': []},
                     {'schema_version': 1, 'segments': {}, 'alternatives': []},
                     {'schema_version': 1, 'segments': [], 'alternatives': {}}):
            payload = dict(PAYLOAD, days=[dict(PAYLOAD['days'][0], plan=plan), *PAYLOAD['days'][1:]])
            with self.subTest(plan=plan), self.assertRaisesRegex(ValueError, 'ITINERARY_UNAVAILABLE'):
                read_itinerary(lambda sql: [{'payload': payload, 'content_revision': REVISION}],
                               'neon-test', 'candidate', '2026-09-27T00:00:00Z')

    def test_missing_view_keeps_all_existing_files_unchanged(self):
        class DB:
            def close(self):
                pass
        with TemporaryDirectory() as output:
            existing = Path(output) / 'snapshot.json'
            existing.write_text('previous published snapshot', encoding='utf-8')
            itinerary = Path(output) / 'itinerary.json'
            itinerary.write_text('previous itinerary', encoding='utf-8')
            with patch.object(export_json, 'OUT', output), \
                 patch.object(export_json, 'SOURCE', 'neon'), \
                 patch.object(export_json, 'rows_neon', return_value=[]), \
                 patch.dict('os.environ', {'DATABASE_URL': 'injected-test-only'}), \
                 patch('psycopg2.connect', return_value=DB()):
                with self.assertRaisesRegex(ValueError, 'ITINERARY_UNAVAILABLE'):
                    export_json.main()
            self.assertEqual(existing.read_text(encoding='utf-8'), 'previous published snapshot')
            self.assertEqual(itinerary.read_text(encoding='utf-8'), 'previous itinerary')
            self.assertEqual(sorted(p.name for p in Path(output).iterdir()), ['itinerary.json', 'snapshot.json'])

    def test_export_writes_public_envelope_and_replaces_itinerary(self):
        class DB:
            def close(self):
                pass
        with TemporaryDirectory() as output:
            path = Path(output) / 'itinerary.json'
            path.write_text('outdated', encoding='utf-8')

            def fetch(db, sql):
                if 'public.itinerary_public' in sql:
                    return [{'payload': PAYLOAD, 'content_revision': REVISION}]
                return []

            with patch.object(export_json, 'OUT', output), \
                 patch.object(export_json, 'SOURCE', 'neon'), \
                 patch.object(export_json, 'rows_neon', side_effect=fetch), \
                 patch.dict('os.environ', {'DATABASE_URL': 'injected-test-only',
                                         'PHQ_META_SOURCE': 'neon-test', 'PHQ_META_ENV': 'candidate'}), \
                 patch('psycopg2.connect', return_value=DB()):
                export_json.main()
            written = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(written['data'], PAYLOAD)
            self.assertEqual(written['meta']['content_revision'], REVISION)
            self.assertEqual(written['meta']['source'], 'neon-test')
            self.assertEqual(written['meta']['environment'], 'candidate')
            self.assertEqual(written['meta']['fetched_at'], written['meta']['exported_at'])
            self.assertEqual(list(Path(output).glob('.itinerary-*.tmp')), [])

    def test_legacy_write_failure_after_staging_preserves_prior_itinerary(self):
        class DB:
            def close(self):
                pass
        with TemporaryDirectory() as output:
            path = Path(output) / 'itinerary.json'
            path.write_text('previous complete itinerary', encoding='utf-8')
            staged = []
            actual_tempfile = tempfile.NamedTemporaryFile
            actual_open = builtins.open

            def stage(*args, **kwargs):
                staged.append(True)
                return actual_tempfile(*args, **kwargs)

            def failing_open(file, mode='r', *args, **kwargs):
                if str(file).endswith('/snapshot.json') and 'w' in mode:
                    self.assertTrue(staged, 'itinerary must be staged before legacy outputs')
                    raise OSError('injected legacy snapshot write failure')
                return actual_open(file, mode, *args, **kwargs)

            def fetch(db, sql):
                return [{'payload': PAYLOAD, 'content_revision': REVISION}] if 'public.itinerary_public' in sql else []

            with patch.object(export_json, 'OUT', output), \
                 patch.object(export_json, 'SOURCE', 'neon'), \
                 patch.object(export_json, 'rows_neon', side_effect=fetch), \
                 patch.dict('os.environ', {'DATABASE_URL': 'injected-test-only'}), \
                 patch('psycopg2.connect', return_value=DB()), \
                 patch.object(export_json.tempfile, 'NamedTemporaryFile', side_effect=stage), \
                 patch.object(builtins, 'open', side_effect=failing_open):
                with self.assertRaisesRegex(OSError, 'injected legacy'):
                    export_json.main()
            self.assertEqual(path.read_text(encoding='utf-8'), 'previous complete itinerary')
            self.assertEqual(list(Path(output).glob('.itinerary-*.tmp')), [])

    def test_committed_local_pg18_node_python_and_cli_export_parity(self):
        # A dedicated disposable local DB makes the same committed row visible
        # to three independent connections; never pass the Node result to Python.
        base = psycopg2.extensions.parse_dsn(test_dsn())
        name = 'itinerary_b1_' + uuid.uuid4().hex[:16]
        admin = psycopg2.connect(**{**base, 'dbname': 'postgres'})
        if admin.server_version // 10000 != 18 or not admin.info.host.startswith('/tmp/opencode/'):
            admin.close()
            raise RuntimeError('refusing non-local PG18 fixture')
        admin.autocommit = True
        try:
            with admin.cursor() as cur:
                cur.execute(pg_sql.SQL('CREATE DATABASE {}').format(pg_sql.Identifier(name)))
            try:
                scratch = {**base, 'dbname': name}
                dsn = psycopg2.extensions.make_dsn(**scratch)
                with closing(psycopg2.connect(dsn)) as db:
                    with db.cursor() as cur:
                        prelude, seed = SEED.read_text().split('-- TEST SEED (rollback fixture)')
                        cur.execute(prelude)
                        migration = Path('tools/migrate_neon/006_itinerary_model.sql').read_text()
                        cur.execute(migration)
                        # Only the old exporter needs this otherwise-empty legacy relation.
                        cur.execute('''CREATE TABLE dish_carriers (
                            title text, dish_id text, place_id text, role text, status text,
                            scope text, food_conf text, evidence_as_of text, accepted_at text)''')
                        cur.execute(seed)
                    db.commit()
                # Python reads directly from the view, independently of Node.
                with closing(psycopg2.connect(dsn)) as db:
                    python = read_itinerary(lambda query: export_json.rows_neon(db, query),
                                            'neon-test', 'candidate', '2026-09-27T00:00:00Z')

                script = '''
import pg from './functions/node_modules/pg/lib/index.js';
import {itineraryResponse} from './functions/itinerary-response.mjs';
const client = new pg.Client({host: process.env.PGHOST,
  port: Number(process.env.PGPORT), database: process.env.PGDATABASE});
await client.connect();
try {
  const r = await itineraryResponse(client.query.bind(client),
    {source:'neon-test', environment:'candidate', fetched_at:'2026-09-27T00:00:00Z'}, {});
  if (r.status !== 200) throw new Error(`unexpected HTTP ${r.status}`);
  console.log(await r.text());
} finally { await client.end(); }
'''
                env = {**os.environ, 'PGHOST': scratch['host'],
                       'PGPORT': str(scratch['port']), 'PGDATABASE': name}
                node = subprocess.run(['node', '--input-type=module', '-e', script],
                                      cwd=Path(__file__).resolve().parents[2], env=env,
                                      capture_output=True, text=True, check=True)
                api = json.loads(node.stdout)
                self.assertEqual(api['data'], python['data'])
                self.assertEqual(api['meta'], {key: value for key, value in python['meta'].items()
                                               if key != 'exported_at'})
                self.assertEqual(api['data']['refs']['bases'], [
                    {'id': 'hotel', 'ref': {'type': 'booking', 'id': 'fixture-booking'}}])
                with TemporaryDirectory() as out:
                    with patch.object(export_json, 'OUT', out), \
                         patch.object(export_json, 'SOURCE', 'neon'), \
                         patch.dict(os.environ, {'DATABASE_URL': dsn,
                                                'PHQ_META_SOURCE': 'neon-test', 'PHQ_META_ENV': 'candidate'}), \
                         redirect_stdout(StringIO()):
                        export_json.main()
                    fallback = json.loads((Path(out) / 'itinerary.json').read_text(encoding='utf-8'))
                    self.assertEqual(fallback['data'], api['data'])
                    self.assertEqual(fallback['meta']['content_revision'], api['meta']['content_revision'])
                    self.assertEqual(fallback['meta']['source'], api['meta']['source'])
                    self.assertIn('exported_at', fallback['meta'])
            finally:
                with admin.cursor() as cur:
                    cur.execute(pg_sql.SQL('DROP DATABASE {}').format(pg_sql.Identifier(name)))
        finally:
            admin.close()
