import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {chromium} from 'playwright';

test('smoke readiness awaits this navigation, not a delayed previous response',async()=>{
  // Execute the actual workflow probe against a real browser, including its
  // request/response events. This catches stale-response certification on reload.
  const workflow=await readFile(new URL('../../.github/workflows/data-smoke.yml',import.meta.url),'utf8');
  const probe=workflow.split('// Itinerary readiness probe')[1].split('// Poll for this commit:')[0];
  const makeProbe=new Function('page','// Itinerary readiness probe'+probe+'\nreturn {ready,diagnostic:()=>typeof readyDiagnostic===\'undefined\'?\'\':readyDiagnostic};');
  const api='https://br-silent-haze-b3xw64tm-phqreadonly.compute.c-4.ap-southeast-1.aws.neon.tech/api/itinerary';
  const revision='phq1:'+'a'.repeat(64);
  const html=`<div data-itinerary data-source="live" data-content-revision="${revision}"><button class="date-tab" role="tab">10-10</button></div><script>fetch(${JSON.stringify(api)}).catch(()=>{});</script>`;
  const browser=await chromium.launch({headless:true});
  let releaseOld,releaseCurrent;
  const oldBodyHeld=new Promise(r=>{releaseOld=r;});
  const currentRequestHeld=new Promise(r=>{releaseCurrent=r;});
  try {
    const page=await browser.newPage();
    let responses=0,calls=0,signalFirst,signalSecond;
    const firstSeen=new Promise(r=>{signalFirst=r;});
    const secondStarted=new Promise(r=>{signalSecond=r;});
    page.on('response',response=>{
      if(response.url()!==api||++responses!==1)return;
      const json=response.json.bind(response);
      response.json=async()=>{await oldBodyHeld;return json();};
      signalFirst();
    });
    const observation=makeProbe(page);
    await page.route('http://smoke.test/',route=>route.fulfill({contentType:'text/html',body:html}));
    await page.route(api,async route=>{
      if(++calls===1)return route.fulfill({json:{meta:{content_revision:revision}},headers:{'access-control-allow-origin':'*'}});
      signalSecond();await currentRequestHeld;
      return route.fulfill({contentType:'application/json',body:'invalid JSON',headers:{'access-control-allow-origin':'*'}});
    });
    await page.goto('http://smoke.test/',{waitUntil:'domcontentloaded'});
    await firstSeen;
    await page.reload({waitUntil:'domcontentloaded'});
    await secondStarted;
    releaseOld();
    let settled=false;
    const result=observation.ready().then(value=>{settled=true;return value;});
    await page.waitForTimeout(100);
    assert.equal(settled,false,'previous-document response must not certify the current document');
    releaseCurrent();
    assert.equal(await result,false,'invalid current API body cannot pass with stale live DOM');
    assert.match(observation.diagnostic(),/API body/);
  } finally {releaseOld();releaseCurrent();await browser.close();}
});
