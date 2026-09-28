"""Read the same fixed public itinerary projection used by the API."""
import re

ID = 'phuquoc-2026'
SQL = "SELECT payload,content_revision FROM public.itinerary_public WHERE itinerary_id='phuquoc-2026'"


def read_itinerary(fetch, source, environment, exported_at):
    rows = fetch(SQL)
    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError('ITINERARY_UNAVAILABLE')
    row = rows[0]
    payload = row.get('payload')
    trip = payload.get('itinerary') if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or payload.get('schema_version') != 1 or \
            not isinstance(trip, dict) or trip.get('id') != ID or \
            trip.get('start_date') != '2026-10-10' or \
            trip.get('end_date') != '2026-10-15' or \
            trip.get('timezone') != 'Asia/Ho_Chi_Minh' or \
            not isinstance(payload.get('refs'), dict) or not isinstance(payload['refs'].get('bases'), list) or \
            not isinstance(payload.get('days'), list) or len(payload['days']) != 6 or \
            any(not isinstance(day, dict) or
                day.get('date') != f'2026-10-{date}' or
                day.get('id') != f'{ID}:2026-10-{date}' or
                not isinstance(day.get('plan'), dict) or
                type(day['plan'].get('schema_version')) is not int or day['plan']['schema_version'] != 1 or
                not isinstance(day['plan'].get('segments'), list) or
                not isinstance(day['plan'].get('alternatives'), list)
                for date, day in zip(range(10, 16), payload['days'])) or \
            not isinstance(row.get('content_revision'), str) or \
            not re.fullmatch(r'phq1:[0-9a-f]{64}', row['content_revision']):
        raise ValueError('ITINERARY_UNAVAILABLE')
    return {'data': payload, 'meta': {'schema_version': 1,
            'content_revision': row['content_revision'], 'source': source,
            'environment': environment, 'fetched_at': exported_at,
            'exported_at': exported_at}}
