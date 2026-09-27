"""Real PostgreSQL contract tests for the itinerary public projection."""
import copy
import hashlib
import json

import psycopg2

from itinerary_db_support import ItineraryDBCase


class ProjectionTests(ItineraryDBCase):
    def test_six_days_and_no_private_metadata(self):
        s = self.snapshot()
        self.assertEqual(len(s['payload']['days']), 6)
        self.assertRegex(s['revision'], r'^phq1:[0-9a-f]{64}$')
        self.assertEqual(s['payload']['schema_version'], 1)
        self.assertEqual(s['payload']['itinerary_id'], 'phuquoc-2026')
        self.assertEqual(s['payload']['days'][0]['id'], 'phuquoc-2026:2026-10-10')
        forbidden = {'version', 'locked_constraints', 'request_id', 'old_value', 'new_value'}

        def walk(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden.intersection(value))
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(s['payload'])
        self.assertEqual(s['revision'], 'phq1:' + hashlib.sha256(
            s['canonical'].encode('utf-8')).hexdigest())

    def test_refs_are_only_reachable_rows_and_whitelisted(self):
        refs = self.snapshot()['payload']['refs']
        self.assertEqual([x['slug'] for x in refs['cards']], ['onbird'])
        self.assertEqual([x['pool_key'] for x in refs['pool']], ['fixture-pool'])
        self.assertEqual([x['notion_id'] for x in refs['foods']], ['fixture-food'])
        self.assertEqual([x['slug'] for x in refs['bookings']], ['fixture-booking'])
        self.assertEqual([x['slug'] for x in refs['transport']], ['fixture-transport'])
        self.assertEqual([x['slug'] for x in refs['points']], ['fixture-point'])
        self.assertNotIn('detail', refs['bookings'][0])
        self.assertNotIn('evidence', refs['bookings'][0])
        self.assertNotIn('condition_note', refs['points'][0])
        self.assertNotIn('kid_plan', refs['foods'][0])

    def test_referenced_food_change_affects_revision_but_unrelated_does_not(self):
        old = self.snapshot()['revision']
        self.execute("UPDATE food_places SET hours_text='unrelated changed' WHERE notion_id='fixture-unrelated'")
        self.assertEqual(old, self.snapshot()['revision'])
        self.execute("UPDATE food_places SET hours_text='new hours' WHERE notion_id='fixture-food'")
        s = self.snapshot()
        self.assertNotEqual(old, s['revision'])
        self.assertEqual(s['payload']['refs']['foods'][0]['hours_text'], 'new hours')

    def test_every_referenced_source_category_affects_revision(self):
        for table, column, key, ident in (
            ('cards', 'route', 'slug', 'onbird'),
            ('points', 'durable_note', 'slug', 'fixture-point'),
            ('bookings', 'title', 'slug', 'fixture-booking'),
            ('transport_options', 'plan', 'slug', 'fixture-transport'),
            ('food_pool', 'desc_copy', 'pool_key', 'fixture-pool'),
        ):
            with self.subTest(table=table):
                old = self.snapshot()['revision']
                self.execute(f"UPDATE {table} SET {column}='fixture changed' WHERE {key}=%s", (ident,))
                self.assertNotEqual(old, self.snapshot()['revision'])

    def test_pool_reassignment_moves_indirect_food_dependency(self):
        self.execute("UPDATE food_pool SET notion_id='fixture-unrelated' WHERE pool_key='fixture-pool'")
        s = self.snapshot()
        self.assertEqual([f['notion_id'] for f in s['payload']['refs']['foods']], ['fixture-unrelated'])

    def test_private_changes_and_restore_do_not_change_content_identity(self):
        before = self.snapshot()
        self.execute("UPDATE itineraries SET version=version+1, updated_at=now() WHERE id='phuquoc-2026'")
        self.execute("UPDATE itinerary_days SET version=version+1, updated_at=now()")
        self.assertEqual(before['revision'], self.snapshot()['revision'])
        self.execute("UPDATE itinerary_days SET plan=jsonb_set(plan, '{public_note}', '\"changed\"'::jsonb) WHERE date='2026-10-10'")
        self.assertNotEqual(before['revision'], self.snapshot()['revision'])
        self.execute("UPDATE itinerary_days SET plan=plan-'public_note' WHERE date='2026-10-10'")
        self.assertEqual(before['revision'], self.snapshot()['revision'])

    def test_null_pool_food_is_legal(self):
        self.execute("UPDATE food_pool SET notion_id=NULL WHERE pool_key='fixture-pool'")
        self.assertEqual(self.snapshot()['payload']['refs']['foods'], [])

    def test_missing_source_fails_closed(self):
        self.execute("DELETE FROM points WHERE slug='fixture-point'")
        with self.assertRaises(psycopg2.Error) as raised:
            self.snapshot()
        self.assertEqual(raised.exception.pgcode, '22023')

    def test_validator_rejects_invalid_shapes_and_refs(self):
        original = self.scalar("SELECT jsonb_build_object('day_kind',day_kind,'main_card_slug',main_card_slug,'plan',plan) FROM itinerary_days WHERE date='2026-10-10'")
        bad_plans = []
        def changed(path, value):
            obj = copy.deepcopy(original)
            item = obj
            for key in path[:-1]:
                item = item[key]
            item[path[-1]] = value
            bad_plans.append(obj)
        changed(['plan', 'secret'], 'not public')
        changed(['plan', 'segments', 0, 'surprise'], 'x')
        changed(['plan', 'segments', 0, 'time', 'day_offset'], 2)
        changed(['plan', 'segments', 0, 'time', 'timezone'], 'Invalid/Zone')
        changed(['plan', 'segments', 0, 'time', 'duration_minutes'], {'min': -1, 'max': 5})
        changed(['plan', 'segments', 0, 'time', 'start_window'], {'min': '25:01', 'max': '26:00'})
        changed(['plan', 'segments', 0, 'ref'], {'type': 'card', 'id': 'missing-card'})
        changed(['plan', 'segments', 0, 'condition_refs'], ['unknown-condition'])
        changed(['plan', 'segments', 0, 'transfer'], {'mode': 'grab'})
        changed(['plan', 'segments', 0, 'id'], 'meal')
        changed(['plan', 'alternatives', 0, 'replacement_segments', 0, 'id'], 'meal')
        changed(['plan', 'alternatives', 0, 'replacement_segments', 0, 'alternatives'], [])
        for idx, obj in enumerate(bad_plans):
            with self.subTest(case=idx):
                self.execute('SAVEPOINT validation_case')
                try:
                    with self.assertRaises(psycopg2.Error) as raised:
                        self.execute('SELECT itinerary_validate_day(%s::jsonb)', (json.dumps(obj),))
                    self.assertEqual(raised.exception.pgcode, '22023')
                finally:
                    self.execute('ROLLBACK TO SAVEPOINT validation_case')

    def test_valid_day_and_private_edit_read(self):
        edit = self.scalar("SELECT itinerary_read_for_edit('phuquoc-2026')")
        self.assertEqual(edit['version'], 1)
        self.assertEqual(edit['content_revision'], self.snapshot()['revision'])
        self.assertEqual(len(edit['days']), 6)
        day = {k: v for k, v in edit['days'][0].items() if k != 'version'}
        self.execute('SELECT itinerary_validate_day(%s::jsonb)', (json.dumps(day),))

    def test_web_role_only_reads_public_view(self):
        self.execute('SAVEPOINT acl_check')
        try:
            self.execute('SET LOCAL ROLE phq_web_ro')
            self.assertEqual(len(self.scalar("SELECT payload->'days' FROM itinerary_public WHERE itinerary_id='phuquoc-2026'")), 6)
            self.execute('SAVEPOINT raw_access')
            try:
                with self.assertRaises(psycopg2.Error) as blocked:
                    self.execute('SELECT version FROM itinerary_days LIMIT 1')
                self.assertEqual(blocked.exception.pgcode, '42501')
            finally:
                self.execute('ROLLBACK TO SAVEPOINT raw_access')
            self.execute('SAVEPOINT edit_access')
            try:
                with self.assertRaises(psycopg2.Error) as blocked:
                    self.execute("SELECT itinerary_read_for_edit('phuquoc-2026')")
                self.assertEqual(blocked.exception.pgcode, '42501')
            finally:
                self.execute('ROLLBACK TO SAVEPOINT edit_access')
        finally:
            self.execute('ROLLBACK TO SAVEPOINT acl_check')

    def test_activity_requires_matching_card_segment(self):
        day = self.scalar("SELECT jsonb_build_object('day_kind',day_kind,'main_card_slug',main_card_slug,'plan',plan) FROM itinerary_days WHERE date='2026-10-11'")
        day['plan']['segments'] = []
        with self.assertRaises(psycopg2.Error) as raised:
            self.execute('SELECT itinerary_validate_day(%s::jsonb)', (json.dumps(day),))
        self.assertEqual(raised.exception.pgcode, '22023')

    def test_validator_rejects_large_day_and_non_string_conditions(self):
        day = self.scalar("SELECT jsonb_build_object('day_kind',day_kind,'main_card_slug',main_card_slug,'plan',plan) FROM itinerary_days WHERE date='2026-10-10'")
        day['plan']['public_note'] = 'x' * 131073
        self.execute('SAVEPOINT large_day')
        with self.assertRaises(psycopg2.Error) as raised:
            self.execute('SELECT itinerary_validate_day(%s::jsonb)', (json.dumps(day),))
        self.assertEqual(raised.exception.pgcode, '22023')
        self.execute('ROLLBACK TO SAVEPOINT large_day')
        day['plan'].pop('public_note')
        day['plan']['segments'][0]['condition_refs'] = [42]
        with self.assertRaises(psycopg2.Error) as raised:
            self.execute('SELECT itinerary_validate_day(%s::jsonb)', (json.dumps(day),))
        self.assertEqual(raised.exception.pgcode, '22023')
