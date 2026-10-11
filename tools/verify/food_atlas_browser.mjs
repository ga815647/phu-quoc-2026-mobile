// End-to-end display checks on the deployed, approved public projection.
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {readFile,mkdir} from 'node:fs/promises';
const base=(process.env.PHQ_SMOKE_BASE||'https://ga815647.github.io/phu-quoc-2026-mobile').replace(/\/$/,'');
const api='https://br-silent-haze-b3xw64tm-phqreadonly.compute.c-4.ap-southeast-1.aws.neon.tech';
const snapshot=JSON.parse(await readFile('data/itinerary.json','utf8'));
const pool=JSON.parse(await readFile('data/pool.json','utf8'));
const build=JSON.parse(await readFile('site-version.json','utf8'));
const browser=await chromium.launch({headless:true});
await mkdir('food-atlas-evidence',{recursive:true});
try{
  for(const mode of ['live','fallback']){
    const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,storageState:{cookies:[],origins:[{origin:new URL(base).origin,localStorage:[{name:'phq-v4-food-eaten',value:'{\"bun-ken-ut-luom\":true}'}]}]}});
    const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
    await page.clock.install({time:new Date('2026-10-11T05:00:00Z')});
    if(mode==='fallback')await context.route(api+'/**',route=>route.abort());
    const responsePromise=mode==='live'?page.waitForResponse(r=>r.url()===api+'/api/itinerary'):null;
    await page.goto(base+'/?food-atlas-check='+Date.now());
    const envelope=responsePromise?await(await responsePromise).json():snapshot;
    await page.locator(`[data-itinerary][data-source="${mode}"]`).waitFor();
    assert.equal(await page.locator('html').getAttribute('data-site-build'),build.build_id);
    assert.equal(await page.locator('[data-itinerary]').getAttribute('data-content-revision'),envelope.meta.content_revision);
    const refs=envelope.data.refs;
    let held=0,checked=0;
    for(const day of envelope.data.days){
      await page.getByRole('tab',{name:day.date.slice(5)}).click();
      const panel=page.locator(`[data-itinerary-day="${day.id}"]`);
      const alternatives=panel.locator('.itinerary-alternatives');
      if(await alternatives.count())await alternatives.locator(':scope > summary').click();
      for(const s of [...day.plan.segments,...day.plan.alternatives.flatMap(a=>a.replacement_segments)]){
        if(s.kind==='transfer'){
          const diningRefs=[s.transfer.from_ref,s.transfer.to_ref].filter(r=>['food','pool'].includes(r?.type));
          const states=diningRefs.map(r=>refs.foods.find(f=>f.notion_id===(r.type==='food'?r.id:refs.pool.find(p=>p.pool_key===r.id)?.notion_id))?.atlas_state);
          if(states.some(state=>state!=='ACTIVE'))assert.match(await panel.locator(`[data-segment-id="${s.id}"] .dining-status`).innerText(),states.includes('DEACTIVATED')?/已下架/:/待再確認.*暫停推薦/);
        }
        if(s.kind!=='meal')continue;checked++;
        const f=s.ref.type==='food'?refs.foods.find(f=>f.notion_id===s.ref.id):refs.foods.find(f=>f.notion_id===refs.pool.find(p=>p.pool_key===s.ref.id)?.notion_id);
        const step=panel.locator(`[data-segment-id="${s.id}"]`),text=await step.innerText();
        assert.equal(await step.getAttribute('data-ref-id'),s.ref.id);
        if(f?.atlas_state!=='ACTIVE'){
          assert.match(text,f?.atlas_state==='DEACTIVATED'?/已下架.*不列入用餐建議/:/待再確認.*暫停推薦/);
          if(f)held++;
        }
        assert.ok(text.includes(f?.last_verified?'營運核實 '+f.last_verified:'營運核實：未知'));
        if(f?.evidence_as_of)assert.ok(text.includes('資料查核 '+f.evidence_as_of));
        for(const detail of await step.locator('.itinerary-evidence').all())assert.equal(await detail.getAttribute('open'),null);
      }
    }
    assert.ok(checked>0,'expected itinerary meal coverage');
    assert.match(await page.locator('#todayDesc').innerText(),/待再確認.*暫停推薦/);
    assert.equal(await page.locator('[data-food-id]').count(),pool.length);
    assert.doesNotMatch(await page.locator('#foodPool').innerText(),/這趟優先完成/);
    await page.selectOption('#filterEaten','eaten');
    assert.deepEqual(await page.locator('[data-food-id]:not(.hidden)').evaluateAll(nodes=>nodes.map(n=>n.dataset.foodId)),['bun-ken-ut-luom']);
    assert.equal(await page.locator('.pool-divider:visible').count(),1);
    await page.selectOption('#filterEaten','');
    await page.getByRole('tab',{name:'10-10'}).click();
    const research=page.locator('.day-panel.active .itinerary-evidence').first();
    await research.locator('summary').click();
    assert.equal(await research.locator('.evidence-text').isVisible(),true);
    assert.equal(await research.locator('img,script,iframe').count(),0);
    for(const width of [320,390,430]){
      await page.setViewportSize({width,height:844});
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth)<=1,`overflow ${mode} ${width}`);
      assert.ok(await research.locator('summary').evaluate(e=>e.getBoundingClientRect().height)>=44);
      await page.screenshot({path:`food-atlas-evidence/${mode}-${width}.png`,fullPage:true});
    }
    await research.locator('summary').click();
    await page.reload();
    await page.locator(`[data-itinerary][data-source="${mode}"]`).waitFor();
    assert.equal(await page.evaluate(()=>localStorage.getItem('phq-v4-food-eaten')),'{"bun-ken-ut-luom":true}');
    assert.match(await page.locator('#foodProgress').innerText(),/已吃 1 \/ 20/);
    if(mode==='fallback'){
      assert.match(await page.locator('.itinerary-provenance').innerText(),new RegExp('匯出 '+snapshot.meta.exported_at.slice(0,10)));
      assert.match(await page.locator('#todayNext').innerText(),/備援資料/);
    }
    assert.deepEqual(errors,[]);
    console.log(`PASS ${mode}: ${held} held meals, dated evidence, filters, persistent device state, 320/390/430px`);
    await context.close();
  }
}finally{await browser.close();}
