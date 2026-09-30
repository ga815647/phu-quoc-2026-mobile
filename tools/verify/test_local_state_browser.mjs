import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {execFileSync} from 'node:child_process';
import {readFile, mkdtemp, rm} from 'node:fs/promises';
import {resolve, join, extname, sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const root=fileURLToPath(new URL('../..',import.meta.url));
const pool=JSON.parse(await readFile(join(root,'data/pool.json'),'utf8'));
const fixture=JSON.parse(await readFile(new URL('./fixtures/itinerary-envelope.json',import.meta.url)));
const foodId='bun-ken-ut-luom';
const oldState={
  'phq-v2-slots':'{"10/12":"Safari"}',
  'phq-v3-slots':'{"10/13":"VinWonders"}',
  'phq-v2-food-eaten':JSON.stringify({[foodId]:true}),
  'phq-v3-food-eaten':JSON.stringify({[foodId]:true}),
};

// Catch a returned editor, any retired-key access, or an imported old eaten value.
// Exercise the generated page and real browser storage, not source-text matches.
for(const mode of ['candidate','readonly','legacy']) {
  test(`${mode}: retired slots are inert and eaten starts clean then persists`,async()=>{
    const site=await mkdtemp('/tmp/opencode/phq-local-state-');
    const server=createServer(async(req,res)=>{
      const path=new URL(req.url,'http://localhost').pathname;
      try {
        if(path.startsWith('/mock-api/api/')) {
          const endpoint=path.split('/').at(-1);
          const data=endpoint==='itinerary'?fixture: {
            data:JSON.parse(await readFile(join(root,`data/${endpoint}.json`),'utf8')),
            meta:{source:'fixture',fetched_at:'2026-09-30T00:00:00Z'},
          };
          res.setHeader('Content-Type','application/json');res.end(JSON.stringify(data));return;
        }
        const file=resolve(site,'.'+path);
        if(!file.startsWith(site+sep)){res.writeHead(403).end();return;}
        res.setHeader('Content-Type',extname(file)==='.mjs'?'text/javascript':extname(file)==='.json'?'application/json':'text/html');
        res.end(await readFile(file));
      } catch {res.writeHead(404).end();}
    });
    await new Promise(r=>server.listen(0,'127.0.0.1',r));
    const origin=`http://127.0.0.1:${server.address().port}`;
    let browser;
    try {
      execFileSync('python3',['tools/build_site.py','--api-base',origin+'/mock-api',
        '--out-dir',site,'--itinerary-mode',mode],{cwd:root,stdio:'pipe'});
      browser=await chromium.launch({headless:true});
      // Also cover devices whose old v2 values have not yet been migrated.
      for(const state of [oldState,Object.fromEntries(Object.entries(oldState).filter(([key])=>key.startsWith('phq-v2-')))]) {
        const context=await browser.newContext({viewport:{width:390,height:844},
          storageState:{cookies:[],origins:[{origin,localStorage:Object.entries(state).map(([name,value])=>({name,value}))}]}});
        const page=await context.newPage(),errors=[];
        page.on('pageerror',e=>errors.push(String(e)));
        page.on('console',msg=>{if(msg.type()==='error')errors.push(msg.text());});
        page.on('dialog',dialog=>dialog.accept());
        await page.addInitScript(()=>{
          window.retiredStorageAccess=[];
          for(const method of ['getItem','setItem','removeItem']) {
            const original=Storage.prototype[method];
            Storage.prototype[method]=function(key,...args){
              if(/^phq-v[23]-(slots|food-eaten)$/.test(key))window.retiredStorageAccess.push([method,key]);
              return original.call(this,key,...args);
            };
          }
          const clear=Storage.prototype.clear;
          Storage.prototype.clear=function(){window.retiredStorageAccess.push(['clear']);return clear.call(this);};
        });
        await page.goto(origin+'/data-candidate.html');
        await page.locator('a.link-card').first().waitFor();
        if(mode!=='legacy')await page.locator('[data-itinerary][data-source="live"]').waitFor();
        assert.equal(await page.locator('#foodProgress').innerText(),`已吃 0 / ${pool.length}`);
        assert.equal(await page.locator('select[data-day],#resetSlots,#slotMigrated,.slot-list').count(),0);
        assert.doesNotMatch(await page.locator('body').innerText(),/舊本機暫排|清除暫排|暫排只存/);
        assert.deepEqual(await page.evaluate(()=>window.retiredStorageAccess),[]);
        const button=page.locator(`[data-food-id="${foodId}"] .eaten-btn`);
        assert.equal(await button.getAttribute('aria-pressed'),'false');
        await button.click();
        assert.equal(await page.locator('#foodProgress').innerText(),`已吃 1 / ${pool.length}`);
        assert.deepEqual(await page.evaluate(()=>window.retiredStorageAccess),[]);
        await page.reload();
        assert.equal(await button.getAttribute('aria-pressed'),'true');
        assert.equal(await page.locator('#foodProgress').innerText(),`已吃 1 / ${pool.length}`);
        await page.selectOption('#filterEaten','eaten');
        assert.deepEqual(await page.locator('[data-food-id]:not(.hidden)').evaluateAll(els=>els.map(el=>el.dataset.foodId)),[foodId]);
        await page.locator('#resetFood').click();
        assert.equal(await page.locator('#foodProgress').innerText(),`已吃 0 / ${pool.length}`);
        assert.equal(await page.locator('#foodEmpty').isVisible(),true);
        await page.reload();
        if(mode!=='legacy')await page.locator('[data-itinerary][data-source="live"]').waitFor();
        assert.equal(await button.getAttribute('aria-pressed'),'false');
        for(const width of [320,390,430]) {
          await page.setViewportSize({width,height:844});
          assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth)<=1,`overflow ${width}`);
        }
        assert.equal(await page.locator('a.link-card').count(),5);
        if(mode!=='legacy')assert.equal(await page.locator('[data-itinerary-day]').count(),6);
        assert.deepEqual(await page.evaluate(()=>window.retiredStorageAccess),[]);
        // Read through storageState so the verification itself is not a recorded old-key read.
        const stored=(await context.storageState()).origins.find(o=>o.origin===origin).localStorage;
        for(const [key,value] of Object.entries(state))assert.equal(stored.find(row=>row.name===key)?.value,value);
        assert.equal(stored.find(row=>row.name==='phq-v4-food-eaten')?.value,'{}');
        assert.deepEqual(errors,[]);
        await context.close();
      }
    } finally {
      await browser?.close();await new Promise(r=>server.close(r));
      await rm(site,{recursive:true,force:true});
    }
  });
}
