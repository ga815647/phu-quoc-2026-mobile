import unittest
import json
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from tools.itinerary_export import read_itinerary
from tools import export_json


REVISION = 'phq1:' + 'a' * 64
PAYLOAD = {
    'schema_version': 1,
    'itinerary_id': 'phuquoc-2026', 'start_date': '2026-10-10',
    'end_date': '2026-10-15', 'timezone': 'Asia/Ho_Chi_Minh',
    'days': [{'id': f'phuquoc-2026:2026-10-{d}', 'date': f'2026-10-{d}',
              'day_kind': 'free', 'main_card_slug': None, 'plan': {'segments': [], 'alternatives': []}}
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
