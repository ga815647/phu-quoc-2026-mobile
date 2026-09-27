const datesEl = document.querySelector('#dates');
const contentEl = document.querySelector('#day-content');
const switches = { a: document.querySelector('#view-a'), b: document.querySelector('#view-b') };
const initial = new URL(location.href);
let selectedDay;
let view;
let selected = {};
let data;

const escapeHTML = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[c]);
const e = escapeHTML;
const maps = key => data.places[key] ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(data.places[key])}` : '';
const mapLink = (item, label = '開啟地圖') => item.map && maps(item.map) ? `<a class="map-link" href="${maps(item.map)}" target="_blank" rel="noopener noreferrer" aria-label="${e(item.title)}：在 Google 地圖搜尋（開新視窗）"><svg aria-hidden="true" viewBox="0 0 20 20"><path d="M10 18s6-5.2 6-10a6 6 0 0 0-12 0c0 4.8 6 10 6 10Z"/><circle cx="10" cy="8" r="2"/></svg>${e(label)}</a>` : '';
const note = item => `<span class="certainty">${e(item.certainty)}</span>`;
const typeName = {anchor:'行程', transit:'交通', meal:'用餐'};

function footer(day) {
  return `<details class="backup"><summary>遇到變動，看看備案 <span aria-hidden="true">＋</span></summary><div class="backup-body">${day.backup.map(b => `<div class="backup-row"><strong>如果：${e(b.trigger)}</strong><p>就：${e(b.action)}</p>${b.map ? mapLink({map:b.map,title:b.trigger}) : ''}</div>`).join('')}</div></details>
    <p class="day-disclaimer">時間只有航班時刻與 OnBird Morning 為已確認；其餘是建議順序／時段，非實測交通時間。餐廳與營運資訊出發前重查。</p>`;
}

function renderA(day) {
  return `<section class="route" aria-label="海岸路線簿：${e(day.name)}">
    <div class="route-intro"><div class="route-overline">${e(day.region)}</div><h2>${e(day.name)}</h2><p>沿著今天的線走；交通和用餐都在路上。</p></div>
    <ol class="route-line">${day.items.map(item => `<li class="route-item ${e(item.type)}"><div class="route-time">${e(item.time)}</div><div class="route-node" aria-hidden="true"></div><div class="route-body"><span class="item-kind">${typeName[item.type]}・${e(item.phase)}</span><h3>${e(item.title)}</h3><p>${e(item.detail)}</p>${note(item)}${mapLink(item)}</div></li>`).join('')}</ol>
    ${footer(day)}
  </section>`;
}

function renderB(day) {
  const focus = day.items.find(item => item.id === selected[day.date]) ?? day.items.find(item => item.id === day.focus) ?? day.items[0];
  const phases = ['上午','下午','傍晚','晚間'];
  return `<section class="focus-view" aria-label="下一站旅程牌：${e(day.name)}">
    <div class="focus-intro"><span>${e(day.region)}</span><h2>${e(day.name)}</h2></div>
    <div class="focus-panel"><div class="focus-kicker"><span>手動選取的站點</span><span class="focus-symbol" aria-hidden="true">↗</span></div><div class="focus-time">${e(focus.time)}</div><h3 tabindex="-1">${e(focus.title)}</h3><p>${e(focus.detail)}</p><div class="focus-meta">${note(focus)}${mapLink(focus, '導航／搜尋地圖')}</div></div>
    <p class="selection-hint">點下面的站點換焦點。這不是即時位置、下一站預測或完成紀錄。</p>
    <div class="phase-list" aria-label="當天所有段落">${phases.filter(phase => day.items.some(item => item.phase === phase)).map(phase => `<details class="phase" ${phase === focus.phase ? 'open' : ''}><summary>${e(phase)} <span>${day.items.filter(item => item.phase === phase).length} 段</span></summary><div class="phase-body">${day.items.filter(item => item.phase === phase).map(item => `<button type="button" class="stop-choice ${item.id === focus.id ? 'picked' : ''}" data-stop="${e(item.id)}" aria-pressed="${item.id === focus.id}"><span class="stop-time">${e(item.time)}</span><span class="stop-details"><strong>${e(item.title)}</strong><small>${typeName[item.type]}・${e(item.certainty)}</small></span><span class="pick-arrow" aria-hidden="true">↗</span></button>`).join('')}</div></details>`).join('')}</div>
    ${footer(day)}
  </section>`;
}

function syncURL() {
  const url = new URL(location.href);
  url.searchParams.set('view', view);
  url.searchParams.set('day', selectedDay);
  history.replaceState(null, '', url);
}

function render() {
  const day = data.days.find(d => d.date === selectedDay);
  document.body.dataset.view = view;
  datesEl.innerHTML = data.days.map(d => `<button type="button" class="date-tab ${d.date === selectedDay ? 'active' : ''}" data-date="${e(d.date)}" ${d.date === selectedDay ? 'aria-current="date"' : ''}><span>10/${Number(d.date.slice(-2))} ${e(d.weekday)}</span><strong>${e(d.name.split('・')[0])}</strong></button>`).join('');
  const activeDate = datesEl.querySelector('.date-tab.active');
  const dateNav = datesEl.closest('.date-nav');
  dateNav.scrollLeft = activeDate.offsetLeft - dateNav.offsetLeft - (dateNav.clientWidth - activeDate.clientWidth) / 2;
  for (const [key, button] of Object.entries(switches)) {
    button.setAttribute('aria-pressed', String(view === key));
    button.classList.toggle('selected', view === key);
  }
  contentEl.innerHTML = view === 'a' ? renderA(day) : renderB(day);
  syncURL();
}

datesEl.addEventListener('click', event => {
  const button = event.target.closest('[data-date]');
  if (!button) return;
  selectedDay = button.dataset.date;
  render();
  datesEl.querySelector('.date-tab.active').focus({ preventScroll: true });
});
document.querySelector('.view-switch').addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button) return;
  view = button.id === 'view-a' ? 'a' : 'b';
  render();
  switches[view].focus({ preventScroll: true });
});
contentEl.addEventListener('click', event => {
  const button = event.target.closest('[data-stop]');
  if (!button) return;
  selected[selectedDay] = button.dataset.stop;
  render();
  contentEl.querySelector('.focus-panel h3').focus({ preventScroll: true });
  contentEl.querySelector('.focus-panel')?.scrollIntoView({ block: 'nearest', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
});
window.addEventListener('popstate', () => {
  const url = new URL(location.href);
  view = url.searchParams.get('view') === 'b' ? 'b' : 'a';
  selectedDay = data.days.some(d => d.date === url.searchParams.get('day')) ? url.searchParams.get('day') : data.days[3].date;
  render();
});

try {
  const response = await fetch('./content.json');
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  data = await response.json();
  view = initial.searchParams.get('view') === 'b' ? 'b' : 'a';
  selectedDay = data.days.some(d => d.date === initial.searchParams.get('day')) ? initial.searchParams.get('day') : '2026-10-13';
  document.querySelector('#source-text').textContent = `快照 ${data.snapshot}；${data.evidence}`;
  render();
} catch {
  contentEl.innerHTML = '<div class="load-error" role="alert"><h2>草案暫時無法載入</h2><p>請在有網路時重新整理此頁；這份預覽不會改動正式行程。</p></div>';
}
