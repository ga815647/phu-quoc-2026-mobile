// Pure validation only. The caller must establish GitHub provenance and pass its
// independently verified context; neither request JSON nor workflow env is evidence.
export const SITE_URL='https://ga815647.github.io/phu-quoc-2026-mobile/';
export const RESULT_BRANCH='site-check-results';
export const UUID_RE=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

const SHA_RE=/^[0-9a-f]{40}$/;
const REVISION_RE=/^phq1:[0-9a-f]{64}$/;
// Match itinerary_validate_day in 006_itinerary_model.sql for source segment IDs.
const SEGMENT_RE=/^[a-z0-9][a-z0-9-]{0,39}$/;
const REF_ID_RE=/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;
const MAIN_CARDS=new Set(['onbird','vinwonders','cable','starfish','safari']);
// An Thoi is an OPTIONAL satellite endpoint, not a sixth main-day card.
const REF_CARDS=new Set([...MAIN_CARDS,'anthoi']);
const MODES=new Set(['operator_pickup','grab','taxi','bus','charter','walk','cable']);
const REF_TYPES=new Set(['card','food','pool','point','base']);
const fail=()=>{throw Error('INVALID_REQUEST');};
const object=x=>x!==null && typeof x==='object' && !Array.isArray(x);
const shape=(value,required,optional=[])=>object(value) &&
  required.every(key=>Object.hasOwn(value,key)) &&
  Object.keys(value).every(key=>required.includes(key)||optional.includes(key));
const dayId=id=>typeof id==='string' &&
  /^phuquoc-2026:2026-10-1[0-5]$/.test(id);
const ref=value=>shape(value,['type','id']) && REF_TYPES.has(value.type) &&
  typeof value.id==='string' && REF_ID_RE.test(value.id) &&
  (value.type!=='card' || REF_CARDS.has(value.id));

/**
 * Validate a fixed v1 assertion, not a write command. `gitContext` is supplied
 * from independently checked GitHub commit/compare data by the C2 worker.
 * C2 must also compare the full expected arrays against the live public payload.
 */
export function validateRequest(rawBytes,gitContext) {
  if(!(rawBytes instanceof Uint8Array) || rawBytes.byteLength===0 ||
      rawBytes.byteLength>128*1024) fail();
  let request;
  try {
    const text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(rawBytes);
    request=JSON.parse(text);
  } catch {fail();}
  if(!shape(request,['schema_version','request_id','target','itinerary_id',
      'expected_content_revision','changed_day_ids','expected'],['previous_request_id']) ||
      request.schema_version!==1 || typeof request.request_id!=='string' ||
      !UUID_RE.test(request.request_id) ||
      request.target!=='production' || request.itinerary_id!=='phuquoc-2026' ||
      typeof request.expected_content_revision!=='string' ||
      !REVISION_RE.test(request.expected_content_revision) ||
      (Object.hasOwn(request,'previous_request_id') &&
        (typeof request.previous_request_id!=='string' ||
          !UUID_RE.test(request.previous_request_id) || request.previous_request_id===request.request_id))) fail();

  const ids=request.changed_day_ids;
  if(!Array.isArray(ids) || ids.length===0 || ids.length>6 ||
      !ids.every(dayId) || new Set(ids).size!==ids.length ||
      !Array.isArray(request.expected) || request.expected.length!==ids.length) fail();
  const expectedIds=new Set();
  for(const row of request.expected) {
    if(!shape(row,['day_id','main_card_slug','meals','transfers']) ||
        !ids.includes(row.day_id) || expectedIds.has(row.day_id) ||
        (row.main_card_slug!==null && !MAIN_CARDS.has(row.main_card_slug)) ||
        !Array.isArray(row.meals) || !Array.isArray(row.transfers) ||
        row.meals.length+row.transfers.length>32) fail();
    expectedIds.add(row.day_id);
    const segments=new Set();
    for(const meal of row.meals) {
      if(!shape(meal,['segment_id','ref']) || typeof meal.segment_id!=='string' ||
          !SEGMENT_RE.test(meal.segment_id) ||
          segments.has(meal.segment_id) || !ref(meal.ref) ||
          !['food','pool'].includes(meal.ref.type)) fail();
      segments.add(meal.segment_id);
    }
    for(const transfer of row.transfers) {
      if(!shape(transfer,['segment_id','from_ref','to_ref','mode']) ||
          typeof transfer.segment_id!=='string' || !SEGMENT_RE.test(transfer.segment_id) ||
          segments.has(transfer.segment_id) ||
          !ref(transfer.from_ref) || !ref(transfer.to_ref) || !MODES.has(transfer.mode)) fail();
      segments.add(transfer.segment_id);
    }
  }

  const context=gitContext;
  const path=`bridge/site-check/requests/${request.request_id}.json`;
  if(!object(context) || context.repository!=='ga815647/phu-quoc-2026-mobile' ||
      context.event!=='push' || context.branch!==`chat-site-check/${request.request_id}` ||
      typeof context.requestSha!=='string' || !SHA_RE.test(context.requestSha) ||
      !Array.isArray(context.parents) || context.parents.length!==1 ||
      typeof context.parents[0]!=='string' || !SHA_RE.test(context.parents[0]) ||
      context.parents[0]===context.requestSha || context.mainAncestor!==true ||
      !Array.isArray(context.files) || context.files.length!==1 ||
      !shape(context.files[0],['filename','status']) ||
      context.files[0].filename!==path || context.files[0].status!=='added') fail();
  return request;
}
