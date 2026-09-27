// C3 local-only chain: rollback PG18 edit -> real projection -> generated candidate
// -> Chromium verifier -> fake GitHub request/publish -> immutable result read.
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createServer} from 'node:http';
import {readFile,mkdtemp} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve,sep} from 'node:path';
import {chromium} from 'playwright';
import {verifySite} from './site-check-browser.mjs';
import {readTrustedRequest,publishResult} from './site-check-publish.mjs';

const env=await readFile('/tmp/opencode/phq-pg18-test-env','utf8');
assert.match(env,/ITINERARY_TEST_ALLOW_WRITE=1/);
const fixture=JSON.parse(execFileSync('python3',['tools/verify/itinerary_e2e_db.py'],{
  env:{...process.env,PYTHONPATH:`tools/verify:${process.cwd()}`,PYTHONUTF8:'1'},encoding:'utf8'}));
const {envelope,receipt,audit}=fixture;
const changed=receipt.changed_day_ids[0];
assert.equal(audit.new.plan.segments.find(s=>s.kind==='meal').ref.id,'fixture-unrelated');
const day=envelope.data.days.find(d=>d.id===changed);
const meals=day.plan.segments.filter(s=>s.kind==='meal').map(s=>({segment_id:s.id,ref:s.ref}));
const transfers=day.plan.segments.filter(s=>s.kind==='transfer').map(s=>({segment_id:s.id,
  from_ref:s.transfer.from_ref,to_ref:s.transfer.to_ref,mode:s.transfer.mode}));
const id=receipt.request_id, requestSha='a'.repeat(40),parent='b'.repeat(40),main='c'.repeat(40),blobSha='d'.repeat(40);
const request={schema_version:1,request_id:id,target:'production',itinerary_id:'phuquoc-2026',
  expected_content_revision:receipt.content_revision,changed_day_ids:[changed],
  expected:[{day_id:changed,main_card_slug:day.main_card_slug,meals,transfers}]};
const requestPath=`bridge/site-check/requests/${id}.json`;
const resultPath=`requests/${id}/result.json`;
const trees=new Map([['root',new Map()]]),commits=new Map([[main,{tree:'root'}]]),blobs=new Map();
let head=null, serial=0;
// Deliberately in-memory fake GitHub. No token, network request, remote branch or Actions run.
const github={request:async(method,url,body)=>{
  if(url.endsWith('/actions/runs/17'))return {id:17,workflow_id:42,event:'push',name:'chat site-check request',status:'completed',conclusion:'success',head_sha:requestSha,head_branch:`chat-site-check/${id}`,head_repository:{full_name:'ga815647/phu-quoc-2026-mobile'}};
  if(url.endsWith('/actions/workflows/chat-site-check-request.yml'))return {id:42};
  if(url.endsWith(`/commits/${requestSha}?per_page=100&page=1`))return {sha:requestSha,parents:[{sha:parent}],files:[{filename:requestPath,status:'added',sha:blobSha}]};
  if(url.endsWith(`/commits/${requestSha}?per_page=100&page=2`))return {files:[]};
  if(url.endsWith('/git/ref/heads/main'))return {object:{sha:main}};
  if(url.includes(`/compare/${parent}...${main}`))return {status:'ahead'};
  if(url.endsWith(`/git/blobs/${blobSha}`))return {encoding:'base64',content:Buffer.from(JSON.stringify(request)).toString('base64')};
  if(url.endsWith('/git/ref/heads/site-check-results')){
    if(!head)throw Object.assign(Error('not found'),{status:404});return {object:{sha:head}};
  }
  if(method==='GET'&&url.includes('/git/commits/'))return {tree:{sha:commits.get(url.split('/').at(-1)).tree}};
  if(method==='GET'&&url.includes('/contents/')){
    const path=url.split('/contents/')[1].split('?')[0],at=url.split('ref=')[1];
    const key=trees.get(commits.get(at).tree).get(path);
    if(!key)throw Object.assign(Error('not found'),{status:404});
    return {encoding:'base64',content:Buffer.from(blobs.get(key)).toString('base64')};
  }
  if(method==='POST'&&url.endsWith('/git/blobs')){const sha=`blob${++serial}`;blobs.set(sha,body.content);return {sha};}
  if(method==='POST'&&url.endsWith('/git/trees')){const sha=`tree${++serial}`,entries=new Map(trees.get(body.base_tree));
    for(const row of body.tree)entries.set(row.path,row.sha);trees.set(sha,entries);return {sha};}
  if(method==='POST'&&url.endsWith('/git/commits')){const sha=`commit${++serial}`;commits.set(sha,body);return {sha};}
  if(method==='POST'&&url.endsWith('/git/refs')){assert.equal(head,null);head=body.sha;return {object:{sha:head}};}
  throw Error(`Unexpected fake GitHub call: ${method} ${url}`);
}};
const trusted=await readTrustedRequest({event:{workflow_run:{id:17}},github});
assert.deepEqual(trusted.request,request);
const directory=await mkdtemp(join(tmpdir(),'phq-c3-'));
let server,browser;
try {
  server=createServer(async(req,res)=>{
    const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
    if(pathname==='/api/itinerary'){res.writeHead(200,{'Content-Type':'application/json','Access-Control-Allow-Origin':'*'}).end(JSON.stringify(envelope));return;}
    if(pathname==='/api/cards'){const cards=JSON.parse(await readFile('data/cards.json','utf8'));
      res.writeHead(200,{'Content-Type':'application/json','Access-Control-Allow-Origin':'*'}).end(JSON.stringify({data:cards,meta:{fetched_at:'2026-09-27T00:00:00Z'}}));return;}
    // Candidate filename aliases simulate the production paths the verifier expects.
    const file=resolve(directory,'.'+(pathname==='/'?'/data-candidate.html':pathname==='/card.html'?'/card-candidate.html':pathname));
    if(!file.startsWith(directory+sep)){res.writeHead(403).end();return;}
    try {let value=await readFile(file);if(pathname==='/')value=Buffer.from(value.toString().replaceAll('card-candidate.html','card.html'));
      res.writeHead(200,{'Content-Type':file.endsWith('.mjs')?'text/javascript':file.endsWith('.json')?'application/json':'text/html'}).end(value);
    }catch {res.writeHead(404).end();}
  });
  await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
  const origin=`http://127.0.0.1:${server.address().port}`;
  execFileSync('python3',['tools/build_site.py','--api-base',origin,'--out-dir',directory,'--itinerary-mode','candidate'],{stdio:'pipe'});
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true,serviceWorkers:'block'});
  // The fixture carries production-shaped metadata solely to exercise the strict
  // verifier; it does NOT show an actual production server or deployed content.
  const result=await verifySite({request:trusted.request,page,siteUrl:origin+'/',apiOrigin:origin,
    budgetMs:15000,intervalMs:15000});
  if(result.status!=='PASS')console.error(JSON.stringify(await page.locator('a.link-card').evaluateAll(ns=>ns.map(n=>({href:n.href,w:n.getBoundingClientRect().width,h:n.getBoundingClientRect().height})))));
  assert.equal(result.status,'PASS',JSON.stringify(result.checks));
  assert.equal(result.observed_content_revision,receipt.content_revision);
  result.request_commit=trusted.requestSha;result.test_commit=trusted.testSha;result.run_id=71;
  const published=await publishResult({github,requestSha:trusted.requestSha,result,markdown:'# Local fixture only\n'});
  assert.equal(published.path,resultPath);
  const immutable=await github.request('GET',`/repos/ga815647/phu-quoc-2026-mobile/contents/${resultPath}?ref=${published.commitSha}`);
  const readback=JSON.parse(Buffer.from(immutable.content,'base64').toString('utf8'));
  assert.equal(readback.status,'PASS');
  assert.equal(readback.request_commit,requestSha);
  assert.equal(readback.observed_content_revision,receipt.content_revision);
  assert.equal(readback.request_id,id);
  console.log('LOCAL FIXTURE PASS: PG18 rollback update/audit -> public view/export -> generated candidate -> Chromium verifier -> fake GitHub immutable result');
} finally {
  await browser?.close();
  if(server)await new Promise(ok=>server.close(ok));
}
