const API = { channels: './data/channels.json', events: './data/events_cdn.json', futbolenlatv: './data/events_futbolenlatv.json', workflowRuns: 'https://api.github.com/repos/susanaorbe/OTT/actions/workflows/update_mi_tv.yml/runs?per_page=10' };
const FAVORITES_KEY = 'mi-tv-favorites-v1';
const state = { view: 'sports', channels: [], events: [], sport: 'all', source: 'all', daypart: 'all', competition: 'all', channelLetter: 'all', favorites: loadFavorites(), sourceErrors: [], lastUpdated: null };
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
  return normalizeAgendaChannelName(value)
    .replace(/\b(?:fhd|uhd|hd|4k|sd)\b\s*$/i, '')
    .replace(/\s+/g, ' ').trim();
}
function findCatalogChannel(channelName) {
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
function eventHasCatalogChannel(ev) {
  return (Array.isArray(ev?.channels) ? ev.channels : []).some(channel => {
    const name = typeof channel === 'string' ? channel : (channel?.channel_name || channel?.name || '');
    return Boolean(findCatalogChannel(name));
  });
}
function renderAgendaChannel(channelValue) {
  const name = typeof channelValue === 'string' ? channelValue : (channelValue?.channel_name || channelValue?.name || 'Canal');
  const safeName = esc(name);
  const catalogChannel = findCatalogChannel(name);
  if (catalogChannel) {
    return `<a class="channel-chip channel-chip-link" href="#canales" data-agenda-channel="${esc(keyOf(catalogChannel))}" title="Abrir ${safeName} en Mi TV">${safeName} 🔗</a>`;
  }
  return `<span class="channel-chip">${safeName}</span>`;
}

function loadFavorites() { try { return new Set(JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]')); } catch { return new Set(); } }
function saveFavorites() { localStorage.setItem(FAVORITES_KEY, JSON.stringify([...state.favorites])); updateFavoriteCount(); }
function esc(value='') { return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function keyOf(channel) { return `${String(channel.name || '').trim().toLowerCase()}|${String(channel.code || '').trim().toLowerCase()}`; }
function updateFavoriteCount() {
  const counter = $('#fav-count');
  if (!counter) return;
  const query = $('#search-input')?.value.trim().toLocaleLowerCase('es') || '';
  const visibleChannels = state.channels.filter(ch =>
    state.favorites.has(`c:${keyOf(ch)}`) && isPlaybackAllowed(ch) &&
    (!query || String(ch.name || '').toLocaleLowerCase('es').includes(query))
  ).length;
  const favoriteEvents = state.events.filter(ev => state.favorites.has(`e:${eventId(ev)}`));
  const visibleEvents = filteredEvents(favoriteEvents).length;
  counter.textContent = String(visibleChannels + visibleEvents);
}

function countryName(code) { const raw=String(code||'').trim(); if(!raw)return 'País no identificado'; if(['other','others','unknown','xx'].includes(raw.toLowerCase()))return 'Otros'; try { return new Intl.DisplayNames(['es'], {type:'region'}).of(raw.toUpperCase()) || raw.toUpperCase(); } catch { return raw.toUpperCase(); } }
function showNotice(message) { const n=$('#notice'); n.textContent=message; n.classList.add('show'); clearTimeout(showNotice.timer); showNotice.timer=setTimeout(()=>n.classList.remove('show'),3200); }
function setView(view) {
  state.view=view;
  $$('.nav-btn').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
  $$('.view').forEach(v=>v.classList.toggle('active',v.id===`${view}-view`));
  const titles={channels:['Canales de televisión','Explora el catálogo disponible y guarda tus canales favoritos.'],sports:['Agenda deportiva','La agenda personalizada de Futbolenlatv determina qué eventos se muestran.'],favorites:['Tus favoritos','Tus canales y eventos guardados en este navegador.']};
  $('#page-title').textContent=titles[view][0]; $('#page-subtitle').textContent=titles[view][1];
  $('#competition-filter').style.display=view==='sports'?'':'none';
  $('#channel-letter-filter').hidden=view!=='channels';
  $('#search-input').placeholder=view==='sports'?'Buscar equipo, competición o canal…':view==='favorites'?'Buscar en tus favoritos…':'Buscar canal…';
  renderAll();
}
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
function normalizeFutbolenlatv(payload) {
  return (Array.isArray(payload?.events)?payload.events:[]).map(ev=>({
    eventId:ev.id, source:'futbolenlatv', date:ev.date, start:ev.time, sport:ev.sport,
    icon:ev.icon, tournament:ev.competition, eventTitle:ev.event,
    channels:(ev.channels||[]).map(name=>({channel_name:name})), featured:ev.featured===true,
    competitionKey:ev.competition_key, status:'agenda'
  }));
}
function isPlaybackAllowed(channel) {
  return channel?.playback_allowed === true && Boolean(safePlayerUrl(channel));
}
function safePlayerUrl(channel) {
  const value=channel?.player_url;
  if(!value)return null;
  try {
    const u=new URL(value);
    if(u.protocol!=='https:' || !['cdnlivetv.tv','www.cdnlivetv.tv'].includes(u.hostname) || u.pathname!=='/api/v1/channels/player/') return null;
    return u.href;
  } catch { return null; }
}
function channelCard(ch) {
  const k=keyOf(ch), saved=state.favorites.has(`c:${k}`);
  const image=ch.image?`<img class="channel-logo" src="${esc(ch.image)}" alt="" loading="lazy" onerror="this.style.display='none'">`:`<div class="channel-logo channel-placeholder">${esc((ch.name||'?').slice(0,1).toUpperCase())}</div>`;
  return `<article class="channel-card channel-card-clickable" data-channel-card="${esc(k)}" role="button" tabindex="0" aria-label="Abrir ${esc(ch.name||'canal')}"><div class="channel-top">${image}<div><div class="channel-name">${esc(ch.name||'Canal sin nombre')}</div><div class="channel-country">${esc(countryName(ch.code))}</div></div></div><div class="channel-bottom"><span class="channel-availability">▶ Reproducir</span><div class="card-actions"><button class="icon-btn ${saved?'saved':''}" data-fav-channel="${esc(k)}" aria-label="${saved?'Quitar':'Añadir'} favorito">${saved?'★':'☆'}</button></div></div></article>`;
}
function filteredChannels(list) {
  const q=$('#search-input').value.trim().toLocaleLowerCase('es');
  return list.filter(ch=>{
    const name=String(ch.name||'').trim();
    const searchOk=!q||name.toLocaleLowerCase('es').includes(q);
    const first=name.normalize('NFD').replace(/[\u0300-\u036f]/g,'').charAt(0).toUpperCase();
    const letter=/^[A-Z]$/.test(first)?first:'#';
    const letterOk=state.view!=='channels'||state.channelLetter==='all'||letter===state.channelLetter;
    return searchOk&&letterOk&&isPlaybackAllowed(ch);
  }).sort((a,b)=>String(a.name||'').localeCompare(String(b.name||''),'es',{sensitivity:'base',numeric:true}));
}
function renderChannels() {
  const list=state.view==='favorites'?state.channels.filter(ch=>state.favorites.has(`c:${keyOf(ch)}`)):state.channels;
  const filtered=filteredChannels(list); const target=state.view==='favorites'?$('#favorites-grid'):$('#channels-grid');
  target.innerHTML=filtered.length?filtered.map(channelCard).join(''):'<div class="empty-state">No hay canales reproducibles que coincidan con la búsqueda.</div>';
  $('#channels-caption').textContent=`${filtered.length} canales reproducibles mostrados`;
  updateFavoriteCount();
  bindChannelActions();
}
function sportKey(sport) {
  const s=String(sport||'').toLowerCase();
  if(s==='soccer'||s==='fútbol'||s==='futbol') return 'football';
  if(s==='baloncesto') return 'basketball';
  if(s==='tenis') return 'tennis';
  if(s==='motor') return 'motor';
  return s;
}
function eventId(ev) {
  if(ev.eventId) return String(ev.eventId);
  return String(ev.gameID||`${ev.source||'cdn'}:${ev.sport}:${ev.homeTeam||''}:${ev.awayTeam||''}:${ev.start||ev.time||''}`);
}
function eventTitle(ev) {
  if(ev.agenda_event_title) return ev.agenda_event_title;
  if(ev.eventTitle) return ev.eventTitle;
  return [ev.homeTeam,ev.awayTeam].filter(Boolean).join(' vs ')||'Evento deportivo';
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
  const status=String(ev.status||'').toLowerCase(), channels=Array.isArray(ev.channels)?ev.channels:[];
  const title=eventTitle(ev), when=[eventDateLabel(ev),eventTimeLabel(ev)].filter(Boolean).join(' · ')||'Horario no indicado';
  const chips=channels.map(renderAgendaChannel).join('');
  const id=eventId(ev), saved=state.favorites.has(`e:${id}`);
  const sourceLabel = ev.source === 'both' ? 'CDN + Futbolenlatv'
    : eventHasCatalogChannel(ev) ? 'Futbolenlatv + canales CDN' : 'Futbolenlatv';
  const statusLabel=status==='live'?'EN DIRECTO':status==='finished'?'FINALIZADO':status==='upcoming'?'PRÓXIMO':status==='agenda'?'AGENDA PERSONALIZADA':status.toUpperCase()||'ESTADO NO INDICADO';
  const featured=ev.featured?'<span class="featured-tag">★ Selección de tu agenda</span>':'';
  const sportLabel=ev.icon?`${ev.icon} ${ev.sport}`:(ev.sport==='Soccer'?'⚽ Fútbol':ev.sport);
  return `<article class="event-card"><div class="event-main"><div class="event-meta"><span>${esc(sportLabel)}</span><span>·</span><span>${esc(ev.tournament||ev.competition||'Competición no indicada')}</span><span>·</span><span>${esc(sourceLabel)}</span>${ev.country?`<span>·</span><span>${esc(ev.country)}</span>`:''}</div><div class="event-title">${esc(title)}</div><div class="event-sub">${esc(when)}</div>${featured}${chips?`<div class="event-channels">${chips}</div>`:''}</div><div class="event-side"><span class="event-status ${status==='live'?'live':''}">${esc(statusLabel)}</span><button class="icon-btn ${saved?'saved':''}" data-fav-event="${esc(id)}" aria-label="${saved?'Quitar':'Añadir'} favorito">${saved?'★':'☆'}</button></div></article>`;
}
function eventSearchText(ev) {
  const channels=(ev.channels||[]).map(c=>typeof c==='string'?c:(c.channel_name||c.name||'')).join(' ');
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
  const values=[...new Set(state.events.map(ev=>String(ev.tournament||ev.competition||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'es'));
  select.innerHTML='<option value="all">Todas las competiciones</option>'+values.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');
  state.competition=values.includes(previous)?previous:'all'; select.value=state.competition;
}
function filteredEvents(list) {
  const q=$('#search-input').value.trim().toLocaleLowerCase('es'); const today=todayKey();
  return list.filter(ev=>{
    const date=ev.date||dateKeyFromValue(ev.start||ev.time)||'';
    const sportOk=state.sport==='all'||sportKey(ev.sport)===state.sport;
    // La pestaña CDN muestra eventos de la agenda que tengan al menos un
    // canal reproducible en el catálogo, aunque CDN no publique una ficha
    // independiente del evento. La agenda sigue siendo la fuente autorizada.
    const sourceOk = state.source === 'all' || (state.source === 'cdn'
      ? ev.source === 'both' || eventHasCatalogChannel(ev)
      : ev.source === state.source || ev.source === 'both');
    const comp=String(ev.tournament||ev.competition||'').trim();
    const compOk=state.competition==='all'||comp===state.competition;
    let dayOk=true;
    if(state.daypart==='today')dayOk=date===today;
    else if(state.daypart==='upcoming')dayOk=Boolean(date&&date>today);
    else if(state.daypart==='featured')dayOk=ev.featured===true;
    else if(['madrugada','manana','tarde','noche'].includes(state.daypart))dayOk=date===today&&timeSlot(ev)===state.daypart;
    return sportOk&&sourceOk&&compOk&&dayOk&&(!q||eventSearchText(ev).includes(q));
  });
}
function renderEvents() {
  const list=state.view==='favorites'?state.events.filter(ev=>state.favorites.has(`e:${eventId(ev)}`)):state.events;
  const filtered=filteredEvents(list).sort((a,b)=>eventSortKey(a).localeCompare(eventSortKey(b)));
  const target=state.view==='favorites'?$('#favorite-events'):$('#events-list');
  target.innerHTML=filtered.length?filtered.map(eventCard).join(''):'<div class="empty-state">No hay eventos para mostrar con estos filtros.</div>';
  updateFavoriteCount();
  $$('[data-fav-event]').forEach(btn=>btn.addEventListener('click',()=>toggleFavorite(`e:${btn.dataset.favEvent}`)));
  $$('[data-agenda-channel]').forEach(link=>link.addEventListener('click',event=>{
    event.preventDefault();
    const channel=state.channels.find(item=>keyOf(item)===link.dataset.agendaChannel);
    if(channel)openPlayer(channel);
  }));
}
function bindChannelActions() {
  $$('[data-fav-channel]').forEach(btn=>btn.addEventListener('click',event=>{event.stopPropagation();toggleFavorite(`c:${btn.dataset.favChannel}`);}));
  $$('[data-channel-card]').forEach(card=>{
    const open=()=>{const ch=state.channels.find(x=>keyOf(x)===card.dataset.channelCard);if(ch)openPlayer(ch);};
    card.addEventListener('click',event=>{if(!event.target.closest('[data-fav-channel]'))open();});
    card.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();open();}});
  });
}
function toggleFavorite(key) { if(state.favorites.has(key))state.favorites.delete(key);else state.favorites.add(key);saveFavorites();renderAll(); }
function openPlayer(channel) {
  const url=safePlayerUrl(channel); if(!url){showNotice('Este canal no tiene una página oficial de reproducción disponible.');return;}
  $('#player-title').textContent=channel.name; $('#player-content').innerHTML=`<iframe src="${esc(url)}" title="${esc(channel.name)}" allow="autoplay; encrypted-media; fullscreen; picture-in-picture" allowfullscreen></iframe>`;
  $('#player-dialog').showModal();
  // Suspende el refresco mientras el reproductor esté abierto.
  scheduleEventAutoRefresh();
}
function renderAll() {
  updateFavoriteCount();
  $('#channel-total').textContent=state.channels.filter(isPlaybackAllowed).length||'0'; $('#event-total').textContent=state.events.length||'0';
  if(state.view==='channels')renderChannels(); if(state.view==='sports')renderEvents(); if(state.view==='favorites'){renderChannels();renderEvents();}
}
function eventTeams(ev) {
  if (ev.homeTeam && ev.awayTeam) return [ev.homeTeam, ev.awayTeam];
  if (!['football', 'basketball', 'tennis'].includes(sportKey(ev.sport))) return null;
  const title = eventTitle(ev);
  const parts = title.split(/\s+-\s+/);
  return parts.length === 2 && parts.every(Boolean) ? parts : null;
}
function normalizeMatchPart(value) {
  return String(value || '').toLocaleLowerCase('es')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, ' ').trim();
}
function eventMatchKey(ev) {
  const date = ev.date || dateKeyFromValue(ev.start || ev.time) || '';
  const time = eventTimeLabel(ev).match(/\d{1,2}:\d{2}/)?.[0] || '';
  if (!date || !time) return '';
  const sport = sportKey(ev.sport || ev.agenda_sport);
  const competition = ev.competitionKey || ev.agenda_competition_key || ev.competition_key || '';

  // En motor no hay equipos: la identidad fiable es la competición y el
  // horario exacto. El texto descriptivo cambia entre Futbolenlatv y CDN.
  if (sport === 'motor') {
    const motorCompetition = normalizeMatchPart(ev.tournament || ev.competition || ev.agenda_competition || competition || '');
    return motorCompetition ? `${sport}|${date}|${time}|${motorCompetition}` : '';
  }

  const teams = eventTeams(ev);
  if (teams) return `${sport}|${date}|${time}|${teams.map(normalizeMatchPart).sort().join('|')}`;

  let title = eventTitle(ev);
  const tournament = String(ev.tournament || ev.competition || ev.agenda_competition || '').trim();
  if (tournament) {
    const escapedTournament = tournament.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    title = title.replace(new RegExp(`^${escapedTournament}\\s*[-–—:]\\s*`, 'i'), '');
  }
  const identity = `${normalizeMatchPart(title)}|${normalizeMatchPart(competition || tournament)}`;
  if (!identity.replace(/[| ]/g, '')) return '';
  return `${sport}|${date}|${time}|${identity}`;
}
function mergeAgenda(cdnEvents, personalEvents) {
  // Futbolenlatv es la lista autorizada: CDN solo enriquece eventos que ya existen allí.
  const cdnByKey = new Map();
  for (const cdnEvent of cdnEvents) {
    const key = eventMatchKey(cdnEvent);
    if (!key) continue;
    if (!cdnByKey.has(key)) cdnByKey.set(key, []);
    cdnByKey.get(key).push(cdnEvent);
  }

  return personalEvents.map(personalEvent => {
    const key = eventMatchKey(personalEvent);
    const match = key ? cdnByKey.get(key)?.[0] : null;
    if (!match) return { ...personalEvent, source: 'futbolenlatv', featured: personalEvent.featured === true };

    const oldChannels = Array.isArray(personalEvent.channels) ? personalEvent.channels : [];
    const cdnChannels = Array.isArray(match.channels) ? match.channels : [];
    const channelKey = channel => normalizeChannelMatchName(typeof channel === 'string' ? channel : (channel?.channel_name || channel?.name || ''));
    const channels = [...oldChannels];
    for (const channel of cdnChannels) {
      const normalized = channelKey(channel);
      if (normalized && !channels.some(existing => channelKey(existing) === normalized)) channels.push(channel);
    }
    return {
      ...personalEvent,
      channels,
      status: match.status || personalEvent.status,
      source: 'both',
      cdnMatched: true,
      // La marca de destacado siempre procede de la agenda personalizada.
      featured: personalEvent.featured === true
    };
  });
}
function madridClockParts(date = new Date()) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/Madrid', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
  }).formatToParts(date);
  return Object.fromEntries(parts.map(part => [part.type, part.value]));
}
function currentMadridDaypart() {
  const parts = madridClockParts();
  const minutes = Number(parts.hour) * 60 + Number(parts.minute);
  return minutes <= 419 ? 'madrugada' : minutes <= 839 ? 'manana' : minutes <= 1229 ? 'tarde' : 'noche';
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
function activateCurrentDaypart() {
  state.daypart = currentMadridDaypart();
  $$('.date-tab').forEach(button => button.classList.toggle('active', button.dataset.daypart === state.daypart));
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
    const paths = [API.channels, API.events, API.futbolenlatv];
    const labels = ['CDN Live TV (canales)', 'CDN Live TV (eventos)', 'Futbolenlatv'];
    // La consulta del reloj de GitHub va en paralelo y no bloquea la carga de la agenda.
    fetchLatestWorkflowRun();
    const parsed = await Promise.all(paths.map(async (path, index) => {
      try { return await fetchStaticJson(path); }
      catch (error) { state.sourceErrors.push(`${labels[index]}: ${error.message}`); return null; }
    }));
    const [channelsJson, eventsJson, ftvJson] = parsed;
    if (channelsJson) state.channels = extractChannels(channelsJson.data).filter(isPlaybackAllowed)
      .sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'es', { sensitivity: 'base', numeric: true }));
    const cdnEvents = eventsJson ? extractCdnEvents(eventsJson.data) : [];
    const personalEvents = ftvJson ? normalizeFutbolenlatv(ftvJson.data) : [];
    // Nunca se incorporan eventos exclusivos de CDN Live TV.
    state.events = mergeAgenda(cdnEvents, personalEvents);
    populateCompetitionFilter();
    renderAll();
    updateClock();
    scheduleEventAutoRefresh();
    if (state.sourceErrors.length) showNotice(`Datos parcialmente actualizados. ${state.sourceErrors.length} archivo(s) no disponibles.`);
    else showNotice('Canales y agenda personalizada actualizados.');
    if (!channelsJson) $('#channels-grid').innerHTML = '<div class="empty-state">Todavía no hay datos de canales. Comprueba que se haya ejecutado el workflow de actualización.</div>';
    if (!ftvJson) $('#events-list').innerHTML = '<div class="empty-state">No se ha podido cargar la agenda personalizada de Futbolenlatv. No se mostrarán eventos de CDN por separado.</div>';
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
$$('.sport-tab').forEach(b=>b.addEventListener('click',()=>{state.sport=b.dataset.sport;$$('.sport-tab').forEach(x=>x.classList.toggle('active',x===b));renderEvents();}));
$$('.date-tab').forEach(b=>b.addEventListener('click',()=>{state.daypart=b.dataset.daypart;$$('.date-tab').forEach(x=>x.classList.toggle('active',x===b));renderEvents();}));
$('#competition-filter').addEventListener('change',()=>{state.competition=$('#competition-filter').value;renderEvents();});
$$('.source-tab').forEach(b=>b.addEventListener('click',()=>{state.source=b.dataset.source;$$('.source-tab').forEach(x=>x.classList.toggle('active',x===b));renderEvents();}));
$('#close-player').addEventListener('click',()=>$('#player-dialog').close());
$('#player-dialog').addEventListener('close',()=>{
  $('#player-content').innerHTML='<p>Selecciona un canal reproducible para abrir su reproductor.</p>';
  // Al cerrar el canal, vuelve a calcular el siguiente refresco pendiente.
  scheduleEventAutoRefresh();
});
$('#channel-letter-filter').hidden=true;
activateCurrentDaypart();
saveFavorites();
setView('sports');
updateClock();
setInterval(updateClock, 1000);
loadData();
