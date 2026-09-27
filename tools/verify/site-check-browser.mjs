import {SITE_URL} from './site-check-contract.mjs';
import {validateEnvelope} from '../itinerary-reader.mjs';
import {isDeepStrictEqual} from 'node:util';

const API_ORIGIN='https://br-silent-haze-b3xw64tm-phqreadonly.compute.c-4.ap-southeast-1.aws.neon.tech';
const cards=['onbird','vinwonders','cable','starfish','safari'];
const same=isDeepStrictEqual;
const key=r=>r&&`${r.type}:${r.id}`;
const name=(refs,r)=>{
  if(!r)return '';
  const groups={card:['cards','slug'],food:['foods','notion_id'],pool:['pool','pool_key'],point:['points','slug'],base:['bases','id']};
  const [group,id]=groups[r.type]||[];
  const row=refs[group]?.find(x=>x[id]===r.id);
  if(!row)return '';
  if(r.type==='base'){
    const target=refs[row.ref.type==='booking'?'bookings':'points'].find(x=>x.slug===row.ref.id);
    return target?.name||target?.title||row.id;
  }
  if(r.type==='pool'&&row.notion_id)return refs.foods.find(x=>x.notion_id===row.notion_id)?.name||row.pool_key;
  return row.name||row.title||row.slug||row.id;
};

export async function verifySite({request,page,siteUrl=SITE_URL,apiOrigin=API_ORIGIN,
  now=Date.now,sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms)),budgetMs=360000,
  intervalMs=20000,screenshotPath}) {
  const start=now(),wallStart=performance.now(),startedAt=new Date().toISOString(),observations=[];let last=null;
  // Only the production entry point is injectable for isolated browser tests.
  if(siteUrl!==SITE_URL && !['localhost','127.0.0.1'].includes(new URL(siteUrl).hostname))throw Error('INVALID_SITE_URL');
  if(apiOrigin!==API_ORIGIN && !['localhost','127.0.0.1'].includes(new URL(apiOrigin).hostname))throw Error('INVALID_API_ORIGIN');
  const deadlineError=()=>Error('SITE_CHECK_DEADLINE');
  let expired=false;
  const remaining=()=>Math.min(budgetMs-(now()-start),budgetMs-(performance.now()-wallStart));
  // A wall-clock watchdog also bounds evaluate(), response.json(), and injected
  // promises, which have no usable Playwright timeout. Closing the page cancels
  // any outstanding browser operation; never await an uncooperative operation.
  const limited=async (operation,maximum=Infinity)=>{
    const ms=Math.min(remaining(),maximum);
    if(expired||ms<=0)throw deadlineError();
    let timer;
    try {return await Promise.race([
      Promise.resolve().then(()=>operation(ms)),
      new Promise((_,reject)=>{timer=setTimeout(()=>{
        expired=true;
        void page.close({runBeforeUnload:false}).catch(()=>{});
        reject(deadlineError());
      },ms);})
    ]);}finally {clearTimeout(timer);}
  };
  try {await limited(async()=>{
    const devtools=await page.context().newCDPSession(page);
    await devtools.send('Network.setCacheDisabled',{cacheDisabled:true});
  });}catch(e){
    return {schema_version:1,request_id:request.request_id,request_commit:null,test_commit:null,run_id:null,
      url:siteUrl,status:'ERROR',expected_content_revision:request.expected_content_revision,
      observed_content_revision:null,observed_build_id:null,source:null,started_at:startedAt,
      finished_at:new Date().toISOString(),checks:{setup:String(e)},observations:[],artifacts:[]};
  }
  do {
    const errors=[],consumed=[],foreignApi=[],bodyReads=[];const onError=e=>errors.push(String(e));
    let signalResponse;
    const responseSeen=new Promise(resolve=>{signalResponse=resolve;});
    const onResponse=response=>{
      if(response.url()!==new URL('/api/itinerary',apiOrigin).href){
        if(new URL(response.url()).pathname.endsWith('/api/itinerary'))foreignApi.push(response.url());
        return;
      }
      bodyReads.push((async()=>{
        try {return {status:response.status(),body:await response.json(),url:response.url()};}
        catch(e){return {status:response.status(),error:String(e)};}
      })());
      signalResponse();
    };
    page.on('pageerror',onError);page.on('response',onResponse);
    let checks={},status='UNREACHABLE',source=null,revision=null,buildId=null;
    try {await limited(async attemptRemaining=>{
      await page.goto(siteUrl,{waitUntil:'domcontentloaded',timeout:Math.min(15000,attemptRemaining)});
      await page.locator('[data-itinerary][data-source]').waitFor({timeout:Math.min(budgetMs<1000?25:11000,remaining())})
        .catch(e=>{if(e.message==='SITE_CHECK_DEADLINE')throw e;});
      // Await the body of the actual response the page requested; an independent
      // verifier fetch cannot certify which envelope the UI displayed.
      const root=page.locator('[data-itinerary]');
      source=await root.getAttribute('data-source');revision=await root.getAttribute('data-content-revision');
      if(source==='live' && bodyReads.length===0)await responseSeen;
      // Responses can arrive while an earlier body is being read. Drain every
      // response observed by this point rather than snapshotting the first one.
      while(consumed.length<bodyReads.length)
        consumed.push(...await Promise.all(bodyReads.slice(consumed.length)));
      checks.source=source==='live';
      checks.api=consumed.length===1 && consumed[0].status===200 &&
        consumed[0].url===new URL('/api/itinerary',apiOrigin).href;
      checks.exclusive_api=foreignApi.length===0;
      const envelope=checks.api?consumed[0].body:null;
      try {if(envelope)validateEnvelope(envelope);checks.envelope=!!envelope;}
      catch {checks.envelope=false;}
      checks.production=checks.envelope && envelope.meta.environment==='production' && envelope.meta.source==='neon-prod';
      checks.revision=checks.production && envelope.meta.content_revision===request.expected_content_revision &&
        revision===envelope.meta.content_revision && await root.getAttribute('data-schema-version')===String(envelope.meta.schema_version);
      const version=await page.evaluate(async()=>{
        const r=await fetch('./site-version.json',{cache:'no-store'});return r.ok?await r.json():null;
      }).catch(()=>null);
      buildId=await page.locator('html').getAttribute('data-site-build');
      checks.build=!!version && /^sha256:[0-9a-f]{64}$/.test(buildId||'') && version.build_id===buildId;
       checks.days=false;checks.alternatives=false;
      if(checks.envelope){
        const refs=envelope.data.refs;
        checks.all_days=true;
        const tabs=page.locator('[data-itinerary] .date-tab');
        const panels=page.locator('[data-itinerary-day]');
        if(await tabs.count()!==6 || await panels.count()!==6)checks.all_days=false;
        else for(const [index,day] of envelope.data.days.entries()){
          const panel=page.locator(`[data-itinerary-day="${day.id}"]`);
          if(await panel.count()!==1){checks.all_days=false;break;}
          await tabs.nth(index).click();
          const copy=(await panel.innerText()).trim();
          if(!await panel.isVisible() || await panel.getAttribute('data-main-card')!==(day.main_card_slug||'') ||
            (day.main_card_slug && !copy.includes(name(refs,{type:'card',id:day.main_card_slug})))){
            checks.all_days=false;break;
          }
          const visible=await panel.locator('.timeline > .step').evaluateAll(nodes=>nodes.map(node=>({
            id:node.dataset.segmentId,refType:node.dataset.refType,refId:node.dataset.refId,
            from:node.dataset.fromRef,to:node.dataset.toRef,mode:node.dataset.mode,
            text:node.innerText,visible:node.getBoundingClientRect().height>0
          })));
          if(visible.length!==day.plan.segments.length){checks.all_days=false;break;}
          for(const [position,segment] of day.plan.segments.entries()){
            const row=visible[position],refName=segment.ref&&name(refs,segment.ref);
            if(!row.visible||row.id!==segment.id||!row.text.includes(segment.label)||
              row.refType!==(segment.ref?.type||'')||row.refId!==(segment.ref?.id||'')||
              (segment.ref&&(!refName||!row.text.includes(refName)))||
              (segment.kind==='transfer'&&(
                row.from!==key(segment.transfer.from_ref)||row.to!==key(segment.transfer.to_ref)||
                row.mode!==segment.transfer.mode||
                !row.text.includes(name(refs,segment.transfer.from_ref))||
                !row.text.includes(name(refs,segment.transfer.to_ref))||
                !row.text.includes(segment.transfer.mode)))){
              checks.all_days=false;checks.day_error=`visible segment ${day.id}/${segment.id}`;break;
            }
          }
           if(!checks.all_days)break;
           const alternatives=panel.locator('details.itinerary-alternatives');
           if(day.plan.alternatives.length===0){
             if(await alternatives.count()!==0){checks.all_days=false;checks.day_error='unexpected backups';break;}
           }else{
             if(await alternatives.count()!==1){checks.all_days=false;checks.day_error='missing backups';break;}
             await alternatives.locator('summary').click();
             if(!await alternatives.isVisible()){checks.all_days=false;checks.day_error='hidden backups';break;}
             const groups=alternatives.locator(':scope > .panel');
             if(await groups.count()!==day.plan.alternatives.length){checks.all_days=false;checks.day_error='backup count';break;}
             const actions={use_alternative:'改用備案，取代',skip_optional:'略過可選',return_or_rest:'返回或休息，調整'};
             for(const [i,alternative] of day.plan.alternatives.entries()){
               const group=groups.nth(i),text=await group.innerText();
               const targets=alternative.target_segment_ids.map(id=>day.plan.segments.find(s=>s.id===id)?.label||id);
               if(!await group.isVisible() || !text.includes(alternative.trigger_text) ||
                 !text.includes(actions[alternative.action]+' '+targets.join('、'))){checks.all_days=false;checks.day_error='backup trigger/action';break;}
               const rows=group.locator(':scope > .step');
               if(await rows.count()!==alternative.replacement_segments.length){checks.all_days=false;checks.day_error='backup replacement count';break;}
               for(const [j,segment] of alternative.replacement_segments.entries()){
                 const row=rows.nth(j),copy=await row.innerText(),refName=segment.ref&&name(refs,segment.ref);
                 if(!await row.isVisible() || await row.getAttribute('data-segment-id')!==segment.id ||
                   !copy.includes(segment.label) || await row.getAttribute('data-ref-type')!==(segment.ref?.type||'') ||
                   await row.getAttribute('data-ref-id')!==(segment.ref?.id||'') ||
                   (segment.ref&&(!refName||!copy.includes(refName))) ||
                   (segment.kind==='transfer'&&(
                     await row.getAttribute('data-from-ref')!==key(segment.transfer.from_ref) ||
                     await row.getAttribute('data-to-ref')!==key(segment.transfer.to_ref) ||
                     await row.getAttribute('data-mode')!==segment.transfer.mode ||
                     !copy.includes(name(refs,segment.transfer.from_ref)) ||
                     !copy.includes(name(refs,segment.transfer.to_ref)) ||
                     !copy.includes(segment.transfer.mode)))){
                   checks.all_days=false;checks.day_error='backup replacement ref';break;
                 }
               }
               if(!checks.all_days)break;
             }
             if(!checks.all_days)break;
           }
         }
         checks.alternatives=checks.all_days;
        checks.days=true;
        for(const expected of request.expected){
          const day=envelope.data.days.find(x=>x.id===expected.day_id);
          if(!day || day.main_card_slug!==expected.main_card_slug){checks.days=false;checks.day_error='card';break;}
          const meals=day.plan.segments.filter(s=>s.kind==='meal').map(s=>({segment_id:s.id,ref:s.ref}));
          const transfers=day.plan.segments.filter(s=>s.kind==='transfer').map(s=>({segment_id:s.id,
            from_ref:s.transfer.from_ref,to_ref:s.transfer.to_ref,mode:s.transfer.mode}));
          if(!same(meals,expected.meals)||!same(transfers,expected.transfers)){checks.days=false;checks.day_error='payload refs';break;}
          const exact=page.locator(`[data-itinerary-day="${expected.day_id}"]`);
          if(await exact.count()!==1){checks.days=false;checks.day_error='panel';break;}
          const index=envelope.data.days.findIndex(x=>x.id===expected.day_id);
          if(await tabs.count()!==6){checks.days=false;checks.day_error='tabs';break;}
          await tabs.nth(index).click();
          if(!(await exact.isVisible()) || await exact.getAttribute('data-main-card')!==(day.main_card_slug||'')){
            checks.days=false;checks.day_error='panel visibility or card';break;
          }
          const visibleText=(await exact.innerText()).trim();
          if(day.main_card_slug && !visibleText.includes(name(refs,{type:'card',id:day.main_card_slug}))){checks.days=false;checks.day_error='card text';break;}
          const visibleRefs=await exact.locator('.timeline > .step').evaluateAll(nodes=>({
            meals:nodes.filter(n=>['food','pool'].includes(n.dataset.refType)).map(n=>({segment_id:n.dataset.segmentId,
              ref:{type:n.dataset.refType,id:n.dataset.refId}})),
            transfers:nodes.filter(n=>n.hasAttribute('data-from-ref')).map(n=>({segment_id:n.dataset.segmentId,
              from:n.dataset.fromRef,to:n.dataset.toRef,mode:n.dataset.mode}))
          }));
          if(!same(visibleRefs.meals,expected.meals)||!same(visibleRefs.transfers,
            expected.transfers.map(t=>({segment_id:t.segment_id,from:key(t.from_ref),to:key(t.to_ref),mode:t.mode})))){
            checks.days=false;checks.day_error=`DOM complete ref sets actual ${JSON.stringify(visibleRefs)} expected ${JSON.stringify(expected)}`;break;
          }
          for(const assertion of [...expected.meals,...expected.transfers]){
            const segment=exact.locator(`.step[data-segment-id="${assertion.segment_id}"]`);
            if(await segment.count()!==1 || !await segment.isVisible()){checks.days=false;checks.day_error='segment visible';break;}
            const text=(await segment.innerText()).trim();
            if('ref' in assertion){
              if(await segment.getAttribute('data-ref-type')!==assertion.ref.type ||
                 await segment.getAttribute('data-ref-id')!==assertion.ref.id ||
                 !name(refs,assertion.ref) || !text.includes(name(refs,assertion.ref))){checks.days=false;checks.day_error=`meal text or hook: ${JSON.stringify({text,name:name(refs,assertion.ref),type:await segment.getAttribute('data-ref-type'),id:await segment.getAttribute('data-ref-id')})}`;}
            }else if(await segment.getAttribute('data-from-ref')!==key(assertion.from_ref) ||
              await segment.getAttribute('data-to-ref')!==key(assertion.to_ref) ||
              await segment.getAttribute('data-mode')!==assertion.mode ||
              !name(refs,assertion.from_ref) || !name(refs,assertion.to_ref) ||
              !text.includes(name(refs,assertion.from_ref)) || !text.includes(name(refs,assertion.to_ref)) ||
              !text.includes(assertion.mode)){checks.days=false;checks.day_error='transfer text or hook';}
          }
        }
      }
      const links=page.locator('a.link-card');
      const slugs=await links.evaluateAll(nodes=>nodes.map(n=>new URL(n.href).searchParams.get('slug')));
       checks.cards=slugs.length===5 && same([...slugs].sort(),[...cards].sort()) &&
        await links.evaluateAll(nodes=>nodes.every(n=>n.getBoundingClientRect().height>=41 &&
          n.getBoundingClientRect().width>=41 && n.href &&
           new URL(n.href).pathname===new URL('./card.html',location.href).pathname));
       checks.card_navigation=false;
       if(checks.cards){
         // The consumed envelope above is already resolved and validated. Do not
         // overwrite that evidence with an independent fetch after navigation.
         const observed=consumed[0],href=await links.first().getAttribute('href');
         const destination=new URL(href,siteUrl);
         const [response]=await Promise.all([
           page.waitForNavigation({waitUntil:'domcontentloaded',timeout:Math.min(10000,remaining())}),
           links.first().click({timeout:Math.min(10000,remaining())})
         ]);
         await page.locator('#cardMount h1').waitFor({timeout:Math.min(8000,remaining())}).catch(()=>{});
         checks.card_navigation=!!observed && response?.status()===200 &&
           page.url()===destination.href && await page.locator('#cardMount h1').isVisible() &&
           (await page.locator('#cardMount h1').innerText()).trim().length>0;
         if(!checks.card_navigation)checks.card_error=`status ${response?.status()} url ${page.url()} expected ${destination.href} heading ${await page.locator('#cardMount h1').allInnerTexts()}`;
         if(checks.card_navigation){
           await page.goBack({waitUntil:'domcontentloaded',timeout:Math.min(10000,remaining())});
           await page.locator('[data-itinerary][data-source]').waitFor({timeout:Math.min(10000,remaining())});
           checks.card_navigation=page.url()===siteUrl &&
             await page.locator('[data-itinerary]').getAttribute('data-source')==='live' &&
             await page.locator('[data-itinerary]').getAttribute('data-content-revision')===revision;
           if(!checks.card_navigation)checks.card_error=`return ${page.url()} revision ${await page.locator('[data-itinerary]').getAttribute('data-content-revision')}`;
         }
       }
      checks.navigation=await page.locator('.nav [data-jump]').evaluateAll(nodes=>
        ['today','itinerary','food','journey'].every(id=>nodes.some(node=>node.dataset.jump===id &&
          node.getBoundingClientRect().width>=41 && node.getBoundingClientRect().height>=41 &&
          !!document.getElementById(id))));
      if(checks.navigation){
        await page.locator('.nav [data-jump="itinerary"]').click();
        checks.navigation=await page.locator('.nav [data-jump="itinerary"]').evaluate(node=>
          node.classList.contains('primary') && location.hash==='');
      }
      checks.overflow=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1);
      checks.errors=errors.length===0;
       status=Object.entries(checks).filter(([key])=>!['day_error','card_error'].includes(key)).every(([,value])=>value===true)
        ?'PASS':source==='fallback'?'FALLBACK':!checks.api?'UNREACHABLE':'CONTENT_MISMATCH';
    });} catch(e){checks.navigation=String(e);status='UNREACHABLE';}
    finally {page.off('pageerror',onError);page.off('response',onResponse);}
    if(errors.length){checks.errors=false;status='ERROR';}
    last={status,checks,source,revision,buildId};
    observations.push({at:new Date().toISOString(),status,source,revision,build_id:buildId,checks,errors});
    if(status==='PASS')break;
    if(expired||remaining()<=intervalMs)break;
    try {await limited(()=>sleep(intervalMs));}catch{break;}
  } while(true);
  const artifacts=[];
  if(screenshotPath){try {
    await limited(ms=>page.screenshot({path:screenshotPath,fullPage:true,timeout:ms}),10000);
    artifacts.push('screenshot.png');
  }catch(e){last.status='ERROR';observations.push({at:new Date().toISOString(),screenshot_error:String(e)});}}
  return {schema_version:1,request_id:request.request_id,request_commit:null,test_commit:null,run_id:null,url:siteUrl,
    status:last.status,expected_content_revision:request.expected_content_revision,
    observed_content_revision:last.revision,observed_build_id:last.buildId,source:last.source,
    started_at:startedAt,finished_at:new Date().toISOString(),checks:last.checks,observations,artifacts};
}
