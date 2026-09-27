import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createServer} from 'node:http';
import {execFileSync} from 'node:child_process';
import {resolve,join,sep,extname} from 'node:path';

const site=resolve(process.argv[process.argv.indexOf('--site')+1]||'/tmp/opencode/phq-itinerary-candidate');
const fixture=JSON.parse(await readFile(new URL('./fixtures/itinerary-envelope.json',import.meta.url)));
const staticHandler=directory=>async(req,res)=>{
  const path=resolve(directory,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));
  if(!path.startsWith(directory+sep)) {res.writeHead(403).end();return;}
  try {const file=await readFile(path);res.setHeader('Content-Type',extname(path)==='.mjs'?'text/javascript':extname(path)==='.json'?'application/json':'text/html');res.end(file);}
  catch {
    if(path.startsWith(join(directory,'data')+sep) && !path.endsWith('itinerary.json')) {
      try {res.setHeader('Content-Type','application/json');res.end(await readFile(resolve('data',path.slice(join(directory,'data').length+1))));return;} catch {}
    }
    res.writeHead(404).end();
  }
};
const server=createServer(staticHandler(site));
await new Promise(r=>server.listen(0,'127.0.0.1',r));
let browser,readonlyServer;
try {
  browser=await chromium.launch({headless:true});
  const origin=`http://127.0.0.1:${server.address().port}`;
  const page=await browser.newPage({viewport:{width:390,height:844}});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.clock.install({time:new Date('2026-10-12T05:00:00Z')});
  const slot='{"10/12":"Starfish（需條件全通過）"}';
  await page.addInitScript(slot=>localStorage.setItem('phq-v3-slots',slot),slot);
  await page.route('**/mock-api/api/**',async route=>{
    const url=route.request().url();
    if(url.endsWith('/api/itinerary'))return route.fulfill({json:fixture,headers:{'access-control-allow-origin':'*'}});
    return route.abort();
  });
  await page.route('**/data/itinerary.json',route=>route.fulfill({json:fixture}));
  await page.goto(origin+'/data-candidate.html');
  await page.locator('[data-itinerary][data-source="live"]').waitFor();
  assert.equal(await page.locator('[data-itinerary-day]').count(),6);
  assert.match(await page.locator('#todayTitle').innerText(),/測試纜車/);
  assert.match(await page.locator('#vietnamDateLine').innerText(),/2026-10-12/);
  assert.equal(await page.evaluate(()=>localStorage.getItem('phq-v3-slots')),slot);
  assert.equal(await page.locator('a.link-card').count(),5);
  assert.match(await page.locator('#itinerary').innerText(),/舊本機暫排/);
  assert.equal(await page.locator('[data-itinerary-day="phuquoc-2026:2026-10-12"]').getAttribute('data-main-card'),'cable');
  await page.getByRole('tab',{name:'10-12'}).click();
  const scheduled=await page.locator('.day-panel.active [data-segment-id="main"]').innerText();
  assert.match(scheduled,/已核對時刻/);
  assert.match(scheduled,/測試預約通知/);
  assert.match(scheduled,/核實 2026-09-25/);
  assert.match(scheduled,/條件：測試開放狀態/);
  await page.locator('.day-panel.active').getByRole('link',{name:'看行程卡'}).click();
  await page.waitForURL('**/card-candidate.html?slug=cable');
  await page.locator('#cardMount .detail-hero').waitFor();
  await page.locator('#backLink').click();
  await page.waitForURL('**/data-candidate.html#itinerary');
  await page.locator('[data-itinerary][data-source="live"]').waitFor();
  await page.getByRole('tab',{name:'10-11'}).click();
  assert.match(await page.locator('.day-panel.active [data-segment-id="main"] .time').innerText(),/預留（非實測）/);
  await page.getByRole('tab',{name:'10-10'}).click();
  assert.match(await page.locator('.day-panel.active').innerText(),/測試店家/);
  assert.match(await page.locator('.day-panel.active').innerText(),/次日|待估/);
  const estimate=await page.locator('.day-panel.active [data-segment-id="start"]').innerText();
  assert.match(estimate,/估算（非實測）/);
  assert.match(estimate,/依據：測試估時紀錄/);
  assert.match(estimate,/核實 2026-08-01/);
  assert.match(estimate,/出發前重查/);
  assert.match(estimate,/條件：Rain/);
  assert.match(await page.locator('.day-panel.active [data-segment-id="optional-stop"]').innerText(),/順路加點.*可選，非必做/s);
  const meal=page.locator('.day-panel.active [data-segment-id="meal"]');
  assert.match(await meal.innerText(),/測試店家.*核實 2026-08-01.*出發前重查/s);
  const mealMap=meal.getByRole('link',{name:'地圖'});
  assert.equal(new URL(await mealMap.getAttribute('href')).searchParams.get('query'),'測試店家 富國島');
  const transfer=page.locator('[data-segment-id="go"]');
  assert.equal(await transfer.getAttribute('data-from-ref'),'point:fixture-point');
  assert.equal(await transfer.getAttribute('data-to-ref'),'base:hotel');
  assert.equal(await transfer.getAttribute('data-mode'),'grab');
  assert.equal(await page.locator('[data-segment-id="meal"]').getAttribute('data-ref-id'),'fixture-pool');
  assert.equal(await page.locator('[data-itinerary]').getAttribute('data-content-revision'),fixture.meta.content_revision);
  await page.locator('.itinerary-alternatives summary').click();
  const alternatives=await page.locator('.itinerary-alternatives').innerText();
  assert.match(alternatives,/Rain.*改用備案.*Start.*Rest/s);
  assert.match(alternatives,/孩子累了.*略過可選.*順路加點/s);
  assert.match(alternatives,/太晚出發.*返回或休息.*Go/s);
  const minHeight=await page.locator('#refreshItinerary,.date-tab,.itinerary-alternatives summary').evaluateAll(ns=>Math.min(...ns.map(n=>n.getBoundingClientRect().height)));
  assert.ok(minHeight>=41,`touch target ${minHeight}`);
  const build=JSON.parse(await readFile(join(site,'site-version.json'),'utf8')).build_id;
  assert.equal(await page.locator('html').getAttribute('data-site-build'),build);
  assert.ok(!errors.length,errors.join('\n'));
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth);
  assert.ok(overflow<=1,`horizontal overflow ${overflow}`);
  const eaten=page.locator('.food-card:not(.hidden) .eaten-btn').first();
  await eaten.click();
  assert.equal(await eaten.getAttribute('aria-pressed'),'true');
  const stored=await page.evaluate(()=>localStorage.getItem('phq-v3-food-eaten'));
  await page.reload();
  await page.locator('[data-itinerary][data-source="live"]').waitFor();
  assert.equal(await page.evaluate(()=>localStorage.getItem('phq-v3-food-eaten')),stored);
  await page.close();

  const fallback=await browser.newPage({viewport:{width:390,height:844}});
  await fallback.addInitScript(()=>{
    Object.defineProperty(window,'localStorage',{get(){throw Error('storage blocked');}});
  });
  await fallback.route('**/mock-api/api/**',route=>route.abort());
  await fallback.route('**/data/itinerary.json',route=>route.fulfill({json:fixture}));
  await fallback.goto(origin+'/data-candidate.html');
  await fallback.locator('[data-itinerary][data-source="fallback"]').waitFor();
  assert.match(await fallback.locator('[data-itinerary]').innerText(),/備援資料（非最新）.*匯出 2026-09-27T00:00:00Z/s);
  assert.equal(await fallback.locator('[data-itinerary-day]').count(),6);
  assert.match(await fallback.locator('#todayTitle').innerText(),/六日行程|今日/);
  await fallback.close();

  const unavailable=await browser.newPage();
  await unavailable.route('**/mock-api/api/**',route=>route.fulfill({json:{data:{},meta:{}}}));
  await unavailable.route('**/data/itinerary.json',route=>route.fulfill({json:{data:{},meta:{}}}));
  await unavailable.goto(origin+'/data-candidate.html');
  await unavailable.locator('[data-itinerary][data-source="unavailable"]').waitFor();
  assert.match(await unavailable.locator('[data-itinerary]').innerText(),/行程暫不可用/);
  assert.equal(await unavailable.locator('[data-itinerary-day]').count(),0);
  await unavailable.close();

  const race=await browser.newPage();
  const malicious=structuredClone(fixture);
  malicious.data.refs.foods[0].name='<img src=x onerror="window.__injected=1">';
  let calls=0,releaseFirst;
  const firstHeld=new Promise(resolve=>{releaseFirst=resolve;});
  await race.route('**/mock-api/api/**',async route=>{
    if(!route.request().url().endsWith('/api/itinerary'))return route.abort();
    const number=++calls;
    if(number===2)await firstHeld;
    const response=structuredClone(malicious);
    response.meta.fetched_at=number===3?'2026-09-29T00:00:00Z':'2026-09-27T00:00:00Z';
    await route.fulfill({json:response,headers:{'access-control-allow-origin':'*'}}).catch(()=>{});
  });
  await race.route('**/data/itinerary.json',route=>route.fulfill({json:fixture}));
  await race.goto(origin+'/data-candidate.html');
  await race.locator('[data-itinerary][data-source="live"]').waitFor();
  assert.equal(await race.evaluate(()=>window.__injected),undefined);
  await race.getByRole('tab',{name:'10-10'}).click();
  assert.match(await race.locator('.day-panel.active').innerText(),/<img src=x onerror/);
  await race.locator('#refreshItinerary').click();
  await race.locator('#refreshItinerary').click();
  await race.locator('[data-itinerary]').getByText(/2026-09-29T00:00:00Z/).waitFor();
  releaseFirst();
  await race.waitForTimeout(100);
  assert.match(await race.locator('[data-itinerary]').innerText(),/2026-09-29T00:00:00Z/);
  assert.equal(await race.evaluate(()=>window.__injected),undefined);
  await race.route('**/mock-api/api/**',route=>route.abort());
  await race.route('**/data/itinerary.json',route=>route.abort());
  await race.locator('#refreshItinerary').click();
  await race.locator('[data-itinerary][data-source="unavailable"]').waitFor();
  assert.equal(await race.locator('[data-itinerary-day]').count(),6);
  assert.match(await race.locator('#todayNext').innerText(),/非最新/);
  await race.locator('#refreshItinerary').click();
  await race.waitForTimeout(100);
  assert.equal(await race.locator('[data-itinerary] > .callout.red').count(),1);
  await race.close();

  const readonly=resolve(site,'../phq-itinerary-readonly');
  execFileSync('python3',['tools/build_site.py','--api-base','http://localhost:8000/mock-api','--out-dir',readonly,'--itinerary-mode','readonly'],{stdio:'pipe'});
  const readonlyHtml=await readFile(join(readonly,'data-candidate.html'),'utf8');
  assert.doesNotMatch(readonlyHtml,/id="resetSlots"|<select data-day=/);
  assert.match(readonlyHtml,/data-itinerary/);
  assert.notEqual(JSON.parse(await readFile(join(readonly,'site-version.json'))).build_id,build);
  readonlyServer=createServer(staticHandler(readonly));
  await new Promise(r=>readonlyServer.listen(0,'127.0.0.1',r));
  const roPage=await browser.newPage();
  await roPage.addInitScript(()=>Object.defineProperty(window,'localStorage',{get(){throw Error('storage blocked');}}));
  await roPage.route('**/mock-api/api/**',async route=>route.request().url().endsWith('/api/itinerary')
    ? route.fulfill({json:fixture,headers:{'access-control-allow-origin':'*'}}) : route.abort());
  await roPage.goto(`http://127.0.0.1:${readonlyServer.address().port}/data-candidate.html`);
  await roPage.locator('[data-itinerary][data-source="live"]').waitFor();
  assert.equal(await roPage.locator('[data-itinerary-day]').count(),6);
  assert.match(await roPage.locator('#todayTitle').innerText(),/六日行程|測試纜車/);
  assert.equal(await roPage.locator('#resetSlots').count(),0);
  await roPage.close();
  console.log('browser: six days, Today, fallback, races, storage, XSS, readonly, cards, eaten, build, mobile PASS');
} finally {await browser?.close();if(readonlyServer)await new Promise(r=>readonlyServer.close(r));await new Promise(r=>server.close(r));}
