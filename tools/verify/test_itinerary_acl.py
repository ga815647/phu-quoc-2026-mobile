"""Local PG18 privilege and migration lifecycle checks; no remote connections."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import unittest
import uuid

import psycopg2
from psycopg2 import sql

from itinerary_db_support import ID, ItineraryDBCase, SEED, test_dsn


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / 'tools' / 'migrate_neon'
UPDATE_SIGNATURE = "public.itinerary_update(text,integer,text,uuid,jsonb,jsonb,text,text,text)"


class ACLTests(ItineraryDBCase):
    def denied(self, statement, params=()):
        self.execute('SAVEPOINT denied_access')
        try:
            with self.assertRaises(psycopg2.Error) as raised:
                self.execute(statement, params)
            self.assertEqual(raised.exception.pgcode, '42501', statement)
        finally:
            self.execute('ROLLBACK TO SAVEPOINT denied_access')
            self.execute('RELEASE SAVEPOINT denied_access')

    def test_reader_can_read_only_projection(self):
        self.execute('SET LOCAL ROLE phq_web_ro')
        self.assertEqual(self.scalar('SELECT count(*) FROM public.itinerary_public'), 1)
        self.assertEqual(len(self.scalar('SELECT payload->\'days\' FROM public.itinerary_public')), 6)
        self.assertRegex(self.scalar('SELECT content_revision FROM public.itinerary_public'), r'^phq1:[0-9a-f]{64}$')
        for table in ('itineraries', 'itinerary_days', 'itinerary_requests', 'content_revisions'):
            with self.subTest(table=table):
                self.assertFalse(self.scalar('SELECT has_table_privilege(current_user,%s,\'SELECT\')', (f'public.{table}',)))
                self.denied(f'SELECT * FROM public.{table} LIMIT 1')
        for table, column in (('itineraries', 'version'), ('itinerary_days', 'version'),
                              ('content_revisions', 'request_id')):
            with self.subTest(table=table, column=column):
                self.assertFalse(self.scalar('SELECT has_column_privilege(current_user,%s,%s,\'SELECT\')',
                                             (f'public.{table}', column)))
                self.denied(f'SELECT {column} FROM public.{table} LIMIT 1')
        self.denied("SELECT public.itinerary_read_for_edit('phuquoc-2026')")
        self.denied("SELECT public.itinerary_validate_day('{}'::jsonb)")
        self.denied("SELECT public.itinerary_starfish_route_ok('[]'::jsonb,'{}'::jsonb)")
        self.denied("SELECT public.itinerary_update('phuquoc-2026',1,'x',gen_random_uuid(),'[]'::jsonb,'[]'::jsonb,NULL,'test','test')")
        self.denied("UPDATE public.itinerary_days SET version=version+1 WHERE id='phuquoc-2026:2026-10-10'")

    def test_only_fixed_projection_helper_can_execute(self):
        self.execute('SET LOCAL ROLE phq_web_ro')
        self.assertTrue(self.scalar("SELECT has_function_privilege(current_user,'public.itinerary_payload(text)','EXECUTE')"))
        self.assertEqual(self.scalar("SELECT public.itinerary_payload('phuquoc-2026')"),
                         self.scalar('SELECT payload FROM public.itinerary_public'))
        self.assertIsNone(self.scalar("SELECT public.itinerary_payload('not-an-itinerary')"))
        for signature in (UPDATE_SIGNATURE, 'public.itinerary_read_for_edit(text)',
                           'public.itinerary_validate_day(jsonb)',
                           'public.itinerary_dependency_ids(text,jsonb)',
                           'public.itinerary_starfish_route_ok(jsonb,jsonb)'):
            with self.subTest(signature=signature):
                self.assertFalse(self.scalar('SELECT has_function_privilege(current_user,%s,\'EXECUTE\')',
                                             (signature,)))


class MigrationLifecycleTests(unittest.TestCase):
    """Build a fresh, separate local database from production-shaped DDL, no travel seeds."""

    def test_rerun_preserves_schema_and_synthetic_changes(self):
        base = psycopg2.extensions.parse_dsn(test_dsn())
        name = 'itinerary_a3_' + uuid.uuid4().hex[:16]
        admin = psycopg2.connect(**{**base, 'dbname': 'postgres'})
        if admin.server_version // 10000 != 18 or not admin.info.host.startswith('/tmp/opencode/'):
            admin.close()
            raise RuntimeError('Refusing nonlocal or non-PG18 database')
        admin.autocommit = True
        try:
            with admin.cursor() as cur:
                cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            try:
                self.check_database({**base, 'dbname': name})
            finally:
                with admin.cursor() as cur:
                    cur.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
        finally:
            admin.close()

    def check_database(self, params):
        db = psycopg2.connect(**params)
        try:
            with db.cursor() as cur:
                cur.execute((MIGRATIONS / 'neon_schema_candidate.sql').read_text())
                cur.execute((MIGRATIONS / '003_content_revisions.sql').read_text())
                # 004 mixes DDL with real production food-pool seeds. Use ONLY its
                # schema/function sections; never copy historical travel rows.
                legacy = (MIGRATIONS / '004_controlled_update.sql').read_text()
                pool_ddl = legacy.split('CREATE TABLE IF NOT EXISTS food_pool (', 1)[1].split('-- 種子資料：', 1)[0]
                cur.execute('CREATE TABLE IF NOT EXISTS food_pool (' + pool_ddl)
                function_ddl = legacy.split('CREATE OR REPLACE FUNCTION content_update(', 1)[1].split('-- ============ D.', 1)[0]
                cur.execute('CREATE OR REPLACE FUNCTION content_update(' + function_ddl)
                cur.execute('GRANT SELECT (pool_key' + legacy.split('GRANT SELECT (pool_key', 1)[1])
                cur.execute((MIGRATIONS / '005_restrict_content_update.sql').read_text())
                for table in ('food_pool', 'cards'):
                    cur.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(table)))
                    self.assertEqual(cur.fetchone()[0], 0, table)
                migration = (MIGRATIONS / '006_itinerary_model.sql').read_text()
                cur.execute(migration)
                for table in ('itineraries', 'itinerary_days', 'itinerary_requests'):
                    cur.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(table)))
                    self.assertEqual(cur.fetchone()[0], 0, table)
            db.commit()

            with db.cursor() as cur:
                cur.execute(SEED.read_text().split('-- TEST SEED (rollback fixture)')[1])
                cur.execute("SELECT version FROM public.itineraries WHERE id=%s", (ID,))
                base_version = cur.fetchone()[0]
                cur.execute('SELECT content_revision FROM public.itinerary_public WHERE itinerary_id=%s', (ID,))
                revision = cur.fetchone()[0]
                cur.execute("""SELECT jsonb_build_object('id',id,'date',date,'day_kind',day_kind,
                    'main_card_slug',main_card_slug,'plan',jsonb_set(plan,'{public_note}','"local fixture"'::jsonb))
                    FROM public.itinerary_days WHERE date='2026-10-12'""")
                candidate = cur.fetchone()[0]
                cur.execute('SELECT public.itinerary_update(%s,%s,%s,%s::uuid,%s::jsonb,%s::jsonb,%s,%s,%s)',
                            (ID, base_version, revision, str(uuid.uuid4()), json.dumps([candidate]),
                             '[]', None, 'local fixture', 'migration rerun'))
                self.assertEqual(cur.fetchone()[0]['resulting_version'], 2)
            db.commit()
            before_schema = self.schema_dump(params)
            before_data = self.data_fingerprint(db)
            with db.cursor() as cur:
                # Simulate an old accidental role grant: rerun must tighten it.
                cur.execute('GRANT EXECUTE ON FUNCTION ' + UPDATE_SIGNATURE + ' TO phq_web_ro')
                cur.execute('GRANT SELECT ON public.itinerary_requests TO phq_web_ro')
                cur.execute(migration)
                cur.execute("SELECT has_function_privilege('phq_web_ro',%s,'EXECUTE')", (UPDATE_SIGNATURE,))
                self.assertFalse(cur.fetchone()[0])
                cur.execute("SELECT has_table_privilege('phq_web_ro','public.itinerary_requests','SELECT')")
                self.assertFalse(cur.fetchone()[0])
            db.commit()
            self.assertEqual(self.schema_dump(params), before_schema)
            self.assertEqual(self.data_fingerprint(db), before_data)
        finally:
            db.close()

    def schema_dump(self, params):
        binary = Path('/tmp/opencode/phq-pg18/root/usr/lib/postgresql/18/bin/pg_dump')
        env = os.environ.copy()
        env['LD_LIBRARY_PATH'] = '/tmp/opencode/phq-pg18/root/usr/lib/x86_64-linux-gnu:' + env.get('LD_LIBRARY_PATH', '')
        dumped = subprocess.run([str(binary), '--schema-only', '--no-owner',
                                 f'--host={params["host"]}', f'--port={params["port"]}',
                                 f'--dbname={params["dbname"]}'],
                                capture_output=True, check=True, env=env).stdout
        # pg_dump 18 writes a new random psql restrict token on every invocation.
        return re.sub(rb'^\\(?:un)?restrict [A-Za-z0-9]+$', b'', dumped, flags=re.MULTILINE)

    def data_fingerprint(self, db):
        hashes = {}
        with db.cursor() as cur:
            for table in ('cards', 'food_places', 'food_pool', 'points', 'bookings',
                          'transport_options', 'content_revisions', 'itineraries',
                          'itinerary_days', 'itinerary_requests'):
                cur.execute(sql.SQL('SELECT to_jsonb(t)::text FROM public.{} t ORDER BY to_jsonb(t)::text')
                            .format(sql.Identifier(table)))
                rows = [row[0] for row in cur.fetchall()]
                hashes[table] = (len(rows), hashlib.sha256(json.dumps(rows).encode()).hexdigest())
            cur.execute('SELECT content_revision FROM public.itinerary_public WHERE itinerary_id=%s', (ID,))
            hashes['public_revision'] = cur.fetchone()[0]
        self.assertEqual(hashes['itinerary_requests'][0], 1)
        self.assertEqual(hashes['content_revisions'][0], 1)
        self.assertEqual(hashes['itinerary_days'][0], 6)
        return hashes
