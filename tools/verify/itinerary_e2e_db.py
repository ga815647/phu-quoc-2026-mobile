"""One rollback-only local PG18 edit -> audit -> public export for the C3 browser scenario."""
import json

from itinerary_db_support import ItineraryDBCase
from tools.itinerary_export import read_itinerary


def main():
    case = ItineraryDBCase(methodName='runTest')
    case.setUp()  # guards local socket, PG18, explicit write opt-in and rollback fixture
    try:
        case.execute("INSERT INTO cards(slug,name) VALUES ('cable','Fixture cable')")
        before = case.snapshot()
        original = next(d for d in before['payload']['days'] if d['date'] == '2026-10-12')
        day = case.candidate('2026-10-12', 'cable')
        # The changed day has a card, a meal and a transfer; the latter two follow the route.
        import copy
        source = before['payload']['days'][0]['plan']['segments']
        meal, transfer = copy.deepcopy(source[1]), copy.deepcopy(source[2])
        meal['ref'] = {'type': 'food', 'id': 'fixture-unrelated'}
        transfer['transfer']['from_ref'] = {'type': 'card', 'id': 'cable'}
        transfer['transfer']['mode'] = 'taxi'
        day['plan']['segments'].extend([meal, transfer])
        request_id = case.new_request_id()
        receipt = case.update(request_id, [day], before['version'], before['revision'])
        audit = case.scalar("""SELECT jsonb_build_object('old',old_value::jsonb,'new',new_value::jsonb,
            'base',base_version,'result',resulting_version) FROM content_revisions
            WHERE request_id=%s::uuid AND target_id=%s""", (request_id, day['id']))
        for field in ('day_kind', 'main_card_slug', 'plan'):
            assert audit['old'][field] == original[field], f'wrong audited old {field}'
            assert audit['new'][field] == day[field], f'wrong audited new {field}'
        assert (audit['base'], audit['result']) == (before['version'], before['version'] + 1)
        assert case.scalar('SELECT count(*) FROM content_revisions WHERE request_id=%s::uuid', (request_id,)) == 1
        # Same view as Function/export; metadata is explicitly synthetic for local browser verifier.
        def fetch(_query):
            with case.db.cursor() as cur:
                cur.execute('SELECT payload,content_revision FROM public.itinerary_public WHERE itinerary_id=%s', ('phuquoc-2026',))
                payload, revision = cur.fetchone()
                return [{'payload': payload, 'content_revision': revision}]
        envelope = read_itinerary(fetch, 'neon-prod', 'production', '2026-09-27T00:00:00Z')
        assert envelope['meta']['content_revision'] == receipt['content_revision'] != before['revision']
        assert next(d for d in envelope['data']['days'] if d['id'] == day['id'])['plan'] == day['plan']
        print(json.dumps({'envelope': envelope, 'receipt': receipt, 'audit': audit}, ensure_ascii=False))
    finally:
        case.tearDown()


if __name__ == '__main__':
    main()
