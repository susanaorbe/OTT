const API = { channels: './data/channels.json', events: './data/events_cdn.json', workflowRuns: 'https://api.github.com/repos/susanaorbe/OTT/actions/workflows/update_mi_tv.yml/runs?per_page=10' };
const FAVORITES_KEY = 'mi-tv-favorites-v1';
const HIDDEN_CHANNELS_KEY = 'mi-tv-hidden-channels-v1';
const state = { view: 'sports', channels: [], events: [], competition: 'all', channelLetter: 'all', channelMode: 'all', favorites: loadFavorites(), hiddenChannels: loadHiddenChannels(), hiddenSelection: new Set(), sourceErrors: [], lastUpdated: null };
let eventRefreshTimer = null;
const EVENT_REFRESH_DELAY_MS = 61000;
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

// Todos los dispositivos usan el mismo reproductor web de Mi TV.
function normalizeAgendaChannelName(value) {
  return String(value || '').toLocaleLowerCase('es')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/\([^)]*\)/g, '').replace(/\s+/g, ' ').trim();
}
function normalizeChannelMatchName(value) {
  // La calidad puede aparecer al final o antes del país (p. ej. HD UK).
  return normalizeAgendaChannelName(value)
    .replace(/\b(?:fhd|uhd|hd|4k|sd)\b/gi, ' ')
    .replace(/\s+/g, ' ').trim();
}
function findCatalogChannel(channelValue) {
  // Si el evento CDN incluye el identificador, es la correspondencia más fiable.
  const channelId = channelValue && typeof channelValue === 'object'
    ? (channelValue.id || channelValue.channel_id || channelValue.channelId || '') : '';
  if (channelId) {
    const byId = state.channels.filter(channel => String(channel.id || channel.channel_id || channel.channelId || '') === String(channelId));
    if (byId.length === 1) return byId[0];
  }
  const channelName = channelValueName(channelValue);
  const wanted = normalizeAgendaChannelName(channelName);
  if (!wanted) return null;
  const exact = state.channels.filter(channel => normalizeAgendaChannelName(channel.name) === wanted);
  if (exact.length === 1) return exact[0];
  if (exact.length > 1) return exact.find(isPlaybackAllowed) || exact[0];

  // La agenda puede nombrar un canal sin indicar su calidad (p. ej. DAZN F1),
  // mientras que el catálogo sí la especifica (DAZN F1 FHD). Solo aceptamos
  // la equivalencia si identifica un único canal para evitar enlaces ambiguos.
  const canonical = normalizeChannelMatchName(channelName);
  if (!canonical) return null;
  const matches = state.channels.filter(channel => normalizeChannelMatchName(channel.name) === canonical);
  return matches.length === 1 ? matches[0] : null;
}
function channelValueName(channel) {
  return typeof channel === 'string' ? channel : (channel?.channel_name || channel?.name || '');
}
function eventChannelsForCurrentSource(ev) {
  return Array.isArray(ev?.channels) ? ev.channels : [];
}
function renderAgendaChannel(channelValue) {
  const name = channelValueName(channelValue) || 'Canal';
  const catalogChannel = findCatalogChannel(channelValue);
  const url = safePlayerUrl(channelValue) || (catalogChannel ? safePlayerUrl(catalogChannel) : null);
  if (!url) return `<span class="channel-chip" title="CDN Live TV no proporciona una URL oficial válida para este canal">${esc(name)}</span>`;
  return `<a class="channel-chip channel-chip-link" href="#reproductor" data-agenda-player-url="${esc(url)}" data-agenda-player-name="${esc(name)}" title="Abrir ${esc(name)} en el reproductor de CDN Live TV">${esc(name)} 🔗</a>`;
}

function loadFavorites() { try { return new Set(JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]')); } catch { return new Set(); } }
function saveFavorites() { localStorage.setItem(FAVORITES_KEY, JSON.stringify([...state.favorites])); updateFavoriteCount(); }
function loadHiddenChannels() { try { return new Set(JSON.parse(localStorage.getItem(HIDDEN_CHANNELS_KEY) || '[]')); } catch { return new Set(); } }
function saveHiddenChannels() { localStorage.setItem(HIDDEN_CHANNELS_KEY, JSON.stringify([...state.hiddenChannels])); }
function esc(value='') { return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function keyOf(channel) { return `${String(channel.name || '').trim().toLowerCase()}|${String(channel.code || '').trim().toLowerCase()}`; }
function updateFavoriteCount() {
  const counter = $('#fav-count');
  if (!counter) return;
  counter.textContent = String(state.channels.filter(ch =>
    state.favorites.has(`c:${keyOf(ch)}`) && !state.hiddenChannels.has(keyOf(ch))
  ).length);
}

function showNotice(message) { const n=$('#notice'); n.textContent=message; n.classList.add('show'); clearTimeout(showNotice.timer); showNotice.timer=setTimeout(()=>n.classList.remove('show'),3200); }
function setView(view) {
  state.view = view === 'channels' ? 'channels' : 'sports';
  $$('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.view === state.view));
  $$('.view').forEach(v => v.classList.toggle('active', v.id === `${state.view}-view`));
  const titles = {
    channels: ['Canales de televisión', 'Catálogo completo de CDN Live TV. Organiza tus favoritos y oculta los canales que no quieras ver.'],
    sports: ['Agenda de CDN Live TV', 'Todos los eventos publicados por CDN Live TV y los canales asociados a cada emisión.']
  };
  $('#page-title').textContent = titles[state.view][0];
  $('#page-subtitle').textContent = titles[state.view][1];
  const agendaHeading = $('#sports-view .section-heading h2');
  const agendaCaption = $('#sports-view .section-heading .muted');
  if (agendaHeading) agendaHeading.textContent = 'Agenda de CDN Live TV';
  if (agendaCaption) agendaCaption.textContent = 'Todos los eventos publicados por CDN Live TV y los canales asociados a cada emisión.';
  $('#competition-filter').style.display = state.view === 'sports' ? '' : 'none';
  $('#channel-letter-filter').hidden = state.view !== 'channels';
  $('#search-input').placeholder = state.view === 'sports' ? 'Buscar evento, competición o canal…' : 'Buscar canal…';
  renderAll();
}

function installCdnUi() {
  const oldFavoritesNav = $('.nav-btn[data-view="favorites"]');
  if (oldFavoritesNav) oldFavoritesNav.remove();
  const oldFavoritesView = $('#favorites-view');
  if (oldFavoritesView) oldFavoritesView.remove();
  const style = document.createElement('style');
  style.textContent = `
    #sport-tabs, #date-tabs, #source-tabs { display:none !important; }
    #channel-letter-filter { display:flex; flex-wrap:wrap; align-items:center; gap:7px; }
    #channel-letter-filter[hidden] { display:none !important; }
    .channel-mode-controls { display:flex; flex-wrap:wrap; gap:7px; margin-left:8px; }
    .hidden-bulk-actions { display:flex; flex-wrap:wrap; gap:8px; width:100%; margin-top:8px; }
    .hidden-bulk-actions[hidden] { display:none !important; }
    .text-action { border:1px solid var(--line); background:var(--panel2); color:var(--text); border-radius:8px; padding:7px 10px; cursor:pointer; font:inherit; font-size:12px; }
    .text-action:disabled { opacity:.45; cursor:not-allowed; }
    .hidden-select-label { display:flex; align-items:center; gap:5px; color:var(--muted); font-size:11px; }
    .channel-unavailable { opacity:.78; }
    .channel-availability { font-size:11px; color:var(--muted); }
    .channel-card .card-actions { display:flex; align-items:center; gap:6px; }
    .channel-country { display:none !important; }
    .channel-card-clickable[aria-label^="No disponible"] { cursor:default; }
  `;
  document.head.appendChild(style);
}
installCdnUi();

function extractChannels(payload) { return Array.isArray(payload?.channels) ? payload.channels : []; }
function dateKeyFromValue(value) {
  const raw=String(value||'');
  const iso=raw.match(/(\d{4})-(\d{2})-(\d{2})/);
  if(iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  const local=raw.match(/\b(\d{1,2})\/(\d{1,2})\/(\d{4})\b/);
  if(local) return `${local[3]}-${local[2].padStart(2,'0')}-${local[1].padStart(2,'0')}`;
  if(/^\d{10,13}$/.test(raw)) {
    const d=new Date(Number(raw.length===10?raw+'000':raw));
    if(!Number.isNaN(d.getTime())) { const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d); const obj=Object.fromEntries(parts.map(p=>[p.type,p.value])); return `${obj.year}-${obj.month}-${obj.day}`; }
  }
  return '';
}
function extractCdnEvents(payload) {
  const root=payload?.['cdn-live-tv'] || payload?.data?.['cdn-live-tv'] || payload?.['cdnlivetv.tv'] || payload?.data?.['cdnlivetv.tv'] || payload || {};
  const out=[];
  for (const [category, items] of Object.entries(root)) {
    if (!Array.isArray(items)) continue;
    for (const item of items) {
      if (!item || typeof item !== 'object') continue;
      const fallbackSport = ({Soccer:'Fútbol',NBA:'Baloncesto',Tennis:'Tenis',Motorsport:'Motor',Motor:'Motor'})[category] || category;
      out.push({
        ...item,
        date:item.date||dateKeyFromValue(item.start||item.time),
        sport:item.agenda_sport||fallbackSport,
        icon:item.agenda_icon||item.icon,
        tournament:item.agenda_competition||item.tournament||item.competition||item.league,
        eventTitle:item.agenda_event_title||item.eventTitle||item.title,
        competitionKey:item.agenda_competition_key||item.competitionKey,
        featured:item.agenda_featured===true||item.featured===true,
        source:'cdn'
      });
    }
  }
  return out;
}
function isPlaybackAllowed(channel) {
  return channel?.playback_allowed === true && Boolean(safePlayerUrl(channel));
}
function safePlayerUrl(channel) {
  const value=channel?.player_url || channel?.url;
  if(!value)return null;
  try {
    const u=new URL(value);
    const required = ['name', 'code', 'user', 'plan'];
    if(u.protocol!=='https:' || !['cdnlivetv.tv','www.cdnlivetv.tv'].includes(u.hostname) || u.pathname!=='/api/v1/channels/player/' || required.some(key => !u.searchParams.has(key)) || u.searchParams.get('user') !== 'cdnlivetv' || u.searchParams.get('plan') !== 'free' || !u.searchParams.get('name')) return null;
    return u.href;
  } catch { return null; }
}
function channelCard(ch) {
  const k = keyOf(ch);
  const saved = state.favorites.has(`c:${k}`);
  const playable = Boolean(safePlayerUrl(ch));
  const hiddenMode = state.channelMode === 'hidden';
  const checked = state.hiddenSelection.has(k);
  const image = ch.image
    ? `<img class="channel-logo" src="${esc(ch.image)}" alt="" loading="lazy" onerror="this.style.display='none'">`
    : `<div class="channel-logo channel-placeholder">${esc((ch.name || '?').slice(0, 1).toUpperCase())}</div>`;
  const availability = playable ? '▶ Abrir reproductor' : 'Reproductor no disponible';
  const actions = hiddenMode
    ? `<label class="hidden-select-label"><input type="checkbox" data-select-hidden="${esc(k)}" ${checked ? 'checked' : ''}> Seleccionar</label><button class="text-action" data-show-channel="${esc(k)}" type="button">Mostrar</button>`
    : `<button class="icon-btn ${saved ? 'saved' : ''}" data-fav-channel="${esc(k)}" aria-label="${saved ? 'Quitar' : 'Añadir'} favorito" title="${saved ? 'Quitar favorito' : 'Añadir a favoritos'}">${saved ? '★' : '☆'}</button><button class="icon-btn" data-hide-channel="${esc(k)}" aria-label="Ocultar canal" title="Ocultar canal">◉</button>`;
  return `<article class="channel-card channel-card-clickable ${playable ? '' : 'channel-unavailable'}" data-channel-card="${esc(k)}" role="button" tabindex="0" aria-label="${playable ? 'Abrir' : 'No disponible:'} ${esc(ch.name || 'canal')}"><div class="channel-top">${image}<div><div class="channel-name">${esc(ch.name || 'Canal sin nombre')}</div></div></div><div class="channel-bottom"><span class="channel-availability">${availability}</span><div class="card-actions">${actions}</div></div></article>`;
}
function filteredChannels(list) {
  const q = $('#search-input').value.trim().toLocaleLowerCase('es');
  return list.filter(ch => {
    const key = keyOf(ch);
    const name = String(ch.name || '').trim();
    const searchOk = !q || name.toLocaleLowerCase('es').includes(q);
    const first = name.normalize('NFD').replace(/[\u0300-\u036f]/g, '').charAt(0).toUpperCase();
    const letter = /^[A-Z]$/.test(first) ? first : '#';
    const letterOk = state.channelLetter === 'all' || letter === state.channelLetter;
    const hidden = state.hiddenChannels.has(key);
    const modeOk = state.channelMode === 'hidden' ? hidden
      : state.channelMode === 'favorites' ? (!hidden && state.favorites.has(`c:${key}`))
      : !hidden;
    return searchOk && letterOk && modeOk;
  }).sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'es', { sensitivity: 'base', numeric: true }));
}
function renderChannelModeControls() {
  const host = $('#channel-letter-filter');
  if (!host) return;
  let controls = $('#channel-mode-controls');
  if (!controls) {
    controls = document.createElement('div');
    controls.id = 'channel-mode-controls';
    controls.className = 'channel-mode-controls';
    controls.innerHTML = `<button class="letter-filter-btn" data-channel-mode="favorites" type="button">★ Favoritos <span id="fav-count" class="count">0</span></button><button class="letter-filter-btn" data-channel-mode="hidden" type="button">◉ Ocultos <span id="hidden-count" class="count">0</span></button>`;
    host.appendChild(controls);
    controls.querySelectorAll('[data-channel-mode]').forEach(button => button.addEventListener('click', () => {
      state.channelMode = button.dataset.channelMode;
      state.channelLetter = 'all';
      state.hiddenSelection.clear();
      $$('[data-letter]').forEach(item => item.classList.toggle('active', item.dataset.letter === 'all'));
      renderChannels();
    }));
  }
  controls.querySelectorAll('[data-channel-mode]').forEach(button => button.classList.toggle('active', button.dataset.channelMode === state.channelMode));
  const hiddenCount = $('#hidden-count');
  if (hiddenCount) hiddenCount.textContent = String(state.hiddenChannels.size);
  let bulk = $('#hidden-bulk-actions');
  if (state.channelMode === 'hidden') {
    if (!bulk) {
      bulk = document.createElement('div');
      bulk.id = 'hidden-bulk-actions';
      bulk.className = 'hidden-bulk-actions';
      bulk.innerHTML = `<button class="text-action" data-hidden-action="show-selected" type="button">Mostrar seleccionados</button><button class="text-action" data-hidden-action="show-all" type="button">Mostrar todos</button>`;
      host.appendChild(bulk);
      bulk.querySelector('[data-hidden-action="show-selected"]').addEventListener('click', showSelectedChannels);
      bulk.querySelector('[data-hidden-action="show-all"]').addEventListener('click', showAllChannels);
    }
    bulk.hidden = false;
    bulk.querySelector('[data-hidden-action="show-selected"]').disabled = state.hiddenSelection.size === 0;
  } else if (bulk) bulk.hidden = true;
}
function renderChannels() {
  const filtered = filteredChannels(state.channels);
  const target = $('#channels-grid');
  target.innerHTML = filtered.length ? filtered.map(channelCard).join('') : `<div class="empty-state">${state.channelMode === 'hidden' ? 'No tienes canales ocultos.' : state.channelMode === 'favorites' ? 'No tienes canales favoritos visibles.' : 'No hay canales que coincidan con la búsqueda.'}</div>`;
  $('#channels-caption').textContent = `${filtered.length} canales ${state.channelMode === 'hidden' ? 'ocultos' : state.channelMode === 'favorites' ? 'favoritos' : 'visibles'} · ${state.channels.length} en el catálogo`;
  renderChannelModeControls();
  updateFavoriteCount();
  bindChannelActions();
}
function hideChannel(key) {
  state.hiddenChannels.add(key);
  state.hiddenSelection.delete(key);
  saveHiddenChannels();
  renderChannels();
}
function showChannel(key) {
  state.hiddenChannels.delete(key);
  state.hiddenSelection.delete(key);
  saveHiddenChannels();
  renderChannels();
}
function showSelectedChannels() {
  for (const key of state.hiddenSelection) state.hiddenChannels.delete(key);
  state.hiddenSelection.clear();
  saveHiddenChannels();
  renderChannels();
}
function showAllChannels() {
  state.hiddenChannels.clear();
  state.hiddenSelection.clear();
  saveHiddenChannels();
  renderChannels();
}

function eventTitle(ev) {
  if(ev.agenda_event_title) return ev.agenda_event_title;
  if(ev.eventTitle) return ev.eventTitle;
  return ev.event || ev.title || ev.name || [ev.homeTeam,ev.awayTeam].filter(Boolean).join(' vs ') || 'Evento deportivo';
}
function eventDateLabel(ev) {
  if(!ev.date) return '';
  const m=String(ev.date).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if(!m) return String(ev.date);
  return new Intl.DateTimeFormat('es-ES',{day:'2-digit',month:'2-digit',year:'numeric'}).format(new Date(Number(m[1]),Number(m[2])-1,Number(m[3]),12));
}
function eventSortKey(ev) {
  const date=String(ev.date||dateKeyFromValue(ev.start||ev.time)||''); const time=eventTimeLabel(ev);
  return `${date||'9999-99-99'}T${time.match(/\d{1,2}:\d{2}/)?.[0]||'99:99'}`;
}
function eventTimeLabel(ev) { const raw=String(ev.start||ev.time||''); const match=raw.match(/\d{1,2}:\d{2}/); if(match)return match[0]; if(/^\d{10,13}$/.test(raw)){const d=new Date(Number(raw.length===10?raw+'000':raw));if(!Number.isNaN(d.getTime()))return new Intl.DateTimeFormat('es-ES',{timeZone:'Europe/Madrid',hour:'2-digit',minute:'2-digit',hour12:false}).format(d);} return raw; }
function eventCard(ev) {
  const status = String(ev.status || '').toLowerCase();
  const channels = eventChannelsForCurrentSource(ev);
  const title = eventTitle(ev);
  const when = [eventDateLabel(ev), eventTimeLabel(ev)].filter(Boolean).join(' · ') || 'Horario no indicado';
  const chips = channels.map(renderAgendaChannel).join('');
  const statusLabel = status === 'live' ? 'EN DIRECTO'
    : status === 'finished' ? 'FINALIZADO'
    : status === 'upcoming' || status === 'ns' ? 'PRÓXIMO'
    : status.toUpperCase() || 'ESTADO NO INDICADO';
  const sportLabel = ev.icon ? `${ev.icon} ${ev.sport}` : (ev.sport === 'Soccer' ? '⚽ Fútbol' : ev.sport || 'Deporte no indicado');
  return `<article class="event-card"><div class="event-main"><div class="event-meta"><span>${esc(sportLabel)}</span><span>·</span><span>${esc(ev.tournament || ev.competition || ev.league || 'Competición no indicada')}</span>${ev.country ? `<span>·</span><span>${esc(ev.country)}</span>` : ''}</div><div class="event-title">${esc(title)}</div><div class="event-sub">${esc(when)}</div>${chips ? `<div class="event-channels">${chips}</div>` : '<div class="event-sub">No hay canales asociados a este evento.</div>'}</div><div class="event-side"><span class="event-status ${status === 'live' ? 'live' : ''}">${esc(statusLabel)}</span></div></article>`;
}

function eventSearchText(ev) {
  const channels=eventChannelsForCurrentSource(ev).map(channelValueName).join(' ');
  return `${ev.homeTeam||''} ${ev.awayTeam||''} ${eventTitle(ev)} ${ev.tournament||''} ${ev.competition||''} ${ev.country||''} ${channels} ${ev.source||''}`.toLocaleLowerCase('es');
}
function timeSlot(ev) {
  const value=eventTimeLabel(ev).match(/(\d{1,2}):(\d{2})/);
  if(!value)return '';
  const mins=Number(value[1])*60+Number(value[2]);
  return mins<=419?'madrugada':mins<=839?'manana':mins<=1229?'tarde':'noche';
}
function todayKey() {
  const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
  const obj=Object.fromEntries(parts.map(p=>[p.type,p.value])); return `${obj.year}-${obj.month}-${obj.day}`;
}
function populateCompetitionFilter() {
  const select=$('#competition-filter'); if(!select)return;
  const previous=state.competition;
  const values=[...new Set(state.events.map(ev=>String(ev.tournament||ev.competition||ev.league||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'es'));
  select.innerHTML='<option value="all">Todas las competiciones</option>'+values.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');
  state.competition=values.includes(previous)?previous:'all'; select.value=state.competition;
}
function filteredEvents(list) {
  const q = $('#search-input').value.trim().toLocaleLowerCase('es');
  return list.filter(ev => {
    const comp = String(ev.tournament || ev.competition || ev.league || '').trim();
    const compOk = state.competition === 'all' || comp === state.competition;
    return compOk && (!q || eventSearchText(ev).includes(q));
  });
}

function renderEvents() {
  const filtered = filteredEvents(state.events).sort((a, b) => eventSortKey(a).localeCompare(eventSortKey(b)));
  const target = $('#events-list');
  target.innerHTML = filtered.length ? filtered.map(eventCard).join('') : '<div class="empty-state">No hay eventos disponibles con estos criterios.</div>';
  $$('[data-agenda-player-url]').forEach(link => link.addEventListener('click', event => {
    event.preventDefault();
    openPlayer({ name: link.dataset.agendaPlayerName || 'Canal CDN Live TV', player_url: link.dataset.agendaPlayerUrl });
  }));
}

function bindChannelActions() {
  $$('[data-fav-channel]').forEach(btn => btn.addEventListener('click', event => {
    event.stopPropagation();
    toggleFavorite(`c:${btn.dataset.favChannel}`);
  }));
  $$('[data-hide-channel]').forEach(btn => btn.addEventListener('click', event => {
    event.stopPropagation();
    hideChannel(btn.dataset.hideChannel);
  }));
  $$('[data-show-channel]').forEach(btn => btn.addEventListener('click', event => {
    event.stopPropagation();
    showChannel(btn.dataset.showChannel);
  }));
  $$('[data-select-hidden]').forEach(input => input.addEventListener('click', event => event.stopPropagation()));
  $$('[data-select-hidden]').forEach(input => input.addEventListener('change', () => {
    if (input.checked) state.hiddenSelection.add(input.dataset.selectHidden);
    else state.hiddenSelection.delete(input.dataset.selectHidden);
    const bulkButton = $('[data-hidden-action="show-selected"]');
    if (bulkButton) bulkButton.disabled = state.hiddenSelection.size === 0;
  }));
  $$('[data-channel-card]').forEach(card => {
    const open = () => {
      const ch = state.channels.find(x => keyOf(x) === card.dataset.channelCard);
      if (ch) openPlayer(ch);
    };
    card.addEventListener('click', event => {
      if (!event.target.closest('[data-fav-channel], [data-hide-channel], [data-show-channel], [data-select-hidden], .hidden-select-label')) open();
    });
    card.addEventListener('keydown', event => {
      if ((event.key === 'Enter' || event.key === ' ') && !event.target.closest('button, input, label')) {
        event.preventDefault();
        open();
      }
    });
  });
}

function toggleFavorite(key) { if(state.favorites.has(key))state.favorites.delete(key);else state.favorites.add(key);saveFavorites();renderAll(); }
function openPlayer(channel) {
  const url=safePlayerUrl(channel); if(!url){showNotice('Este canal no tiene una página oficial de reproducción disponible.');return;}
  $('#player-title').textContent=channel.name || channel.channel_name || 'Canal CDN Live TV'; $('#player-content').innerHTML=`<iframe src="${esc(url)}" title="${esc(channel.name)}" allow="autoplay; encrypted-media; fullscreen; picture-in-picture" allowfullscreen></iframe>`;
  $('#player-dialog').showModal();
  // Suspende el refresco mientras el reproductor esté abierto.
  scheduleEventAutoRefresh();
}
function renderAll() {
  updateFavoriteCount();
  $('#channel-total').textContent=state.channels.length || '0'; $('#event-total').textContent=state.events.length || '0';
  if (state.view === 'channels') renderChannels();
  if (state.view === 'sports') renderEvents();
}
function madridClockParts(date = new Date()) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/Madrid', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
  }).formatToParts(date);
  return Object.fromEntries(parts.map(part => [part.type, part.value]));
}
function updateClock() {
  const current = $('#current-time');
  if (current) {
    const parts = madridClockParts();
    current.textContent = `${parts.hour}:${parts.minute}:${parts.second}`;
  }
  const updated = $('#last-updated');
  if (updated) {
    if (!state.lastUpdated) updated.textContent = 'No disponible';
    else {
      const parsed = new Date(state.lastUpdated);
      updated.textContent = Number.isNaN(parsed.getTime()) ? 'No disponible' :
        new Intl.DateTimeFormat('es-ES', { timeZone: 'Europe/Madrid', dateStyle: 'short', timeStyle: 'medium' }).format(parsed);
    }
  }
}
async function fetchLatestWorkflowRun() {
  try {
    // El repositorio es público: la API de GitHub permite consultar la última ejecución sin token.
    // Se deja la caché HTTP normal para no consumir innecesariamente el límite de la API.
    const response = await fetch(API.workflowRuns, {
      headers: { Accept: 'application/vnd.github+json' },
      cache: 'default'
    });
    if (!response.ok) throw new Error(`GitHub API HTTP ${response.status}`);
    const payload = await response.json();
    const runs = Array.isArray(payload.workflow_runs) ? payload.workflow_runs : [];
    const latestRun = runs.find(run => run.run_started_at) || runs[0] || null;
    state.lastUpdated = latestRun?.run_started_at || latestRun?.created_at || null;
  } catch {
    state.lastUpdated = null;
  }
  updateClock();
}
function madridLocalTimestamp(dateValue, timeValue) {
  const dateMatch = String(dateValue || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const timeMatch = String(timeValue || '').match(/^(\d{1,2}):(\d{2})$/);
  if (!dateMatch || !timeMatch) return NaN;
  const [, year, month, day] = dateMatch;
  const hour = Number(timeMatch[1]);
  const minute = Number(timeMatch[2]);
  if (hour > 23 || minute > 59) return NaN;
  const utcGuess = Date.UTC(Number(year), Number(month) - 1, Number(day), hour, minute);
  const offsetLabel = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Europe/Madrid', timeZoneName: 'longOffset', hour: '2-digit'
  }).formatToParts(new Date(utcGuess)).find(part => part.type === 'timeZoneName')?.value || 'GMT+00:00';
  const offsetMatch = offsetLabel.match(/GMT([+-])(\d{2}):(\d{2})/);
  const offsetMinutes = offsetMatch ? (offsetMatch[1] === '-' ? -1 : 1) * (Number(offsetMatch[2]) * 60 + Number(offsetMatch[3])) : 0;
  return utcGuess - offsetMinutes * 60000;
}
function scheduleEventAutoRefresh() {
  if (eventRefreshTimer) clearTimeout(eventRefreshTimer);
  eventRefreshTimer = null;

  // Un refresco nunca debe interrumpir un canal que se esté reproduciendo.
  const playerDialog = $('#player-dialog');
  if (playerDialog?.open) return;

  const now = Date.now();
  const targets = state.events.map(ev => {
    const date = ev.date || dateKeyFromValue(ev.start || ev.time) || '';
    const time = eventTimeLabel(ev).match(/\d{1,2}:\d{2}/)?.[0] || '';
    const start = madridLocalTimestamp(date, time);
    return Number.isFinite(start) ? start + EVENT_REFRESH_DELAY_MS : NaN;
  }).filter(target => Number.isFinite(target) && target > now).sort((a, b) => a - b);
  if (!targets.length) return;
  const nextTarget = targets[0];
  const delay = Math.min(nextTarget - now, 2147480000);
  eventRefreshTimer = setTimeout(() => {
    eventRefreshTimer = null;
    // Si el reproductor se abrió mientras esperábamos, se pospone el refresco.
    if ($('#player-dialog')?.open) return;
    // Si el objetivo se ha limitado por el máximo de setTimeout, vuelve a calcular.
    if (Date.now() + 1000 < nextTarget) scheduleEventAutoRefresh();
    else window.location.reload();
  }, delay);
}
async function fetchStaticJson(path) {
  const separator=path.includes('?')?'&':'?';
  const response=await fetch(`${path}${separator}v=${Date.now()}`,{cache:'no-store'});
  const json=await response.json();
  if(!response.ok||json.ok===false)throw new Error(json.error||`HTTP ${response.status}`);
  return json;
}
async function loadData() {
  const button = $('#refresh-btn');
  button.disabled = true;
  state.sourceErrors = [];
  try {
    const paths = [API.channels, API.events];
    const labels = ['CDN Live TV (canales)', 'CDN Live TV (eventos)'];
    fetchLatestWorkflowRun();
    const parsed = await Promise.all(paths.map(async (path, index) => {
      try { return await fetchStaticJson(path); }
      catch (error) { state.sourceErrors.push(`${labels[index]}: ${error.message}`); return null; }
    }));
    const [channelsJson, eventsJson] = parsed;
    if (channelsJson) state.channels = extractChannels(channelsJson.data)
      .filter(channel => channel && String(channel.name || '').trim())
      .sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'es', { sensitivity: 'base', numeric: true }));
    if (eventsJson) state.events = extractCdnEvents(eventsJson.data);
    populateCompetitionFilter();
    renderAll();
    updateClock();
    scheduleEventAutoRefresh();
    if (state.sourceErrors.length) showNotice(`Datos parcialmente actualizados. ${state.sourceErrors.length} fuente(s) no disponibles.`);
    else showNotice('Catálogo y agenda de CDN Live TV actualizados.');
    if (!channelsJson) $('#channels-grid').innerHTML = '<div class="empty-state">No se ha podido cargar el catálogo completo de CDN Live TV.</div>';
    if (!eventsJson) $('#events-list').innerHTML = '<div class="empty-state">No se ha podido cargar la agenda de CDN Live TV.</div>';
  } catch (error) {
    showNotice(error.message || 'No se pudieron cargar los datos.');
  } finally {
    button.disabled = false;
  }
}

$$('.nav-btn').forEach(b=>b.addEventListener('click',()=>setView(b.dataset.view)));
$('#refresh-btn').addEventListener('click',loadData);
$('#search-input').addEventListener('input',renderAll);
$$('[data-letter]').forEach(button=>button.addEventListener('click',()=>{
  state.channelLetter=button.dataset.letter;
  $$('[data-letter]').forEach(item=>item.classList.toggle('active',item===button));
  renderChannels();
}));

$('#competition-filter').addEventListener('change',()=>{state.competition=$('#competition-filter').value;renderEvents();});

$('#close-player').addEventListener('click',()=>$('#player-dialog').close());
$('#player-dialog').addEventListener('close',()=>{
  $('#player-content').innerHTML='<p>Selecciona un canal reproducible para abrir su reproductor.</p>';
  // Al cerrar el canal, vuelve a calcular el siguiente refresco pendiente.
  scheduleEventAutoRefresh();
});
$('#channel-letter-filter').hidden=true;
setView('sports');
updateClock();
setInterval(updateClock, 1000);
loadData();
