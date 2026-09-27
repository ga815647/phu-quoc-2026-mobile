"""Rollback-only PG18 fixture harness. Never guesses or migrates a database."""
import os
import copy
import json
from pathlib import Path
import unittest
import uuid

import psycopg2

ENV_FILE = Path('/tmp/opencode/phq-pg18-test-env')
SEED = Path(__file__).parent / 'fixtures' / 'itinerary-test-seed.sql'
ID = 'phuquoc-2026'


def test_dsn():
    if not ENV_FILE.is_file():
        raise RuntimeError('Local PG18 test environment file missing; no database accessed')
    # The controller's file contains shell assignments. Only whitelisted local socket
    # variables are parsed; never execute a shell file or echo its secret contents.
    values = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith('export '):
            line = line[7:]
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            values[key] = value.strip().strip('"\'')
    if values.get('ITINERARY_TEST_ALLOW_WRITE') != '1':
        raise RuntimeError('Explicit isolated test write guard not enabled')
    dsn = values.get('ITINERARY_TEST_DSN')
    if not dsn or not psycopg2.extensions.parse_dsn(dsn).get('host', '').startswith('/tmp/opencode/'):
        raise RuntimeError('Expected an explicit local Unix-socket PG18 test DSN')
    return dsn


class ItineraryDBCase(unittest.TestCase):
    def setUp(self):
        self.db = psycopg2.connect(test_dsn())
        if self.db.server_version // 10000 != 18 or not self.db.info.host.startswith('/tmp/opencode/'):
            self.db.close()
            raise RuntimeError('Expected local PG18; refusing non-isolated database')
        self.db.autocommit = False
        try:
            with self.db.cursor() as cur:
                cur.execute('SELECT payload FROM public.itinerary_public LIMIT 0')
                cur.execute(SEED.read_text().split('-- TEST SEED (rollback fixture)')[1])
        except Exception:
            self.db.rollback()
            self.db.close()
            raise

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def execute(self, sql, params=()):
        with self.db.cursor() as cur:
            cur.execute(sql, params)

    def scalar(self, sql, params=()):
        with self.db.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()[0]

    def snapshot(self):
        with self.db.cursor() as cur:
            cur.execute("""SELECT payload, content_revision, payload::text,
                       (SELECT version FROM itineraries WHERE id=%s),
                       (SELECT count(*) FROM content_revisions WHERE target_table='itinerary_days'),
                       (SELECT count(*) FROM itinerary_requests WHERE itinerary_id=%s)
                       FROM itinerary_public WHERE itinerary_id=%s""", (ID, ID, ID))
            payload, revision, canonical, version, audit_count, request_count = cur.fetchone()
        return dict(payload=payload, revision=revision, canonical=canonical,
                    version=version, audit_count=audit_count, request_count=request_count)

    def candidate(self, day, card=None):
        original = next(d for d in self.snapshot()['payload']['days'] if d['date'] == day)
        result = copy.deepcopy(original)
        if card is not None:
            result['day_kind'] = 'activity'
            result['main_card_slug'] = card
            segments = result['plan']['segments']
            # Keep non-activity segments, including their meal/transfer assignments.
            segments[:] = [s for s in segments if s['kind'] != 'activity']
            template = copy.deepcopy(self.snapshot()['payload']['days'][1]['plan']['segments'][0])
            template['ref'] = {'type': 'card', 'id': card}
            template['id'] = 'main' if not any(s['id'] == 'main' for s in segments) else 'main-card'
            segments.insert(0, template)
        return result

    @staticmethod
    def new_request_id():
        return str(uuid.uuid4())

    def update(self, request_id, changes, base=None, revision=None, decisions=None,
               actor=None, source='fixture', reason='itinerary test'):
        if base is None or revision is None:
            current = self.snapshot()
            if base is None:
                base = current['version']
            if revision is None:
                revision = current['revision']
        return self.scalar('''SELECT public.itinerary_update(%s,%s,%s,%s::uuid,
            %s::jsonb,%s::jsonb,%s,%s,%s)''',
            (ID, base, revision, request_id, json.dumps(changes, ensure_ascii=False),
             json.dumps([] if decisions is None else decisions, ensure_ascii=False),
             actor, source, reason))
