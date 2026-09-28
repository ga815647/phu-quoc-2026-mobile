import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readTrustedRequest,publishResult,artifactFailureResult} from './site-check-publish.mjs';

const id='1f4be2aa-e9b5-4a8a-8f1c-68c6d7eef67a',sha='a'.repeat(40),parent='b'.repeat(40),main='c'.repeat(40);
const path=`bridge/site-check/requests/${id}.json`;
const request={schema_version:1,request_id:id,target:'production',itinerary_id:'phuquoc-2026',
  expected_content_revision:`phq1:${'a'.repeat(64)}`,changed_day_ids:['phuquoc-2026:2026-10-12'],
  expected:[{day_id:'phuquoc-2026:2026-10-12',main_card_slug:'cable',meals:[],transfers:[]}]};

test('reads immutable blob and provenance from GitHub, not event claims',async()=>{
  const calls=[];
  const github={request:async(method,url)=>{
    calls.push(url);
    if(url.endsWith(`/actions/runs/17`))return {id:17,workflow_id:42,event:'push',name:'chat site-check request',status:'completed',conclusion:'success',head_sha:sha,head_branch:`chat-site-check/${id}`,head_repository:{full_name:'ga815647/phu-quoc-2026-mobile'}};
    if(url.endsWith('/actions/workflows/chat-site-check-request.yml'))return {id:42};
    if(url.endsWith(`/commits/${sha}?per_page=100&page=1`))return {sha,parents:[{sha:parent}],files:[{filename:path,status:'added',sha:'d'.repeat(40)}]};
    if(url.endsWith(`/commits/${sha}?per_page=100&page=2`))return {files:[]};
    if(url.includes(`/compare/${parent}...${main}`))return {status:'ahead',total_commits:1};
    if(url.endsWith('/git/ref/heads/main'))return {object:{sha:main}};
    if(url.endsWith('/git/blobs/'+'d'.repeat(40)))return {encoding:'base64',content:Buffer.from(JSON.stringify(request)).toString('base64')};
    throw Error(url);
  }};
  const value=await readTrustedRequest({event:{workflow_run:{id:17,head_sha:'f'.repeat(40)}},github});
  assert.equal(value.requestSha,sha);assert.equal(value.testSha,main);
  assert.deepEqual(value.request,request);assert.ok(calls.some(p=>p.includes('/git/blobs/')));
});

test('rejects hidden second-page files and wrong production provenance',async()=>{
  for(const cause of ['extra','fork','ancestry','workflow']){
    const github={request:async(method,url)=>{
      if(url.endsWith('/actions/runs/17'))return {id:17,workflow_id:cause==='workflow'?99:42,event:'push',name:'chat site-check request',status:'completed',
        conclusion:'success',head_sha:sha,head_branch:`chat-site-check/${id}`,
        head_repository:{full_name:cause==='fork'?'attacker/fork':'ga815647/phu-quoc-2026-mobile'}};
      if(url.endsWith('/actions/workflows/chat-site-check-request.yml'))return {id:42};
      if(url.endsWith(`/commits/${sha}?per_page=100&page=1`))return {sha,parents:[{sha:parent}],files:[{filename:path,status:'added',sha:'d'.repeat(40)}]};
      if(url.endsWith(`/commits/${sha}?per_page=100&page=2`))return {files:cause==='extra'?[{filename:'tools/evil.js',status:'added'}]:[]};
      if(url.endsWith('/git/ref/heads/main'))return {object:{sha:main}};
      if(url.includes('/compare/'))return {status:cause==='ancestry'?'diverged':'ahead'};
      if(url.includes('/git/blobs/'))return {encoding:'base64',content:Buffer.from(JSON.stringify(request)).toString('base64')};
      throw Error(url);
    }};
    await assert.rejects(readTrustedRequest({event:{workflow_run:{id:17}},github}),/INVALID_REQUEST/);
  }
});

test('failed artifact upload produces ERROR without screenshot or PASS',()=>{
  const result=artifactFailureResult({requestId:id,requestSha:sha,testSha:main,runID:17});
  assert.equal(result.status,'ERROR');assert.deepEqual(result.artifacts,[]);
  assert.equal(result.checks.artifact_upload,'failed');
});

test('concurrent CAS retries from fresh head preserve both request results',async()=>{
  const trees=new Map(),blobs=new Map(),commits=new Map();let head='e'.repeat(40),serial=0;
  trees.set('root',new Map());commits.set(head,{tree:'root'});
  const github={request:async(method,url,body)=>{
    if(method==='GET'&&url.endsWith('/git/ref/heads/site-check-results'))return {object:{sha:head}};
    if(method==='GET'&&url.includes('/git/commits/'))return {tree:{sha:commits.get(url.split('/').at(-1)).tree}};
    if(method==='GET'&&url.includes('/contents/')){
      const key=url.split('/contents/')[1].split('?')[0],at=url.split('ref=')[1];
      const blob=trees.get(commits.get(at).tree).get(key);
      if(!blob)throw Object.assign(Error('missing'),{status:404});
      return {encoding:'base64',content:Buffer.from(blobs.get(blob)).toString('base64')};
    }
    if(method==='POST'&&url.endsWith('/git/blobs')){const sha=`blob${++serial}`;blobs.set(sha,body.content);return {sha};}
    if(method==='POST'&&url.endsWith('/git/trees')){const sha=`tree${++serial}`,entries=new Map(trees.get(body.base_tree));
      for(const f of body.tree)entries.set(f.path,f.sha);trees.set(sha,entries);return {sha};}
    if(method==='POST'&&url.endsWith('/git/commits')){const sha=`commit${++serial}`;commits.set(sha,body);return {sha};}
    if(method==='PATCH'&&url.endsWith('/git/refs/heads/site-check-results')){
      const commit=commits.get(body.sha);
      if(commit.parents[0]!==head)throw Object.assign(Error('CAS'),{status:422});
      assert.equal(body.force,false);head=body.sha;
      return {object:{sha:head}};
    }
    throw Error(`${method} ${url}`);
  }};
  const other='99f2ab99-96c0-48d6-a347-07e4d196fe2f';
  const result=id=>({request_id:id,request_commit:sha,run_id:17,status:'PASS'});
  // Force the two writers to read the same HEAD before either creates a tree.
  let reads=0;let unblock;const gate=new Promise(resolve=>unblock=resolve);
  const parallel={request:async(...args)=>{
    const value=await github.request(...args);
    if(args[0]==='GET'&&args[1].endsWith('/git/ref/heads/site-check-results')&&++reads<=2){if(reads===2)unblock();await gate;}
    return value;
  }};
  await Promise.all([id,other].map(request_id=>publishResult({github:parallel,requestSha:sha,result:result(request_id),markdown:'fixture'})));
  const files=trees.get(commits.get(head).tree);
  assert.equal(files.size,4);
  assert.ok(files.has(`requests/${id}/result.json`));assert.ok(files.has(`requests/${other}/result.json`));
  assert.equal((await publishResult({github,requestSha:sha,result:result(id),markdown:'fixture'})).existing,true);
  await assert.rejects(publishResult({github,requestSha:'f'.repeat(40),result:{...result(id),request_commit:'f'.repeat(40)},markdown:'fixture'}),/RESULT_CONFLICT/);
});
