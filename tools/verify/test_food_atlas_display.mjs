import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {renderItinerary} from '../itinerary-reader.mjs';
const fixture=JSON.parse(await readFile(new URL('./fixtures/itinerary-envelope.json',import.meta.url)));
class Node {
  constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.attributes={};this.className='';this.textContent='';}
  append(...nodes){this.children.push(...nodes)} replaceChildren(...nodes){this.children=nodes}
  querySelector(){return null} setAttribute(k,v){this.attributes[k]=v} addEventListener(){}
}
const walk=node=>[node,...node.children.flatMap(walk)];
const text=node=>walk(node).map(n=>n.textContent).join(' ');
function render(change){
  const envelope=structuredClone(fixture);change(envelope);
  const prior=globalThis.document;
  globalThis.document={createElement:t=>new Node(t),createDocumentFragment:()=>new Node('fragment'),documentElement:{dataset:{}}};
  try{const root=new Node('root');renderItinerary(root,{envelope,mode:'live'});return root}finally{globalThis.document=prior}
}
function meal(root){return walk(root).find(n=>n.dataset.segmentId==='meal')}
test('held meal is explicitly paused while original reference and time stay intact',()=>{
  const root=render(x=>{x.data.refs.foods[0].atlas_state='VERIFY';x.data.days[0].plan.segments[1].note='暫排一般餐飲推薦';});
  const m=meal(root);assert.match(text(m),/待再確認.*暫停推薦/);
  assert.equal(m.dataset.refId,'fixture-pool');assert.match(text(m),/時間待定/);
  const original=walk(m).find(n=>n.className==='itinerary-original-note');
  assert.equal(original?.tag,'details');assert.match(text(original),/暫排一般餐飲推薦/);
});
test('excluded meal and direct food references cannot render as ordinary recommendations',()=>{
  const root=render(x=>{x.data.refs.foods[0].atlas_state='DEACTIVATED';x.data.days[0].plan.segments[1].ref={type:'food',id:x.data.refs.foods[0].notion_id}});
  assert.match(text(meal(root)),/已下架.*不列入用餐建議/);
});
test('operating date and source review date remain distinct even on the same day',()=>{
  const root=render(x=>Object.assign(x.data.refs.foods[0],{atlas_state:'ACTIVE',last_verified:'2026-08-01',evidence_as_of:'2026-08-01'}));
  assert.match(text(meal(root)),/營運核實 2026-08-01/);assert.match(text(meal(root)),/資料查核 2026-08-01/);
});
test('unknown operating verification cannot borrow the source-review date',()=>{
  const root=render(x=>Object.assign(x.data.refs.foods[0],{last_verified:null,evidence_as_of:'2026-10-11'}));
  assert.match(text(meal(root)),/營運核實：未知/);assert.match(text(meal(root)),/資料查核 2026-10-11/);
  assert.doesNotMatch(text(meal(root)),/營運核實 2026-10-11/);
});
test('long research and untrusted source strings are preserved only inside closed native details',()=>{
  const source='<img src=x onerror="alert(1)">\n'+JSON.stringify({source:'https://example.test/'+ 'x'.repeat(800)});
  const root=render(x=>{x.data.refs.foods[0].evidence=source});const m=meal(root);
  const details=walk(m).find(n=>n.className==='itinerary-evidence'&&text(n).includes(source));
  assert.equal(details?.tag,'details');assert.equal(details.attributes.open,undefined);
  assert.equal(walk(details).find(n=>n.textContent===source)?.tag,'p');
  assert.equal(walk(m).filter(n=>n.tag==='img').length,0);
});
