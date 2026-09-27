import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import {validateRequest,UUID_RE,RESULT_BRANCH,SITE_URL} from './site-check-contract.mjs';

const repo='/repos/ga815647/phu-quoc-2026-mobile';
const sha=/^[0-9a-f]{40}$/;
const invalid=()=>{throw Error('INVALID_REQUEST');};
const missing=e=>e?.status===404;
const conflict=e=>e?.status===409||e?.status===422;
const branchId=run=>{
  const branch=run?.head_branch;
  const id=typeof branch==='string' && /^chat-site-check\/([0-9a-f-]+)$/.exec(branch)?.[1];
  return id&&UUID_RE.test(id)?id:null;
};

export async function readTrustedRequest({event,github}) {
  if(!Number.isSafeInteger(event?.workflow_run?.id))invalid();
  // The event is only a pointer: every provenance field is taken from the authenticated GitHub API.
  const run=await github.request('GET',`${repo}/actions/runs/${event.workflow_run.id}`);
  const workflow=await github.request('GET',`${repo}/actions/workflows/chat-site-check-request.yml`);
  const id=branchId(run);
  if(!id||run.event!=='push'||run.name!=='chat site-check request'||run.status!=='completed'||
    run.conclusion!=='success'||run.head_repository?.full_name!=='ga815647/phu-quoc-2026-mobile'||
    !Number.isSafeInteger(workflow.id)||run.workflow_id!==workflow.id||!sha.test(run.head_sha))invalid();
  const requestSha=run.head_sha;
  const commit=await github.request('GET',`${repo}/commits/${requestSha}?per_page=100&page=1`);
  const files=commit.files;
  if(commit.sha!==requestSha||commit.parents?.length!==1||!sha.test(commit.parents[0].sha)||
    !Array.isArray(files)||files.length!==1||files[0].filename!==`bridge/site-check/requests/${id}.json`||
    files[0].status!=='added'||!sha.test(files[0].sha))invalid();
  // Paginated commit files: rejecting any subsequent file prevents the first-page-only bypass.
  const next=await github.request('GET',`${repo}/commits/${requestSha}?per_page=100&page=2`);
  if(!Array.isArray(next.files)||next.files.length)invalid();
  const mainRef=await github.request('GET',`${repo}/git/ref/heads/main`);
  const testSha=mainRef?.object?.sha;
  if(!sha.test(testSha))invalid();
  const ancestry=await github.request('GET',`${repo}/compare/${commit.parents[0].sha}...${testSha}`);
  if(!['identical','ahead'].includes(ancestry.status))invalid();
  const blob=await github.request('GET',`${repo}/git/blobs/${files[0].sha}`);
  if(blob.encoding!=='base64'||typeof blob.content!=='string')invalid();
  const raw=Buffer.from(blob.content.replace(/\s/g,''),'base64');
  if(raw.toString('base64')!==blob.content.replace(/\s/g,'') || raw.byteLength>128*1024)invalid();
  const request=validateRequest(raw,{repository:'ga815647/phu-quoc-2026-mobile',event:run.event,
    branch:run.head_branch,requestSha,parents:[commit.parents[0].sha],mainAncestor:true,
    files:files.map(f=>({filename:f.filename,status:f.status}))});
  return {request,requestSha,testSha};
}

const content=async(github,path,head)=>{
  try {const file=await github.request('GET',`${repo}/contents/${path}?ref=${head}`);
    if(file.encoding!=='base64')throw Error('INVALID_RESULT');
    return Buffer.from(file.content.replace(/\s/g,''),'base64').toString('utf8');
  }catch(e){if(missing(e))return null;throw e;}
};

export async function publishResult({github,requestSha,result,markdown}) {
  if(!sha.test(requestSha)||!UUID_RE.test(result?.request_id)||result.request_commit!==requestSha||
    !['PASS','CONTENT_MISMATCH','FALLBACK','UNREACHABLE','INVALID_REQUEST','SUPERSEDED','ERROR'].includes(result.status)||
    typeof markdown!=='string'||!Number.isSafeInteger(result.run_id))throw Error('INVALID_RESULT');
  const prefix=`requests/${result.request_id}`,jsonPath=`${prefix}/result.json`,mdPath=`${prefix}/result.md`;
  for(let attempt=0;attempt<3;attempt++){
    let head;
    try {head=(await github.request('GET',`${repo}/git/ref/heads/${RESULT_BRANCH}`)).object.sha;}
    catch(e){if(!missing(e))throw e;head=null;}
    if(head){
      const existing=await content(github,jsonPath,head);
      if(existing!==null){
        const previous=JSON.parse(existing);
        if(previous.request_commit===requestSha)return {commitSha:head,path:jsonPath,existing:true};
        throw Error('RESULT_CONFLICT');
      }
    }
    const [jsonBlob,mdBlob]=await Promise.all([
      github.request('POST',`${repo}/git/blobs`,{content:JSON.stringify(result,null,2)+'\n',encoding:'utf-8'}),
      github.request('POST',`${repo}/git/blobs`,{content:markdown,encoding:'utf-8'})]);
    // Preserve the fresh head tree; do not synthesize a tree containing only this request.
    const base=head|| (await github.request('GET',`${repo}/git/ref/heads/main`)).object.sha;
    const baseCommit=await github.request('GET',`${repo}/git/commits/${base}`);
    const tree=await github.request('POST',`${repo}/git/trees`,{base_tree:baseCommit.tree.sha,tree:[
      {path:jsonPath,mode:'100644',type:'blob',sha:jsonBlob.sha},
      {path:mdPath,mode:'100644',type:'blob',sha:mdBlob.sha}]});
    const commit=await github.request('POST',`${repo}/git/commits`,{message:`site-check: ${result.request_id}`,
      tree:tree.sha,parents:[base]});
    try {
      if(head)await github.request('PATCH',`${repo}/git/refs/heads/${RESULT_BRANCH}`,{sha:commit.sha,force:false});
      else await github.request('POST',`${repo}/git/refs`,{ref:`refs/heads/${RESULT_BRANCH}`,sha:commit.sha});
      return {commitSha:commit.sha,path:jsonPath};
    }catch(e){if(!conflict(e))throw e;}
  }
  throw Error('RESULT_CAS_EXHAUSTED');
}

export function githubClient(token) {
  if(!token)throw Error('MISSING_TOKEN');
  return {async request(method,path,body){
    if(!path.startsWith(repo+'/'))throw Error('INVALID_GITHUB_PATH');
    const response=await fetch('https://api.github.com'+path,{method,headers:{
      Authorization:`Bearer ${token}`,Accept:'application/vnd.github+json',
      'X-GitHub-Api-Version':'2022-11-28',...(body?{'Content-Type':'application/json'}:{})},
      body:body?JSON.stringify(body):undefined});
    if(!response.ok){const error=Error(`GITHUB_HTTP_${response.status}`);error.status=response.status;throw error;}
    return response.json();
  }};
}

export function artifactFailureResult({requestId,requestSha,testSha,runID}) {
  if(!UUID_RE.test(requestId)||!sha.test(requestSha)||!sha.test(testSha)||!Number.isSafeInteger(runID))
    throw Error('INVALID_RESULT');
  return {schema_version:1,request_id:requestId,request_commit:requestSha,test_commit:testSha,
    run_id:runID,url:SITE_URL,status:'ERROR',expected_content_revision:null,observed_content_revision:null,
    observed_build_id:null,source:null,started_at:new Date().toISOString(),finished_at:new Date().toISOString(),
    checks:{artifact_upload:'failed'},observations:[],artifacts:[]};
}

async function cli(){
  const mode=process.argv[2],github=githubClient(process.env.GITHUB_TOKEN);
  const event=JSON.parse(await readFile(process.env.GITHUB_EVENT_PATH,'utf8'));
  const runID=Number(process.env.GITHUB_RUN_ID);
  if(!Number.isSafeInteger(runID))throw Error('INVALID_RUN_ID');
  if(mode==='verify'){
    const {chromium}=await import('playwright');
    const {verifySite}=await import('./site-check-browser.mjs');
    let trusted,result;const started=new Date().toISOString();
    try {trusted=await readTrustedRequest({event,github});
      if(trusted.testSha!==process.env.TEST_SHA)throw Error('TRUSTED_MAIN_MOVED');
      await mkdir('site-check-output',{recursive:true});
      const browser=await chromium.launch({headless:true});
      try {const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true,
        deviceScaleFactor:2,serviceWorkers:'block'});
        result=await verifySite({request:trusted.request,page,budgetMs:350000,
          screenshotPath:'site-check-output/screenshot.png'});
      } finally {await browser.close();}
    } catch(e){result={schema_version:1,request_id:trusted?.request.request_id||null,
      status:e.message==='INVALID_REQUEST'?'INVALID_REQUEST':'ERROR',url:SITE_URL,
      expected_content_revision:trusted?.request.expected_content_revision||null,
      observed_content_revision:null,observed_build_id:null,source:null,
      checks:{trust:e.message},observations:[],artifacts:[],started_at:started,finished_at:new Date().toISOString()};}
    const run=Number.isSafeInteger(event?.workflow_run?.id)
      ?await github.request('GET',`${repo}/actions/runs/${event.workflow_run.id}`).catch(()=>null):null;
    result.request_id??=branchId(run);
    result.request_commit=trusted?.requestSha|| (sha.test(run?.head_sha)?run.head_sha:null);
    result.test_commit=process.env.TEST_SHA;result.run_id=runID;
    await mkdir('site-check-output',{recursive:true});
    await writeFile('site-check-output/result.json',JSON.stringify(result,null,2)+'\n');
    await writeFile('site-check-output/result.md',`# Site check ${result.status}\n\nRun: https://github.com/ga815647/phu-quoc-2026-mobile/actions/runs/${runID}\n\nObserved at ${result.finished_at}. This is not evidence of future site state.\n`);
    return;
  }
  if(mode==='publish'){
    const run=await github.request('GET',`${repo}/actions/runs/${event.workflow_run.id}`);
    const id=branchId(run);
    if(!id||!sha.test(run.head_sha))throw Error('UNPUBLISHABLE_REQUEST');
    const artifactOK=process.env.ARTIFACT_OK==='true';
    let result,markdown;
    if(artifactOK){
      const list=await github.request('GET',`${repo}/actions/runs/${runID}/artifacts?per_page=100`);
      const artifactID=Number(process.env.ARTIFACT_ID);
      if(!Number.isSafeInteger(artifactID)||artifactID<=0||
        !list.artifacts?.some(a=>a.id===artifactID && a.name==='site-check-evidence' &&
          a.workflow_run?.id===runID && !a.expired))throw Error('UNTRUSTED_ARTIFACT');
      result=JSON.parse(await readFile('site-check-output/result.json','utf8'));
      markdown=await readFile('site-check-output/result.md','utf8');
      if(result.request_id!==id||result.run_id!==runID||result.request_commit!==run.head_sha||
        result.test_commit!==process.env.TEST_SHA)throw Error('UNTRUSTED_ARTIFACT');
      if(result.artifacts?.includes('screenshot.png') && !(await readFile('site-check-output/screenshot.png').catch(()=>null)))
        throw Error('MISSING_SCREENSHOT');
    }else{
      result=artifactFailureResult({requestId:id,requestSha:run.head_sha,testSha:process.env.TEST_SHA,runID});
      markdown=`# Site check ERROR\n\nArtifact upload failed; no PASS evidence. Run https://github.com/ga815647/phu-quoc-2026-mobile/actions/runs/${runID}\n`;
    }
    const published=await publishResult({github,requestSha:run.head_sha,result,markdown});
    console.log(JSON.stringify(published));
    return;
  }
  throw Error('INVALID_MODE');
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)cli().catch(e=>{
  console.error(e.message);process.exitCode=1;
});
