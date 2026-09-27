import {test} from 'node:test';
import assert from 'node:assert/strict';
import {validateRequest, SITE_URL, RESULT_BRANCH, UUID_RE} from './site-check-contract.mjs';

const id='1f4be2aa-e9b5-4a8a-8f1c-68c6d7eef67a';
const day='phuquoc-2026:2026-10-12';
const path=`bridge/site-check/requests/${id}.json`;
const sha='a'.repeat(40), parent='b'.repeat(40);
const requestFixture={
  schema_version:1,request_id:id,target:'production',itinerary_id:'phuquoc-2026',
  expected_content_revision:`phq1:${'a'.repeat(64)}`,changed_day_ids:[day],
  expected:[{day_id:day,main_card_slug:'cable',meals:[],transfers:[]}],
};
const trustedContext={repository:'ga815647/phu-quoc-2026-mobile',event:'push',
  branch:`chat-site-check/${id}`,requestSha:sha,parents:[parent],mainAncestor:true,
  files:[{filename:path,status:'added'}]};
const bytes=x=>new TextEncoder().encode(JSON.stringify(x));
const check=(request=requestFixture,context=trustedContext)=>validateRequest(bytes(request),context);
const invalid=(request,context=trustedContext)=>assert.throws(()=>check(request,context),/^Error: INVALID_REQUEST$/);

test('exports stable site and result identifiers',()=>{
  assert.equal(SITE_URL,'https://ga815647.github.io/phu-quoc-2026-mobile/');
  assert.equal(RESULT_BRANCH,'site-check-results');
  assert.ok(UUID_RE.test(id));
});
test('accepts one exact request and optional previous request ID',()=>{
  assert.deepEqual(check(),requestFixture);
  assert.deepEqual(check({...requestFixture,previous_request_id:'99f2ab99-96c0-48d6-a347-07e4d196fe2f'}),
    {...requestFixture,previous_request_id:'99f2ab99-96c0-48d6-a347-07e4d196fe2f'});
});
test('accepts all six distinct days with complete statically shaped expected assertions',()=>{
  const ids=Array.from({length:6},(_,n)=>`phuquoc-2026:2026-10-${10+n}`);
  const request={...requestFixture,changed_day_ids:ids,expected:ids.map(day_id=>({
    day_id,main_card_slug:null,meals:[{segment_id:'lunch',ref:{type:'pool',id:'fixture-pool'}}],
    transfers:[{segment_id:'ride',from_ref:{type:'base',id:'hotel'},
      to_ref:{type:'point',id:'fixture-point'},mode:'grab'}],
  }))};
  assert.deepEqual(check(request),request);
});
test('rejects empty, non-JSON, non-UTF8, BOM and oversized input',()=>{
  for(const raw of [new Uint8Array(),new Uint8Array([0xff]),new TextEncoder().encode('{'),
    new Uint8Array([0xef,0xbb,0xbf,0x7b,0x7d]),new Uint8Array(128*1024+1),
    JSON.stringify(requestFixture)]) {
    assert.throws(()=>validateRequest(raw,trustedContext),/^Error: INVALID_REQUEST$/);
  }
});
test('rejects unknown keys, missing keys and invalid scalars',()=>{
  for(const request of [null,[],{...requestFixture,sql:'SELECT 1'},
    {...requestFixture,target:'staging'}, {...requestFixture,schema_version:2},
    {...requestFixture,request_id:id.toUpperCase()},
    {...requestFixture,expected_content_revision:'phq1:wrong'},
    {...requestFixture,expected_content_revision:{toString:null}},
    {...requestFixture,request_id:{toString:null}},
    {...requestFixture,itinerary_id:'other'},
    {...requestFixture,previous_request_id:id},
    {...requestFixture,previous_request_id:'bad'},
    {...requestFixture,previous_request_id:{toString:null}},
    (({expected,...rest})=>rest)(requestFixture)]) invalid(request);
});
test('rejects invalid days, duplicates and incomplete expected sets',()=>{
  for(const changed_day_ids of [[],[day,day],['phuquoc-2026:2026-10-16'],
    ['phuquoc-2026:2026-02-30'],['phuquoc-2026:2026-10-01'],['../2026-10-12']])
    invalid({...requestFixture,changed_day_ids});
  for(const expected of [[],[requestFixture.expected[0],requestFixture.expected[0]],
    [{...requestFixture.expected[0],day_id:'phuquoc-2026:2026-10-13'}]])
    invalid({...requestFixture,expected});
});
test('rejects unknown refs, modes, slug, unsafe IDs, extra keys and duplicate segment IDs',()=>{
  const base=requestFixture.expected[0];
  const meal={segment_id:'meal',ref:{type:'food',id:'abc-123'}};
  const transfer={segment_id:'trip',from_ref:{type:'base',id:'hotel'},
    to_ref:{type:'card',id:'cable'},mode:'walk'};
  const variants=[
    {...base,main_card_slug:'khem'}, {...base,main_card_slug:'https://example.com'},
    {...base,private_note:'secret'}, {...base,meals:[{...meal,ref:{type:'booking',id:'abc'}}]},
    {...base,meals:[{...meal,ref:{type:'food',id:'../secret'}}]},
    {...base,meals:[{...meal,segment_id:'https://bad'}]},
    {...base,meals:[{...meal,segment_id:{toString:null}}]},
    {...base,meals:[{...meal,ref:{...meal.ref,url:'https://bad'}}]},
    {...base,meals:[meal,meal]},
    {...base,meals:[{...meal,segment_id:'trip'}],transfers:[transfer]},
    {...base,transfers:[transfer,transfer]},
    {...base,transfers:[{...transfer,mode:'helicopter'}]},
    {...base,transfers:[{...transfer,segment_id:{toString:null}}]},
    {...base,transfers:[{...transfer,to_ref:{type:'unknown',id:'a'}}]},
    {...base,transfers:[{...transfer,from_ref:{type:'card',id:'khem'}}]},
  ];
  for(const assertion of variants) invalid({...requestFixture,expected:[assertion]});
});
test('rejects untrusted provenance even with one added JSON file',()=>{
  const variants=[
    {repository:'attacker/phu-quoc-2026-mobile'}, {event:'pull_request'},
    {branch:`chat-site-check/${id}-other`}, {branch:'refs/heads/main'},
    {requestSha:'not-a-sha'}, {parents:[]}, {parents:[parent,sha]},
    {parents:['not-a-sha']}, {mainAncestor:false}, {mainAncestor:'true'},
    {files:[]}, {files:[{filename:path,status:'modified'}]},
    {files:[{filename:path,status:'renamed'}]},
    {files:[{filename:path,status:'deleted'}]},
    {files:[{filename:path,status:'added'},{filename:'.github/workflows/site-check.yml',status:'modified'}]},
    {files:[{filename:`bridge/site-check/requests/../${id}.json`,status:'added'}]},
    {files:[{filename:`bridge/site-check/requests/${id.toUpperCase()}.json`,status:'added'}]},
    {files:[{filename:`bridge/site-check/requests/${'f'.repeat(36)}.json`,status:'added'}]},
  ];
  for(const change of variants) invalid(requestFixture,{...trustedContext,...change});
});
