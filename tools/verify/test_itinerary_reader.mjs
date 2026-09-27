import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {validateEnvelope, loadItinerary} from '../itinerary-reader.mjs';

const fixture = JSON.parse(await readFile(new URL('./fixtures/itinerary-envelope.json', import.meta.url)));
const clone = () => structuredClone(fixture);
const invalid = value => assert.throws(() => validateEnvelope(value), {message: 'INVALID_ITINERARY'});

test('accepts the six-day public projection from the isolated A view', () => {
  assert.equal(validateEnvelope(clone()).data.itinerary.id, 'phuquoc-2026');
});

test('rejects old wire, missing days, duplicate day IDs and invalid revision', () => {
  for (const change of [
    x => {x.data.itinerary = 'phuquoc-2026';},
    x => {x.data.days.pop();},
    x => {x.data.days[1].id = x.data.days[0].id;},
    x => {x.meta.content_revision = 'not-a-hash';},
    x => {x.data.schema_version = 2;},
  ]) { const x = clone(); change(x); invalid(x); }
});

test('rejects missing referenced rows, malformed base and malicious or unsupported URLs', () => {
  for (const change of [
    x => {x.data.refs.cards = [];},
    x => {x.data.refs.foods = [];},
    x => {x.data.refs.bases[0] = {id:'hotel', type:'booking', ref:'fixture-booking'};},
    x => {x.data.days[0].plan.segments[1].ref.id = 'unknown';},
    x => {x.data.days[0].plan.segments[2].transfer.to_ref.id = 'missing';},
    x => {x.data.days[0].plan.segments[0].time.day_offset = 2;},
    x => {x.data.days[0].plan.segments[0].time.timezone = 'No/Such_Zone';},
    x => {x.data.days[0].plan.segments[0].url = 'javascript:alert(1)';},
    x => {x.data.days[0].plan.segments[0].condition_refs=['nonexistent'];},
    x => {x.data.days[0].plan.segments[2].transfer.condition_refs=['nonexistent'];},
  ]) { const x = clone(); change(x); invalid(x); }
});

test('main card must be active and mapped condition keys must match card gate text',()=>{
  const retired=clone();retired.data.refs.cards.find(c=>c.slug==='onbird').status='RETIRED';invalid(retired);
  const mapped=clone(),card=mapped.data.refs.cards.find(c=>c.slug==='onbird');
  card.gates=JSON.stringify(['Existing public gate']);card.condition_labels={check:'Existing public gate'};
  mapped.data.days[1].plan.segments[0].condition_refs=['check'];
  validateEnvelope(mapped);
  card.gates=JSON.stringify(['Changed source text']);invalid(mapped);
});

test('mapped card keys cannot be borrowed by a segment without that card',()=>{
  const mapped=clone(),card=mapped.data.refs.cards.find(c=>c.slug==='onbird');
  card.gates=JSON.stringify(['Existing public gate']);card.condition_labels={check:'Existing public gate'};
  mapped.data.days[1].plan.segments[0].condition_refs=['check'];validateEnvelope(mapped);
  mapped.data.days[0].plan.segments[1].condition_refs=['check'];invalid(mapped);
  mapped.data.days[0].plan.segments[1].condition_refs=[];
  mapped.data.days[0].plan.segments[2].transfer.condition_refs=['check'];invalid(mapped);
});

test('uses entire dated fallback after invalid live response', async () => {
  const bad = clone(); bad.data.days.pop();
  const seen = [];
  const loaded = await loadItinerary({apiUrl:'https://api.test/api/itinerary', fallbackUrl:'https://site.test/data/itinerary.json',
    fetchImpl: async url => {seen.push(url); return new Response(JSON.stringify(seen.length === 1 ? bad : fixture));}});
  assert.equal(loaded.mode, 'fallback');
  assert.deepEqual(loaded.envelope.data.days, fixture.data.days);
  assert.deepEqual(seen, ['https://api.test/api/itinerary', 'https://site.test/data/itinerary.json']);
});

test('fails clearly when neither complete source is available', async () => {
  await assert.rejects(loadItinerary({apiUrl:'live',fallbackUrl:'backup',fetchImpl:async () => new Response('{}')}),
    {message:'ITINERARY_UNAVAILABLE'});
});

test('accepts a live read without export date but rejects an undated backup', async () => {
  const undated=clone();delete undated.meta.exported_at;
  assert.equal(validateEnvelope(undated).meta.exported_at,undefined);
  await assert.rejects(loadItinerary({apiUrl:'live',fallbackUrl:'backup',fetchImpl:async url => url==='live'
    ? new Response('{}',{status:503}) : new Response(JSON.stringify(undated))}),{message:'ITINERARY_UNAVAILABLE'});
});

test('rejects fallback export dates that are not timestamps', async () => {
  const backup=clone();backup.meta.exported_at='2026-09-27';
  await assert.rejects(loadItinerary({apiUrl:'live',fallbackUrl:'backup',fetchImpl:async url => url==='live'
    ? new Response('{}',{status:503}) : new Response(JSON.stringify(backup))}),{message:'ITINERARY_UNAVAILABLE'});
});

test('rejects impossible calendar dates in fallback export timestamps', async () => {
  for (const exported_at of ['2026-02-30T00:00:00Z','2026-04-31T23:59:59+07:00']) {
    const backup=clone();backup.meta.exported_at=exported_at;
    await assert.rejects(loadItinerary({apiUrl:'live',fallbackUrl:'backup',fetchImpl:async url => url==='live'
      ? new Response('{}',{status:503}) : new Response(JSON.stringify(backup))}),{message:'ITINERARY_UNAVAILABLE'});
  }
});

test('times out a stalled source before trying backup', async () => {
  const seen=[];
  const loaded=await loadItinerary({apiUrl:'live',fallbackUrl:'backup',timeoutMs:15,fetchImpl:(url,{signal}) => {
    seen.push(url);
    if(url==='backup') return Promise.resolve(new Response(JSON.stringify(fixture)));
    return new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(Error('abort')),{once:true}));
  }});
  assert.equal(loaded.mode,'fallback');
  assert.deepEqual(seen,['live','backup']);
});
