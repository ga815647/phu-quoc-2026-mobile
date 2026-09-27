"""Atomic update contract on the isolated PG18 socket database."""
import copy
import json
import subprocess
import threading
import time
import unittest
import uuid

import psycopg2

from itinerary_db_support import ID, ItineraryDBCase, SEED, test_dsn


class UpdateTests(ItineraryDBCase):
    def setUp(self):
        super().setUp()
        self.execute("INSERT INTO cards(slug,name) VALUES ('cable','Fixture cable')")

    def failure(self, code, changes, **kwargs):
        before = self.snapshot()
        message = kwargs.pop('message', None)
        request_id = kwargs.pop('request_id', self.new_request_id())
        self.execute('SAVEPOINT attempted_update')
        try:
            with self.assertRaises(psycopg2.Error) as raised:
                self.update(request_id, changes, **kwargs)
            self.assertEqual(raised.exception.pgcode, code)
            if message is not None:
                self.assertEqual(raised.exception.diag.message_primary, message)
        finally:
            self.execute('ROLLBACK TO SAVEPOINT attempted_update')
            self.execute('RELEASE SAVEPOINT attempted_update')
        self.assertEqual(before, self.snapshot())

    def test_main_card_and_meals_must_be_renderable_without_receipt(self):
        self.execute("INSERT INTO cards(slug,name,status) VALUES ('khem','Retired','RETIRED'),('safari','Inactive','RETIRED')")
        for slug in ('khem','safari'):
            with self.subTest(slug=slug):
                self.failure('22023', [self.candidate('2026-10-12', slug)], message='INVALID_PLAN')
        self.execute("UPDATE cards SET status='OPTIONAL' WHERE slug='safari'")
        self.failure('22023', [self.candidate('2026-10-12', 'safari')], message='INVALID_PLAN')
        for target in ('main','replacement'):
            with self.subTest(target=target):
                day=self.candidate('2026-10-10')
                meal=day['plan']['segments'][1]
                if target=='replacement':
                    meal=copy.deepcopy(meal)
                    meal['id']='bad-meal'
                    day['plan']['alternatives'][0]['replacement_segments'].append(meal)
                meal['ref']={'type':'card','id':'onbird'}
                self.failure('22023', [day], message='INVALID_PLAN')

    def test_onbird_core_is_protected_but_meals_are_not(self):
        for mutation in ('night', 'demote', 'rename', 'remove'):
            day=self.candidate('2026-10-11')
            segment=day['plan']['segments'][0]
            if mutation=='night':segment['time']['start_window']={'min':'22:00','max':'23:00'}
            if mutation=='demote':segment['kind']='optional'
            if mutation=='rename':segment['id']='other'
            if mutation=='remove':day['plan']['segments']=[]
            self.failure('22023',[day],message='LOCKED_ARRANGEMENT' if mutation=='night' or mutation=='rename' else 'INVALID_PLAN')
        day=self.candidate('2026-10-11')
        day['plan']['segments'].append(copy.deepcopy(self.candidate('2026-10-10')['plan']['segments'][1]))
        self.update(self.new_request_id(),[day])
        self.assertEqual(len(self.snapshot()['payload']['days'][1]['plan']['segments']),2)

    def test_missing_or_malformed_onbird_core_blocks_edits(self):
        for core in (None,{}, {'segment_id':'main'}):
            self.execute('SAVEPOINT core_case')
            try:
                if core is None:
                    self.execute("UPDATE itineraries SET locked_constraints=locked_constraints-'onbird_core'")
                else:
                    self.execute("UPDATE itineraries SET locked_constraints=jsonb_set(locked_constraints,'{onbird_core}',%s::jsonb)",(json.dumps(core),))
                self.failure('22023',[self.candidate('2026-10-12')],message='LOCKED_ARRANGEMENT')
            finally:
                self.execute('ROLLBACK TO SAVEPOINT core_case')

    def test_starfish_requires_reviewed_gate_and_real_return(self):
        self.execute('INSERT INTO cards(slug,name,gates) VALUES (%s,%s,%s)',('starfish','Starfish',json.dumps(['Weather and boat checked','Return charter arranged'])))
        day=self.candidate('2026-10-12','starfish')
        self.failure('22023',[day],message='LOCKED_ARRANGEMENT')
        self.execute('''UPDATE itineraries SET locked_constraints=jsonb_set(locked_constraints,'{starfish}',%s::jsonb)''',
          (json.dumps({'conditions':{'weather':'Weather and boat checked','return':'Return charter arranged'},
                       'return_base':'hotel'}),))
        self.execute('SAVEPOINT malformed_starfish')
        self.execute('''UPDATE itineraries SET locked_constraints=jsonb_set(locked_constraints,'{starfish,conditions,return}','42'::jsonb)''')
        self.failure('22023',[day],message='LOCKED_ARRANGEMENT')
        self.execute('ROLLBACK TO SAVEPOINT malformed_starfish')
        self.failure('22023',[day],message='LOCKED_ARRANGEMENT')
        activity=day['plan']['segments'][0]
        activity['condition_refs']=['weather','return']
        self.failure('22023',[day],message='LOCKED_ARRANGEMENT')
        tr=copy.deepcopy(self.candidate('2026-10-10')['plan']['segments'][2]);tr['id']='return'
        tr['transfer'].update(from_ref={'type':'card','id':'starfish'},mode='grab',condition_refs=['return'])
        day['plan']['segments'].append(tr)
        self.failure('22023',[day],message='LOCKED_ARRANGEMENT')
        tr['transfer']['mode']='charter'
        tr['transfer']['from_ref']={'type':'point','id':'fixture-point'}
        self.failure('22023',[day],message='LOCKED_ARRANGEMENT')
        tr['transfer']['from_ref']={'type':'card','id':'starfish'}
        receipt=self.update(self.new_request_id(),[day])
        self.assertEqual(receipt['content_revision'],self.snapshot()['revision'])
        self.assert_projection_readable()
        removed=copy.deepcopy(day);removed['plan']['segments'][0]['condition_refs'].remove('return')
        self.failure('22023',[removed],message='LOCKED_ARRANGEMENT')
        disguised=copy.deepcopy(day)
        outbound=copy.deepcopy(tr);outbound['id']='grab-first';outbound['transfer']['mode']='grab'
        disguised['plan']['segments'].insert(1,outbound)
        self.failure('22023',[disguised],message='LOCKED_ARRANGEMENT')
        self.execute("UPDATE cards SET gates='[\"Weather and boat checked\"]' WHERE slug='starfish'")
        self.failure('22023',[day],message='LOCKED_ARRANGEMENT')

    def assert_projection_readable(self):
        state=self.snapshot()
        envelope={'data':state['payload'],'meta':{'schema_version':1,'content_revision':state['revision'],
           'source':'neon-prod','environment':'production','fetched_at':'2026-09-27T00:00:00Z'}}
        result=subprocess.run(['node','--input-type=module','-e',
          "import {validateEnvelope} from './tools/itinerary-reader.mjs'; let text=''; for await (const chunk of process.stdin) text+=chunk; validateEnvelope(JSON.parse(text));"],
          input=json.dumps(envelope),text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_accepted_projection_passes_public_reader(self):
        self.assert_projection_readable()
        self.update(self.new_request_id(),[self.candidate('2026-10-12','cable')])
        self.assert_projection_readable()

    def test_retry_returns_receipt_without_extra_audit(self):
        before = self.snapshot()
        request = self.new_request_id()
        changes = [self.candidate('2026-10-12', 'cable')]
        first = self.update(request, changes, before['version'], before['revision'])
        after = self.snapshot()
        second = self.update(request, changes, before['version'], before['revision'])
        self.assertEqual(first, second)
        self.assertEqual(after, self.snapshot())
        self.assertEqual(after['audit_count'], before['audit_count'] + 1)
        self.assertEqual(after['request_count'], before['request_count'] + 1)
        self.assertEqual(first['changed_day_ids'], [changes[0]['id']])
        self.assertEqual(first['content_revision'], after['revision'])

    def test_two_day_atomic_change_and_restore_audit(self):
        before = self.snapshot()
        a = self.candidate('2026-10-12', 'cable')
        b = self.candidate('2026-10-13')
        b['plan']['public_note'] = '搬到隔天'
        first = self.update(self.new_request_id(), [a, b])
        after = self.snapshot()
        self.assertEqual(after['version'], before['version'] + 1)
        self.assertEqual(after['audit_count'], before['audit_count'] + 2)
        self.assertEqual([d for d in before['payload']['days'] if d['date'] not in ('2026-10-12','2026-10-13')],
                         [d for d in after['payload']['days'] if d['date'] not in ('2026-10-12','2026-10-13')])
        self.assertEqual(self.scalar('''SELECT count(*) FROM content_revisions
            WHERE target_table='itinerary_days' AND field_name='day_plan' AND request_id=%s''', (first['request_id'],)), 2)
        audit = self.scalar('''SELECT jsonb_build_object('old',old_value::jsonb,'new',new_value::jsonb,
           'base',base_version,'result',resulting_version,'source',source,'reason',reason)
           FROM content_revisions WHERE target_id=%s AND request_id=%s''',
           (a['id'], first['request_id']))
        self.assertEqual(audit['old']['plan'], before['payload']['days'][2]['plan'])
        self.assertEqual(audit['new']['plan'], a['plan'])
        self.assertEqual((audit['base'],audit['result']), (1,2))
        self.assertEqual((audit['source'],audit['reason']), ('fixture','itinerary test'))
        originals = [d for d in before['payload']['days'] if d['date'] in ('2026-10-12','2026-10-13')]
        restored = self.update(self.new_request_id(), originals)
        self.assertNotEqual(restored['request_id'], first['request_id'])
        self.assertEqual(self.snapshot()['revision'], before['revision'])
        self.assertEqual(self.snapshot()['audit_count'], before['audit_count'] + 4)

    def test_two_day_activity_meal_transport_swap(self):
        self.execute("INSERT INTO cards(slug,name) VALUES ('vinwonders','Fixture VinWonders')")
        baseline = self.snapshot()
        first = self.candidate('2026-10-12', 'cable')
        second = self.candidate('2026-10-13', 'vinwonders')
        template = baseline['payload']['days'][0]['plan']['segments']
        for day, meal_ref, mode in (
            (first, {'type': 'pool', 'id': 'fixture-pool'}, 'grab'),
            (second, {'type': 'food', 'id': 'fixture-unrelated'}, 'taxi'),
        ):
            meal = copy.deepcopy(template[1])
            meal['ref'] = meal_ref
            transfer = copy.deepcopy(template[2])
            transfer['transfer']['from_ref'] = {'type': 'card', 'id': day['main_card_slug']}
            transfer['transfer']['mode'] = mode
            day['plan']['segments'].extend([meal, transfer])
        self.update(self.new_request_id(), [first, second])
        before = self.snapshot()
        swapped_first = copy.deepcopy(first)
        swapped_second = copy.deepcopy(second)
        for target, source in ((swapped_first, second), (swapped_second, first)):
            target['day_kind'] = source['day_kind']
            target['main_card_slug'] = source['main_card_slug']
            target['plan'] = copy.deepcopy(source['plan'])
        receipt = self.update(self.new_request_id(), [swapped_first, swapped_second])
        after = self.snapshot()
        self.assertEqual(after['version'], before['version'] + 1)
        self.assertEqual(after['audit_count'], before['audit_count'] + 2)
        self.assertEqual(receipt['changed_day_ids'], [first['id'], second['id']])
        days = {d['id']: d for d in after['payload']['days']}
        self.assertEqual(days[first['id']]['main_card_slug'], second['main_card_slug'])
        self.assertEqual(days[second['id']]['main_card_slug'], first['main_card_slug'])
        for target, expected in ((first, second), (second, first)):
            actual = days[target['id']]['plan']['segments']
            self.assertEqual(actual, expected['plan']['segments'])
            self.assertEqual(actual[1]['ref'], expected['plan']['segments'][1]['ref'])
            self.assertEqual(actual[2]['transfer'], expected['plan']['segments'][2]['transfer'])
        self.assertEqual([d for d in after['payload']['days'] if d['id'] not in (first['id'], second['id'])],
                         [d for d in before['payload']['days'] if d['id'] not in (first['id'], second['id'])])
        self.assertEqual(after['payload']['refs']['cards'], before['payload']['refs']['cards'])
        self.assertEqual(after['payload']['refs']['foods'], before['payload']['refs']['foods'])

    def test_second_bad_day_rolls_back_all_and_rejects_shapes(self):
        a = self.candidate('2026-10-12', 'cable')
        b = self.candidate('2026-10-13')
        b['plan']['segments'] = [copy.deepcopy(a['plan']['segments'][0])]
        b['plan']['segments'][0]['ref']['id'] = 'missing'
        self.failure('22023', [a,b])
        for bad in ({'private': 1}, {'plan': {'unknown': 1}}):
            c = copy.deepcopy(a)
            if 'plan' in bad:
                c['plan'].update(bad['plan'])
            else:
                c.update(bad)
            self.failure('22023', [c])
        c = self.candidate('2026-10-10')
        c['plan']['segments'][2]['transfer']['buffer_minutes'] = -1
        self.failure('22023', [c])
        c['plan']['segments'][2]['transfer']['buffer_minutes'] = None
        self.failure('22023', [c])
        c = self.candidate('2026-10-12')
        c['plan']['public_note'] = '🍍' * 33000
        self.failure('22023', [c])
        self.failure('22023', {'not':'an array'})
        self.failure('22023', [None])
        self.failure('22023', [a], source='')
        self.failure('22023', [a], reason='  ')

    def test_stale_base_source_and_reused_id(self):
        current = self.snapshot()
        changed = self.candidate('2026-10-12', 'cable')
        self.failure('40001', [changed], base=current['version'] - 1, revision=current['revision'])
        self.execute("UPDATE food_places SET hours_text='changed' WHERE notion_id='fixture-food'")
        self.failure('40001', [changed], base=current['version'], revision=current['revision'])
        self.execute("UPDATE food_places SET hours_text='old hours' WHERE notion_id='fixture-food'")
        rid = self.new_request_id()
        self.update(rid, [changed])
        newer = self.candidate('2026-10-13')
        newer['plan']['public_note'] = 'different'
        self.failure('22023', [newer], request_id=rid, message='REQUEST_ID_REUSED')
        self.failure('22023', [changed], request_id=rid, decisions=[{'day_id':changed['id'],
                     'segment_id':'main','previous_ref':None,'decision':'keep'}], message='REQUEST_ID_REUSED')

    def test_protected_day_and_explicit_decisions(self):
        locked = self.candidate('2026-10-11')
        locked['main_card_slug'] = None
        locked['day_kind'] = 'light'
        locked['plan']['segments'] = []
        self.failure('22023', [locked], message='LOCKED_ARRANGEMENT')
        elsewhere = self.candidate('2026-10-12', 'onbird')
        self.failure('22023', [elsewhere], message='LOCKED_ARRANGEMENT')
        booking = self.candidate('2026-10-10')
        booking['plan']['segments'][2]['transfer']['to_ref'] = {'type':'point','id':'fixture-point'}
        self.failure('22023', [booking], message='LOCKED_ARRANGEMENT')
        original = self.candidate('2026-10-10')
        original['plan']['segments'][1]['selection'] = 'explicit'
        self.update(self.new_request_id(), [original])
        changed = self.candidate('2026-10-10')
        changed['plan']['segments'][1]['ref'] = {'type':'food','id':'fixture-food'}
        self.failure('22023', [changed], message='EXPLICIT_DECISION_REQUIRED')
        decision = [{'day_id': original['id'], 'segment_id':'meal',
                     'previous_ref':{'type':'pool','id':'fixture-pool'}, 'decision':'replace'}]
        wrong = copy.deepcopy(decision)
        wrong[0]['decision'] = 'keep'
        self.failure('22023', [changed], decisions=wrong, message='EXPLICIT_DECISION_REQUIRED')
        wrong = copy.deepcopy(decision)
        wrong[0]['previous_ref']['id'] = 'fixture-unrelated'
        self.failure('22023', [changed], decisions=wrong, message='EXPLICIT_DECISION_REQUIRED')
        self.update(self.new_request_id(), [changed], decisions=decision)
        self.assertEqual(self.snapshot()['payload']['days'][0]['plan']['segments'][1]['ref'], {'type':'food','id':'fixture-food'})

    def test_protected_booking_must_remain_on_main_route(self):
        candidate = self.candidate('2026-10-10')
        original_transfer = candidate['plan']['segments'][2]
        candidate['plan']['segments'] = candidate['plan']['segments'][:2]
        # The booking is visible but conditional: it cannot satisfy the core lock.
        fallback = copy.deepcopy(original_transfer)
        fallback['id'] = 'fallback-hotel'
        candidate['plan']['alternatives'][0]['replacement_segments'].append(fallback)
        self.execute('SELECT itinerary_validate_day(%s::jsonb)', (json.dumps(candidate),))
        self.failure('22023', [candidate], message='LOCKED_ARRANGEMENT')

        # Reorganizing the main transfer while keeping the booked base is allowed.
        reorganized = self.candidate('2026-10-10')
        reorganized['plan']['segments'][2]['id'] = 'return-hotel'
        reorganized['plan']['segments'][2]['transfer']['mode'] = 'taxi'
        self.update(self.new_request_id(), [reorganized])

    def test_explicit_meal_demotion_to_alternative_or_non_meal_requires_decision(self):
        explicit = self.candidate('2026-10-10')
        explicit['plan']['segments'][1]['selection'] = 'explicit'
        self.update(self.new_request_id(), [explicit])
        declaration = [{'day_id': explicit['id'], 'segment_id': 'meal',
                        'previous_ref': {'type':'pool','id':'fixture-pool'}, 'decision':'remove'}]

        alternative = self.candidate('2026-10-10')
        meal = alternative['plan']['segments'].pop(1)
        alternative['plan']['alternatives'][0]['replacement_segments'].append(meal)
        self.execute('SELECT itinerary_validate_day(%s::jsonb)', (json.dumps(alternative),))
        self.failure('22023', [alternative], message='EXPLICIT_DECISION_REQUIRED')
        self.update(self.new_request_id(), [alternative], decisions=declaration)
        self.assertNotIn('meal', [s['id'] for s in self.snapshot()['payload']['days'][0]['plan']['segments']])

        # Restore the ordinary explicit meal with a new operation before testing a role change.
        self.update(self.new_request_id(), [explicit], decisions=declaration)
        non_meal = self.candidate('2026-10-10')
        non_meal['plan']['segments'][1]['kind'] = 'rest'
        self.execute('SELECT itinerary_validate_day(%s::jsonb)', (json.dumps(non_meal),))
        self.failure('22023', [non_meal], message='EXPLICIT_DECISION_REQUIRED')
        self.update(self.new_request_id(), [non_meal], decisions=declaration)
        self.assertEqual(self.snapshot()['payload']['days'][0]['plan']['segments'][1]['kind'], 'rest')

    def test_onbird_protects_activity_not_breakfast_or_evening(self):
        day = self.candidate('2026-10-11')
        breakfast = copy.deepcopy(self.candidate('2026-10-10')['plan']['segments'][1])
        breakfast['id'] = 'breakfast'
        evening = copy.deepcopy(breakfast)
        evening['id'] = 'dinner'
        evening['ref'] = {'type':'food', 'id':'fixture-unrelated'}
        day['plan']['segments'] = [breakfast, day['plan']['segments'][0], evening]
        self.update(self.new_request_id(), [day])
        revised = self.candidate('2026-10-11')
        revised['plan']['segments'][0]['ref'] = {'type':'food','id':'fixture-food'}
        revised['plan']['segments'][2]['ref'] = {'type':'pool','id':'fixture-pool'}
        self.update(self.new_request_id(), [revised])
        updated = self.snapshot()['payload']['days'][1]
        self.assertEqual(updated['main_card_slug'], 'onbird')
        self.assertEqual(updated['plan']['segments'][0]['ref'], {'type':'food','id':'fixture-food'})
        self.assertEqual(updated['plan']['segments'][2]['ref'], {'type':'pool','id':'fixture-pool'})

    def test_acl_no_public_update(self):
        self.execute('SAVEPOINT update_acl')
        try:
            self.execute('SET LOCAL ROLE phq_web_ro')
            with self.assertRaises(psycopg2.Error) as raised:
                self.execute("SELECT public.itinerary_update('phuquoc-2026',1,'x',gen_random_uuid(),'[]','[]',NULL,'s','r')")
            self.assertEqual(raised.exception.pgcode, '42501')
        finally:
            self.execute('ROLLBACK TO SAVEPOINT update_acl')


class ConcurrentUpdateTests(unittest.TestCase):
    """Committed fixture so separate sessions can contend on real rows."""
    def setUp(self):
        self.db = psycopg2.connect(test_dsn())
        if self.db.server_version // 10000 != 18 or not self.db.info.host.startswith('/tmp/opencode/'):
            self.db.close()
            raise RuntimeError('Expected local PG18 socket')
        with self.db.cursor() as cur:
            cur.execute('SELECT payload FROM public.itinerary_public LIMIT 0')
            cur.execute(SEED.read_text().split('-- TEST SEED (rollback fixture)')[1])
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        with self.db.cursor() as cur:
            for table, predicate in (
                ('content_revisions', "target_table='itinerary_days' AND target_id LIKE 'phuquoc-2026:%'"),
                ('itinerary_requests', "itinerary_id='phuquoc-2026'"),
                ('itinerary_days', "itinerary_id='phuquoc-2026'"),
                ('itineraries', "id='phuquoc-2026'"),
                ('food_pool', "pool_key='fixture-pool'"),
                ('food_places', "notion_id IN ('fixture-food','fixture-unrelated')"),
                ('cards', "slug='onbird'"),
                ('points', "slug='fixture-point'"),
                ('bookings', "slug='fixture-booking'"),
                ('transport_options', "slug='fixture-transport'"),
            ):
                cur.execute(f'DELETE FROM public.{table} WHERE {predicate}')
        self.db.commit()
        self.db.close()

    def state(self):
        with self.db.cursor() as cur:
            cur.execute("SELECT i.version, v.content_revision FROM itineraries i JOIN itinerary_public v ON i.id=v.itinerary_id WHERE i.id=%s", (ID,))
            return cur.fetchone()

    def race(self, same_request):
        base, revision = self.state()
        with self.db.cursor() as cur:
            cur.execute("SELECT jsonb_build_object('id',id,'date',date,'day_kind',day_kind,'main_card_slug',main_card_slug,'plan',plan) FROM itinerary_days WHERE date='2026-10-12'")
            day = cur.fetchone()[0]
        day['plan']['public_note'] = 'raced'
        req = str(uuid.uuid4())
        barrier = threading.Barrier(2)
        results = []
        def worker(index):
            conn = psycopg2.connect(test_dsn())
            try:
                with conn.cursor() as cur:
                    cur.execute('SET statement_timeout=5000')
                    barrier.wait(timeout=5)
                    cur.execute('SELECT itinerary_update(%s,%s,%s,%s::uuid,%s::jsonb,%s::jsonb,%s,%s,%s)',
                                (ID,base,revision,req if same_request else str(uuid.uuid4()),
                                 json.dumps([day]),'[]',None,'fixture','race'))
                    results.append(('ok',cur.fetchone()[0]))
                conn.commit()
            except psycopg2.Error as err:
                results.append((err.pgcode,err.diag.message_primary))
                conn.rollback()
            finally:
                conn.close()
        threads = [threading.Thread(target=worker,args=(i,)) for i in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=8)
        self.assertFalse(any(t.is_alive() for t in threads))
        return results

    def test_two_distinct_requests_one_wins(self):
        results = self.race(False)
        self.assertEqual(sorted(x[0] for x in results), ['40001','ok'])
        self.assertEqual(self.state()[0], 2)

    def test_same_request_replays_receipt(self):
        results = self.race(True)
        self.assertEqual([x[0] for x in results], ['ok','ok'])
        self.assertEqual(results[0][1],results[1][1])
        with self.db.cursor() as cur:
            cur.execute("SELECT count(*) FROM content_revisions WHERE target_table='itinerary_days'")
            self.assertEqual(cur.fetchone()[0],1)

    def test_pool_reassignment_while_update_waits(self):
        base, revision = self.state()
        with self.db.cursor() as cur:
            cur.execute("SELECT jsonb_build_object('id',id,'date',date,'day_kind',day_kind,'main_card_slug',main_card_slug,'plan',plan) FROM itinerary_days WHERE date='2026-10-12'")
            day = cur.fetchone()[0]
        day['plan']['public_note'] = 'pool race'
        writer = psycopg2.connect(test_dsn())
        updater = psycopg2.connect(test_dsn())
        try:
            with writer.cursor() as cur:
                cur.execute('SET statement_timeout=5000')
                cur.execute("UPDATE food_pool SET notion_id='fixture-unrelated' WHERE pool_key='fixture-pool'")
            finished = threading.Event()
            started = threading.Event()
            result = []
            def run():
                try:
                    with updater.cursor() as cur:
                        cur.execute('SET statement_timeout=5000')
                        started.set()
                        cur.execute('SELECT itinerary_update(%s,%s,%s,%s::uuid,%s::jsonb,%s::jsonb,%s,%s,%s)',
                                    (ID,base,revision,str(uuid.uuid4()), json.dumps([day]),'[]',None,'fixture','pool race'))
                        result.append(('ok',cur.fetchone()[0]))
                    updater.commit()
                except psycopg2.Error as err:
                    result.append((err.pgcode, err.diag.message_primary))
                    updater.rollback()
                finally:
                    finished.set()
            thread = threading.Thread(target=run)
            thread.start()
            self.assertTrue(started.wait(timeout=5))
            time.sleep(.2)
            self.assertFalse(finished.is_set(), 'update must wait for source lock')
            writer.commit()
            thread.join(timeout=8)
            self.assertFalse(thread.is_alive())
            self.assertEqual(result, [('40001','SOURCE_CHANGED')])
            self.assertEqual(self.state()[0],base)
        finally:
            writer.rollback()
            updater.rollback()
            writer.close()
            updater.close()
