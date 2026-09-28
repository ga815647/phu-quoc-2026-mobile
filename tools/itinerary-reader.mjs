// One validated public envelope drives both the six-day reader and Today.
const CARD_SLUGS = new Set(['onbird', 'vinwonders', 'cable', 'starfish', 'safari']);
const TYPES = {card:['cards','slug'], food:['foods','notion_id'], pool:['pool','pool_key'], point:['points','slug'], base:['bases','id']};
const isObject = x => x !== null && typeof x === 'object' && !Array.isArray(x);
const keys = (x, required, optional=[]) => isObject(x) && required.every(k => Object.hasOwn(x,k)) && Object.keys(x).every(k => required.includes(k) || optional.includes(k));
const string = x => typeof x === 'string' && x.length > 0;
const fail = () => { throw Error('INVALID_ITINERARY'); };
const interval = x => x === null || (keys(x,['min','max']) && Number.isInteger(x.min) && Number.isInteger(x.max) && x.min >= 0 && x.min <= x.max);
const hhmm = x => /^([01]\d|2[0-3]):[0-5]\d$/.test(x);
const timezoneValid = x => {try {new Intl.DateTimeFormat('en',{timeZone:x});return true;} catch {return false;}};
const timestamp = x => {
  if(typeof x !== 'string')return false;
  const match=/^(\d{4})-(\d{2})-(\d{2})T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.exec(x);
  if(!match || !Number.isFinite(Date.parse(x)))return false;
  const year=Number(match[1]),month=Number(match[2]),day=Number(match[3]);
  const leap=year%4===0 && (year%100!==0 || year%400===0);
  const days=[31,leap?29:28,31,30,31,30,31,31,30,31,30,31];
  return month>=1 && month<=12 && day>=1 && day<=days[month-1];
};
const windowValid = x => x === null || (keys(x,['min','max']) && hhmm(x.min) && hhmm(x.max) && x.min <= x.max);

export function validateEnvelope(value) {
  const data=value?.data, meta=value?.meta, trip=data?.itinerary, refs=data?.refs;
  if (!keys(value,['data','meta']) || !keys(data,['schema_version','itinerary','days','refs']) || data.schema_version !== 1 ||
      !keys(trip,['id','start_date','end_date','timezone']) || trip.id !== 'phuquoc-2026' ||
      trip.start_date !== '2026-10-10' || trip.end_date !== '2026-10-15' || trip.timezone !== 'Asia/Ho_Chi_Minh' ||
      !keys(meta,['schema_version','content_revision','source','environment','fetched_at'],['exported_at']) ||
      meta.schema_version !== 1 || !/^phq1:[0-9a-f]{64}$/.test(meta.content_revision) ||
      !string(meta.source) || !string(meta.environment) || !Number.isFinite(Date.parse(meta.fetched_at)) ||
      (meta.exported_at !== undefined && !timestamp(meta.exported_at)) ||
      !keys(refs,['cards','foods','pool','points','bases','bookings','transport']) ||
      Object.values(refs).some(v=>!Array.isArray(v)) || !Array.isArray(data.days) || data.days.length !== 6) fail();

  for (const [type,[category,key]] of Object.entries(TYPES)) {
    const ids=new Set();
    for(const row of refs[category]) {
      if(!isObject(row) || !string(row[key]) || ids.has(row[key])) fail();
      ids.add(row[key]);
      if(type==='base' && (!keys(row,['id','ref']) || !['booking','point'].includes(row.ref?.type) ||
          !refs[row.ref.type === 'booking' ? 'bookings':'points'].some(r=>r[row.ref.type === 'booking'?'slug':'slug'] === row.ref.id))) fail();
    }
  }
  for(const row of refs.pool) {
    if(row.notion_id !== null && !refs.foods.some(f=>f.notion_id===row.notion_id)) fail();
  }
  function ref(r) {
    if(r === null) return;
    const match=TYPES[r?.type];
    if(!keys(r,['type','id']) || !match || !refs[match[0]].some(row=>row[match[1]]===r.id)) fail();
  }
  function segment(s, ids) {
    if(!keys(s,['id','kind','label','time','ref','condition_refs'],['selection','transfer','note']) ||
        !string(s.id) || ids.has(s.id) || !['activity','meal','transfer','rest','optional'].includes(s.kind) ||
        !string(s.label) || !Array.isArray(s.condition_refs) || !s.condition_refs.every(string)) fail();
    ids.add(s.id); ref(s.ref);
    if(s.kind==='meal' && (!['derived','explicit'].includes(s.selection) || !['food','pool'].includes(s.ref?.type))) fail();
    if(s.selection !== undefined && !['derived','explicit'].includes(s.selection)) fail();
    const t=s.time;
    if(!keys(t,['start_window','day_offset','timezone','duration_minutes','kind','source_refs','evidence_as_of']) ||
        !windowValid(t.start_window) || ![0,1].includes(t.day_offset) || !string(t.timezone) || !timezoneValid(t.timezone) ||
        !interval(t.duration_minutes) || !['scheduled','estimated','planned','unknown'].includes(t.kind) ||
        !Array.isArray(t.source_refs) || !t.source_refs.every(string) ||
        (t.evidence_as_of !== null && !string(t.evidence_as_of))) fail();
    if(s.kind==='transfer') {
      const tr=s.transfer;
      if(!keys(tr,['from_ref','to_ref','mode','wait_minutes','buffer_minutes','condition_refs']) ||
          !['operator_pickup','grab','taxi','bus','charter','walk','cable'].includes(tr.mode) ||
          !interval(tr.wait_minutes) || !Number.isInteger(tr.buffer_minutes) || tr.buffer_minutes < 0 ||
           !Array.isArray(tr.condition_refs) || !tr.condition_refs.every(string)) fail();
      ref(tr.from_ref); ref(tr.to_ref);
      if(!tr.from_ref || !tr.to_ref) fail();
    } else if(s.transfer !== undefined) fail();
  }
  const dayIds=new Set();
  for(let i=0;i<6;i++) {
    const d=data.days[i], date=`2026-10-${String(i+10).padStart(2,'0')}`;
    if(!keys(d,['id','date','day_kind','main_card_slug','plan']) || d.date !== date ||
        d.id !== `${trip.id}:${date}` || dayIds.has(d.id) || !string(d.day_kind) ||
         (d.main_card_slug !== null && (!CARD_SLUGS.has(d.main_card_slug) || !refs.cards.some(c=>c.slug===d.main_card_slug && c.status==='ACTIVE'))) ||
         !keys(d.plan,['schema_version','segments','alternatives'],['public_note']) || d.plan.schema_version !== 1 ||
         !Array.isArray(d.plan.segments) || d.plan.segments.length>32 ||
         !Array.isArray(d.plan.alternatives) || d.plan.alternatives.length>8 ||
         (d.day_kind==='activity' && d.main_card_slug===null) ||
         (d.main_card_slug!==null && !d.plan.segments.some(s=>s?.kind==='activity' &&
           s.ref?.type==='card' && s.ref.id===d.main_card_slug))) fail();
    dayIds.add(d.id);
    const ids=new Set(); d.plan.segments.forEach(s=>segment(s,ids));
    const altIds=new Set();
    for(const a of d.plan.alternatives) {
      if(!keys(a,['id','trigger_kind','trigger_text','action','target_segment_ids','replacement_segments']) ||
          !string(a.id) || altIds.has(a.id) || !string(a.trigger_text) ||
          !['weather','fatigue','late','unavailable','manual'].includes(a.trigger_kind) ||
          !['skip_optional','use_alternative','return_or_rest'].includes(a.action) ||
          !Array.isArray(a.target_segment_ids) || !a.target_segment_ids.every(id=>ids.has(id)) ||
          !Array.isArray(a.replacement_segments) || a.replacement_segments.length>32 ||
          (a.action==='use_alternative') !== (a.replacement_segments.length>0)) fail();
      altIds.add(a.id); a.replacement_segments.forEach(s=>segment(s,ids));
    }
    const checkConditions=(s,replacement)=>{
      const cardIds=[s.ref,s.transfer?.from_ref,s.transfer?.to_ref].filter(r=>r?.type==='card').map(r=>r.id);
       const gates=cardIds.flatMap(id=>{
         try {const card=refs.cards.find(c=>c.slug===id);const parsed=JSON.parse(card?.gates || '[]');
           const mapped=card?.condition_labels || {};
           return Array.isArray(parsed)?[...parsed,...Object.entries(mapped).filter(([,label])=>parsed.includes(label)).map(([key])=>key)]:[];}
        catch {return [];}
      });
      for(const id of [...s.condition_refs,...(s.transfer?.condition_refs || [])]) {
        if((!replacement && altIds.has(id)) || gates.includes(id))continue;
        fail();
      }
    };
    d.plan.segments.forEach(s=>checkConditions(s,false));
    d.plan.alternatives.forEach(a=>a.replacement_segments.forEach(s=>checkConditions(s,true)));
  }
  return value;
}

async function fetchOne(url, fetchImpl, timeoutMs) {
  const ctrl=new AbortController();
  const timer=setTimeout(()=>ctrl.abort(),timeoutMs);
  try {
    const response=await fetchImpl(url,{signal:ctrl.signal,cache:'no-store'});
    if(!response.ok) throw Error('HTTP');
    return validateEnvelope(await response.json());
  } finally {clearTimeout(timer);}
}

export async function loadItinerary({apiUrl,fallbackUrl,fetchImpl=fetch,timeoutMs=8000}) {
  try { return {envelope:await fetchOne(apiUrl,fetchImpl,timeoutMs),mode:'live'}; }
  catch { try { const envelope=await fetchOne(fallbackUrl,fetchImpl,timeoutMs);
      if (!timestamp(envelope.meta.exported_at)) fail();
      return {envelope,mode:'fallback'}; }
    catch {throw Error('ITINERARY_UNAVAILABLE');} }
}

const el=(tag,cls,text) => {const node=document.createElement(tag);if(cls) node.className=cls;if(text !== undefined) node.textContent=String(text);return node;};
const refId=r=>r ? `${r.type}:${r.id}` : '';
const nameFor=(refs,r) => {
  if(!r)return '';
  const [cat,key]=TYPES[r.type]; const row=refs[cat].find(x=>x[key]===r.id);
  if(r.type==='base') {
    const source=row.ref.type==='booking' ? refs.bookings : refs.points;
    const target=source.find(x=>x.slug===row.ref.id);
    return target.name || target.title || row.id;
  }
  if(r.type==='pool') return row.notion_id ? (refs.foods.find(x=>x.notion_id===row.notion_id)?.name || row.pool_key) : row.pool_key;
  return row.name || row.title || row.slug || row.id;
};
function timeText(t) {
  const prefix=t.day_offset===1?'次日 ':'';
  const slot=t.start_window ? `${t.start_window.min}${t.start_window.min===t.start_window.max?'':`–${t.start_window.max}`}` : '時間待定';
  const duration=t.duration_minutes ? `${t.duration_minutes.min}${t.duration_minutes.min===t.duration_minutes.max?'':`–${t.duration_minutes.max}`} 分鐘`:'待估';
  const zone=new Intl.DateTimeFormat('zh-Hant',{timeZone:t.timezone,timeZoneName:'short'}).formatToParts(new Date()).find(p=>p.type==='timeZoneName')?.value || t.timezone;
  const kinds={scheduled:'已核對時刻（非完成）',estimated:'估算（非實測）',planned:'預留（非實測）',unknown:'時間未核實'};
  return {clock:prefix+slot,zone:`時區 ${t.timezone} ${zone}`,certainty:kinds[t.kind],duration};
}
const DAY_KINDS={arrival:'抵達日',activity:'主活動',light:'輕鬆安排',departure:'返程日'};
const SEGMENT_KINDS={activity:'活動',meal:'用餐',transfer:'交通',rest:'休息',optional:'可選'};
const recheck=date=>date && (Date.now()-Date.parse(`${date}T00:00:00Z`))/86400000 > 30;
function evidence(body,dates,source) {
  const unique=[...new Set(dates.filter(Boolean))];
  unique.forEach(date=>body.append(el('p','tiny',`核實 ${date}${recheck(date)?' · 出發前重查':''}`)));
  if(source)body.append(el('p','tiny',`依據：${source}`));
}
function appendSegment(list,s,refs,alternatives) {
  const item=el('div',`step route-${s.kind}`);item.dataset.segmentId=s.id;item.dataset.kind=s.kind;
  item.dataset.refType=s.ref?.type || '';item.dataset.refId=s.ref?.id || '';
  const label=timeText(s.time);
  const time=el('div','time',label.clock);const body=el('div','route-body');
  body.append(el('span','route-kind',SEGMENT_KINDS[s.kind]));
  body.append(el('b','',s.label));
  const detail=el('div','time-detail');
  detail.append(el('span','',label.zone),el('span','',label.certainty),el('span','',label.duration));
  body.append(detail);
  evidence(body,[s.time.evidence_as_of],s.time.source_refs.join('、'));
  const conditionLabel=id=>alternatives.find(a=>a.id===id)?.trigger_text ||
    refs.cards.find(c=>c.slug==='starfish')?.condition_labels?.[id] || id;
  if(s.kind==='optional')body.append(el('p','tiny','可選，非必做'));
  if(s.condition_refs.length)body.append(el('p','tiny',`條件：${s.condition_refs.map(conditionLabel).join('、')}`));
  if(s.ref) {
    body.append(el('p','',nameFor(refs,s.ref)));
    const row=refs[TYPES[s.ref.type][0]].find(x=>x[TYPES[s.ref.type][1]]===s.ref.id);
    const place=s.ref.type==='pool' && row.notion_id ? refs.foods.find(f=>f.notion_id===row.notion_id) : row;
    evidence(body,[place?.last_verified,place?.evidence_as_of],place?.evidence);
    const mapQuery=s.ref.type==='base' ? null : place?.maps_query;
    if(mapQuery) {
      const link=el('a','place-link','地圖');link.href='https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(mapQuery);
      link.target='_blank';link.rel='noopener';body.append(link);
    }
    if(s.ref.type==='card' && CARD_SLUGS.has(s.ref.id)) {
      const link=el('a','place-link','看行程卡');link.href=`./card${document.documentElement.dataset.itineraryMode==='candidate'?'-candidate':''}.html?slug=${s.ref.id}`;body.append(link);
    }
  }
  if(s.kind==='transfer') {
    const tr=s.transfer;item.dataset.fromRef=refId(tr.from_ref);item.dataset.toRef=refId(tr.to_ref);item.dataset.mode=tr.mode;
    body.append(el('p','',`${nameFor(refs,tr.from_ref)} → ${nameFor(refs,tr.to_ref)} · ${tr.mode} · 等車 ${tr.wait_minutes ? `${tr.wait_minutes.min}–${tr.wait_minutes.max} 分鐘`:'待估'} · 緩衝 ${tr.buffer_minutes} 分鐘`));
    if(tr.condition_refs.length)body.append(el('p','tiny',`交通條件：${tr.condition_refs.map(conditionLabel).join('、')}`));
  }
  if(s.note)body.append(el('p','',s.note));
  item.append(time,body);list.append(item);
}

export function renderItinerary(root,loaded) {
  const {envelope,mode}=loaded;validateEnvelope(envelope);
  const {data,meta}=envelope;const fragment=document.createDocumentFragment();
  const selected=root.querySelector('.day-panel.active')?.dataset.itineraryDay || (()=>{try{return sessionStorage.getItem('phq-itinerary-selected-day')}catch{return null}})();
  const activeDay=data.days.some(d=>d.id===selected)?selected:data.days[0].id;
  const info=el('details','itinerary-provenance');
  info.append(el('summary','',`${mode==='live'?'線上資料':'備援資料（非最新）'} · ${mode==='fallback'?'匯出 '+(meta.exported_at||'日期未知'):'取得 '+meta.fetched_at} · 版本與讀取資訊`));
  info.append(el('p','tiny',`版本 ${meta.content_revision} · 最後讀取 ${new Date().toISOString()}`));
  fragment.append(info);
  const tabs=el('div','date-tabs');tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','日期切換 10/10–10/15');fragment.append(tabs);
  const panels=el('div');fragment.append(panels);
  data.days.forEach((d,index)=>{
    const button=el('button','date-tab',d.date.slice(5));button.type='button';button.setAttribute('role','tab');button.setAttribute('aria-selected',String(d.id===activeDay));button.setAttribute('aria-pressed',String(d.id===activeDay));tabs.append(button);
    const panel=el('div','day-panel'+(d.id===activeDay?' active':''));panel.dataset.itineraryDay=d.id;panel.dataset.mainCard=d.main_card_slug||'';
    const header=el('div','day-header');header.append(el('span','day-date',d.date));
    header.append(el('div','today-big',d.main_card_slug ? nameFor(data.refs,{type:'card',id:d.main_card_slug}) : DAY_KINDS[d.day_kind] || '當日安排'));
    if(d.main_card_slug)header.append(el('span','day-kind',DAY_KINDS[d.day_kind] || '當日安排'));
    panel.append(header);
    if(d.plan.public_note)panel.append(el('p','tiny',d.plan.public_note));
    if(!d.plan.segments.length)panel.append(el('p','tiny','當日目前沒有安排段落。'));
    const list=el('div','timeline coastal-route');d.plan.segments.forEach(s=>appendSegment(list,s,data.refs,d.plan.alternatives));panel.append(list);
    if(d.plan.alternatives.length){const details=el('details','itinerary-alternatives');details.append(el('summary','','備案（按需查看）'));
      const actions={use_alternative:'改用備案，取代',skip_optional:'略過可選',return_or_rest:'返回或休息，調整'};
      d.plan.alternatives.forEach(a=>{const group=el('div','panel pad');group.append(el('b','',a.trigger_text));
        const targets=a.target_segment_ids.map(id=>d.plan.segments.find(s=>s.id===id)?.label || id);
        group.append(el('p','tiny',`${actions[a.action]} ${targets.join('、')}`));
        a.replacement_segments.forEach(s=>appendSegment(group,s,data.refs,d.plan.alternatives));details.append(group);});panel.append(details);}
    panels.append(panel);
    button.addEventListener('click',()=>{tabs.querySelectorAll('button').forEach(b=>{b.setAttribute('aria-selected',String(b===button));b.setAttribute('aria-pressed',String(b===button));});panels.querySelectorAll('.day-panel').forEach(p=>p.classList.toggle('active',p===panel));try{sessionStorage.setItem('phq-itinerary-selected-day',d.id)}catch{}});
  });
  root.replaceChildren(fragment);
  root.dataset.contentRevision=meta.content_revision;root.dataset.source=mode;root.dataset.schemaVersion=String(meta.schema_version);
}

export function mountItinerary({root,todayRoot,refreshButton,apiUrl,fallbackUrl,fetchImpl=fetch,now=()=>new Date()}) {
  let generation=0,loaded=null;
  function today() {
    if(!todayRoot || !loaded)return;
    const date=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit'}).format(now());
    const dateLine=todayRoot.querySelector('#vietnamDateLine');if(dateLine)dateLine.textContent='越南時間 '+date;
    const day=loaded.envelope.data.days.find(x=>x.date===date);
    const desc=day ? day.plan.segments.map(s=>`${s.label}${s.ref?'：'+nameFor(loaded.envelope.data.refs,s.ref):''}`).join('、') : '請在行程區查看六日安排。';
    const phase=todayRoot.querySelector('#tripPhase'),title=todayRoot.querySelector('#todayTitle'),detail=todayRoot.querySelector('#todayDesc'),next=todayRoot.querySelector('#todayNext');
    if(phase)phase.textContent=date<'2026-10-10'?'出發前':date>'2026-10-15'?'旅行後':'旅途中 · '+date;
    if(title)title.textContent=day?`今日（${date}）：${day.main_card_slug?nameFor(loaded.envelope.data.refs,{type:'card',id:day.main_card_slug}):DAY_KINDS[day.day_kind] || '當日安排'}`:`六日行程（${date}）`;
    if(detail)detail.textContent=desc;
    if(next)next.textContent=loaded.mode==='fallback'?'備援資料，非最新安排。':'線上行程已讀取。';
  }
  async function refresh() {
    const mine=++generation;
    try {
      const result=await loadItinerary({apiUrl,fallbackUrl,fetchImpl});
      if(mine!==generation)return;
      renderItinerary(root,result);loaded=result;today();
    } catch {
      if(mine!==generation)return;
      root.dataset.source='unavailable';root.dataset.contentRevision='';
      const notice=el('div','callout red',loaded?'更新失敗，保留上次讀取的行程（非最新）。':'行程暫不可用，請檢查連線後重新整理資料。');
      if(loaded){root.querySelector(':scope > .itinerary-error')?.remove();notice.classList.add('itinerary-error');root.prepend(notice);const next=todayRoot?.querySelector('#todayNext');if(next)next.textContent='更新失敗，顯示上次讀取的行程（非最新）。';}
      else {root.replaceChildren(notice);const title=todayRoot?.querySelector('#todayTitle');if(title)title.textContent='行程暫不可用';}
    }
  }
  refreshButton?.addEventListener('click',refresh);
  void refresh();
  return {refresh,destroy:()=>{generation++;refreshButton?.removeEventListener('click',refresh);}};
}
