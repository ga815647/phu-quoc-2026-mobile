import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {chromium} from 'playwright';
import {verifySite} from './site-check-browser.mjs';

const fixture=JSON.parse(await readFile(new URL('./fixtures/itinerary-envelope.json',import.meta.url)));
const actualReader=await readFile(new URL('../itinerary-reader.mjs',import.meta.url),'utf8');
const day=fixture.data.days[0];
const meal=day.plan.segments.find(s=>s.kind==='meal');
const transfer=day.plan.segments.find(s=>s.kind==='transfer');
const request={request_id:'1f4be2aa-e9b5-4a8a-8f1c-68c6d7eef67a',expected_content_revision:fixture.meta.content_revision,
  changed_day_ids:[day.id],expected:[{day_id:day.id,main_card_slug:day.main_card_slug,
    meals:[{segment_id:meal.id,ref:meal.ref}],transfers:[{segment_id:transfer.id,
      from_ref:transfer.transfer.from_ref,to_ref:transfer.transfer.to_ref,mode:transfer.transfer.mode}]}]};
const localUrl='http://localhost:32111/';
const build='sha256:'+'b'.repeat(64);
const cardSlugs=['onbird','vinwonders','cable','starfish','safari'];

async function withPage(options,run) {
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
    if(options.delayBodyMs||options.foreverBody)page.on('response',response=>{
      if(new URL(response.url()).pathname!=='/api/itinerary')return;
      const original=response.json.bind(response);
      response.json=async()=>{options.bodyStarted?.();
        if(options.foreverBody)return new Promise(()=>{});
        await new Promise(resolve=>setTimeout(resolve,options.delayBodyMs));return original();};
    });
    const envelope=structuredClone(fixture);
    envelope.meta.source='neon-prod';envelope.meta.environment=options.environment||'production';
    if(options.cached)envelope.meta.content_revision=`phq1:${'c'.repeat(64)}`;
    const rendered=options.rendered||envelope;
    let navigations=0;
    await page.route('**/*',route=>{
      const url=new URL(route.request().url());
       if(url.pathname==='/' && options.delayedFinal && ++navigations>=3)return new Promise(()=>{});
      if(url.pathname==='/api/itinerary') return route.fulfill({status:options.unreachable?503:200,
        contentType:'application/json',body:JSON.stringify(envelope)});
      if(url.pathname==='/staging/api/itinerary')return route.fulfill({contentType:'application/json',body:JSON.stringify(envelope)});
      if(url.pathname==='/site-version.json')return route.fulfill({contentType:'application/json',body:JSON.stringify({build_id:options.build||build})});
      if(url.pathname==='/assets/itinerary-reader.mjs')return route.fulfill({contentType:'text/javascript; charset=utf-8',body:actualReader});
      if(url.pathname==='/card.html')return route.fulfill({status:options.card404?404:200,contentType:'text/html; charset=utf-8',
        body:`<!doctype html><title>Card</title><div id="cardMount"><h1>${envelope.data.refs.cards.find(c=>c.slug===url.searchParams.get('slug'))?.name||''}</h1></div>`});
      if(url.pathname==='/' && options.realReader)return route.fulfill({contentType:'text/html; charset=utf-8',body:`<!doctype html><html data-site-build="${build}"><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{overflow-wrap:anywhere} nav:not(.nav){display:grid;grid-template-columns:repeat(2,minmax(0,1fr))} .step{overflow-wrap:anywhere}</style></head><body>
        <nav class="nav">${['today','itinerary','food','journey'].map(s=>`<button data-jump="${s}" style="width:60px;height:44px">${s}</button>`).join('')}</nav>
        <div id="today"></div><div id="itinerary"><nav>${cardSlugs.map(s=>`<a class="link-card" href="./card.html?slug=${s}" style="display:inline-block;min-height:44px;padding:10px">${s}</a>`).join('')}</nav>
        <div data-itinerary></div></div><div id="food"></div><div id="journey"></div>
        <script>for(const btn of document.querySelectorAll('.nav button'))btn.onclick=()=>{
          for(const other of document.querySelectorAll('.nav button'))other.classList.toggle('primary',other===btn);
          document.getElementById(btn.dataset.jump).scrollIntoView();
        };</script>
        <script type="module">import {mountItinerary} from '/assets/itinerary-reader.mjs';
          mountItinerary({root:document.querySelector('[data-itinerary]'),apiUrl:'/api/itinerary',fallbackUrl:'/data/itinerary.json'});
        </script></body></html>`});
      if(url.pathname==='/')return route.fulfill({contentType:'text/html; charset=utf-8',body:`<!doctype html><html data-site-build="${build}"><body>${options.overflow?'<div style="width:2000px">overflow</div>':''}<nav class="nav">${['today','itinerary','food','journey'].map(s=>`<button data-jump="${s}" style="width:44px;height:44px">${s}</button>`).join('')}</nav><div id="today"></div><div id="itinerary"><nav>${cardSlugs.map(s=>`<a class="link-card" href="card.html?slug=${s}" style="display:inline-block;min-height:41px">${s}</a>`).join('')}</nav><div data-itinerary></div></div><div id="food"></div><div id="journey"></div><script>
        ${options.jsError?'throw Error("fixture error")':''}
        for(const btn of document.querySelectorAll('.nav button'))btn.onclick=()=>{
          for(const other of document.querySelectorAll('.nav button'))other.classList.toggle('primary',other===btn);
          document.getElementById(btn.dataset.jump).scrollIntoView();
        };
        ${options.foreign?"fetch('/staging/api/itinerary');":''}
        fetch('/api/itinerary').then(r=>r.json()).then(e=>{
          const data=${JSON.stringify(rendered)};
          const root=document.querySelector('[data-itinerary]');
          root.dataset.source=${JSON.stringify(options.fallback?'fallback':'live')};root.dataset.schemaVersion=String(data.meta.schema_version);
          root.dataset.contentRevision=data.meta.content_revision;
          const tabs=document.createElement('div');tabs.className='date-tabs';root.append(tabs);
          for(const d of data.data.days){const p=document.createElement('section');p.dataset.itineraryDay=d.id;p.dataset.mainCard=d.main_card_slug||'';p.className='day-panel';
            const tab=document.createElement('button');tab.className='date-tab';tab.textContent=d.date;tab.onclick=()=>{for(const section of root.querySelectorAll('.day-panel'))section.hidden=section!==p};tabs.append(tab);
            const main=document.createElement('b');main.textContent=d.main_card_slug?data.data.refs.cards.find(c=>c.slug===d.main_card_slug)?.name||'':'no card';p.append(main);
            const timeline=document.createElement('div');timeline.className='timeline';p.append(timeline);
            for(const s of d.plan.segments){let step=document.createElement('div');step.className='step';step.dataset.segmentId=s.id;
              step.dataset.refType=s.ref?.type||'';step.dataset.refId=s.ref?.id||'';
              if(s.transfer){step.dataset.fromRef=s.transfer.from_ref.type+':'+s.transfer.from_ref.id;
                step.dataset.toRef=s.transfer.to_ref.type+':'+s.transfer.to_ref.id;step.dataset.mode=s.transfer.mode;}
              step.textContent=${JSON.stringify(options.blank?'':null)}===null?(s.id==='start'&&${JSON.stringify(!!options.staleActivity)}?'Old secondary activity':s.label+' '+(s.ref ? (s.ref.type==='pool'?data.data.refs.foods.find(f=>f.notion_id===data.data.refs.pool.find(x=>x.pool_key===s.ref.id).notion_id)?.name||s.ref.id:data.data.refs[s.ref.type==='food'?'foods':s.ref.type==='card'?'cards':s.ref.type==='point'?'points':'bases'].find(x=>[x.notion_id,x.slug,x.id].includes(s.ref.id))?.name||s.ref.id) : s.transfer?'Fixture point → Fixture hotel · grab':'')):'';
              timeline.append(step);}
             if(!${JSON.stringify(!!options.omitBackups)}&&d.plan.alternatives.length){
               const details=document.createElement('details');details.className='itinerary-alternatives';details.innerHTML='<summary>備案（按需查看）</summary>';
               for(const a of d.plan.alternatives){const group=document.createElement('div');group.className='panel pad';
                 const target=a.target_segment_ids.map(id=>d.plan.segments.find(s=>s.id===id)?.label||id);
                 const actions={use_alternative:'改用備案，取代',skip_optional:'略過可選',return_or_rest:'返回或休息，調整'};
                 group.textContent=a.trigger_text+' '+actions[a.action]+' '+target.join('、');
                 for(const s of a.replacement_segments){const row=document.createElement('div');row.className='step';row.dataset.segmentId=s.id;
                   row.dataset.refType=s.ref?.type||'';row.dataset.refId=s.ref?.id||'';row.textContent=s.label;group.append(row);}
                 details.append(group);}p.append(details);
             }
             root.append(p);}
        });</script></body></html>`});
      return route.abort();
    });
    let clock=0;
    const result=await verifySite({request,page,siteUrl:localUrl,apiOrigin:localUrl,now:()=>clock,
      sleep:async ms=>{clock+=ms},budgetMs:options.foreverBody?1000:5000,intervalMs:1000,
      screenshotPath:options.delayedFinal||options.foreverBody?'/tmp/opencode/task7-deadline.png':undefined});
    await run(result,page,{navigations,clock});
  } finally {await browser.close();}
}

test('fallback never certifies live content',()=>withPage({fallback:true},r=>assert.equal(r.status,'FALLBACK')));
test('API hash correct but stale visible restaurant fails',()=>{
  const stale=structuredClone(fixture);stale.data.refs.foods[0].name='old restaurant';
  return withPage({rendered:stale},r=>assert.notEqual(r.status,'PASS'));
});
test('matching hooks but blank visible copy fails',()=>withPage({blank:true},r=>assert.notEqual(r.status,'PASS')));
test('correct consumed hash/refs but stale secondary activity text fails',()=>withPage({staleActivity:true},r=>{
  assert.equal(r.status,'CONTENT_MISMATCH');
  assert.match(r.checks.day_error,/visible segment phuquoc-2026:2026-10-10\/start/);
}));
test('valid consumed API and visible DOM pass',()=>withPage({},r=>assert.equal(r.status,'PASS',JSON.stringify(r.checks))));
test('missing visible backups cannot pass',()=>withPage({omitBackups:true},r=>{
  assert.equal(r.status,'CONTENT_MISMATCH');assert.equal(r.checks.alternatives,false);
}));
test('a 404 card target cannot pass with correct link hrefs',()=>withPage({card404:true},r=>{
  assert.equal(r.status,'CONTENT_MISMATCH');assert.equal(r.checks.card_navigation,false);
}));
test('awaits delayed body of the page-observed API response before classifying',()=>withPage({delayBodyMs:200},r=>assert.equal(r.status,'PASS',JSON.stringify(r.checks))));
test('final attempt with forever-pending navigation respects remaining budget',async()=>{
  const start=Date.now();
  await withPage({delayedFinal:true,environment:'test'},(r,_page,{navigations,clock})=>{
    assert.notEqual(r.status,'PASS');assert.deepEqual(r.artifacts,[]);
     assert.ok(r.observations.filter(x=>x.status).length<=3);
    assert.match(r.checks.navigation,/SITE_CHECK_DEADLINE/);
     assert.equal(navigations,3);assert.ok(clock>=1000 && clock<=2000);
  });
   assert.ok(Date.now()-start<6000,'a pending final navigation must not hang the verifier');
});
test('a forever-pending observed response body cannot hang or be certified',async()=>{
  let bodies=0;const start=Date.now();
  await withPage({foreverBody:true,bodyStarted:()=>bodies++},r=>{
    assert.ok(bodies>0,'the intercepted page response body was actually requested');
    assert.notEqual(r.status,'PASS');assert.deepEqual(r.artifacts,[]);
    assert.match(r.checks.navigation,/SITE_CHECK_DEADLINE/);
  });
  assert.ok(Date.now()-start<3500);
});
test('real B2 reader renders the consumed fixture and passes visible assertions',()=>withPage({realReader:true},r=>assert.equal(r.status,'PASS',JSON.stringify(r.checks))));
test('wrong environment, JS error, unreachable, stale build and overflow classify safely',async()=>{
  for(const [opts,status] of [[{environment:'test'},'CONTENT_MISMATCH'],[{jsError:true},'ERROR'],
    [{unreachable:true},'UNREACHABLE'],[{build:'sha256:bad'},'CONTENT_MISMATCH'],
    [{overflow:true},'CONTENT_MISMATCH'],[{cached:true},'CONTENT_MISMATCH'],
    [{foreign:true},'CONTENT_MISMATCH']])
    await withPage(opts,r=>assert.equal(r.status,status,JSON.stringify(r.checks)));
});
