
const API = { channels: './data/channels.json', events: './data/events_cdn.json', futbolenlatv: './data/events_futbolenlatv.json' };
const FAVORITES_KEY = 'mi-tv-favorites-v1';
const state = { view: 'sports', channels: [], events: [], sport: 'all', source: 'all', daypart: 'featured', competition: 'all', channelLetter: 'all', favorites: loadFavorites(), sourceErrors: [] };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const FIRETV_APP_PACKAGES = {
  movistar: 'com.movistarplus.androidtv',
  dazn: 'com.dazn',
  prime: 'com.amazon.firebat',
  kodi: 'org.xbmc.kodi'
};
const CHANNEL_APP_MAP = {
  'la 1': 'movistar', 'la 2': 'movistar', 'antena 3': 'movistar', 'cuatro': 'movistar',
  'telecinco': 'movistar', 'la sexta': 'movistar', 'movistar plus+': 'movistar',
  'm+ vamos': 'movistar', 'm+ vamos 2': 'movistar', 'm+ vamos 3': 'movistar',
  'primera federacion': 'movistar', 'eurosport 1': 'movistar', 'eurosport 2': 'movistar',
  'real madrid tv': 'movistar', 'teledeporte': 'movistar', 'replay': 'movistar',
  'dazn': 'dazn', 'dazn laliga': 'dazn', 'dazn 1': 'dazn', 'dazn 2': 'dazn',
  'tennis channel': 'prime', 'tennis channel - orange tv': 'prime', 'amazon prime video': 'prime',
  'dazn 3': 'kodi', 'dazn 4': 'kodi', 'dazn f1': 'kodi', 'dazn motogp': 'kodi',
  'dazn baloncesto': 'kodi', 'dazn baloncesto 2': 'kodi', 'dazn baloncesto 3': 'kodi'
};
const CHANNEL_APP_LABELS = { movistar: 'Movistar Plus+', dazn: 'DAZN', prime: 'Amazon Prime Video' };
function isFireTVDevice() {
  const ua = String(navigator.userAgent || '');
  return /\bAFT[A-Z0-9]+\b|Fire TV/i.test(ua);
}
function normalizeAgendaChannelName(value) {
  return String(value || '').toLocaleLowerCase('es')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/\([^)]*\)/g, '').replace(/\s+/g, ' ').trim();
}
function getAgendaChannelApp(value) {
  let normalized = normalizeAgendaChannelName(value);
  const aliases = {
    'movistar plus': 'movistar plus+', 'movistar+': 'movistar plus+', tdp: 'teledeporte',
    'tennis channel orange tv': 'tennis channel - orange tv', 'm+ #vamos': 'm+ vamos',
    '#vamos': 'm+ vamos', '#vamos spain': 'm+ vamos', 'm+ vamos 8 y 50': 'm+ vamos'
  };
  normalized = aliases[normalized] || normalized;
  return CHANNEL_APP_MAP[normalized] || 'kodi';
}
function getAgendaFireTVIntent(channelName) {
  const app = getAgendaChannelApp(channelName);
  if (app === 'kodi' || !FIRETV_APP_PACKAGES[app]) return '';
  return `intent:#Intent;action=android.intent.action.MAIN;category=android.intent.category.LEANBACK_LAUNCHER;package=${FIRETV_APP_PACKAGES[app]};end`;
}
function findCatalogChannel(channelName) {
  const wanted = normalizeAgendaChannelName(channelName);
  if (!wanted) return null;
  return state.channels.find(channel => normalizeAgendaChannelName(channel.name) === wanted) || null;
}
function renderAgendaChannel(channelValue) {
  const name = typeof channelValue === 'string' ? channelValue : (channelValue?.channel_name || channelValue?.name || 'Canal');
  const safeName = esc(name);
  if (isFireTVDevice()) {
    const intent = getAgendaFireTVIntent(name);
    if (intent) {
      const app = getAgendaChannelApp(name);
      return `<a class="channel-chip channel-chip-link" href="${esc(intent)}" title="Abrir ${esc(CHANNEL_APP_LABELS[app] || app)} en Fire TV">${safeName} 🔗</a>`;
    }
    return `<span class="channel-chip">${safeName}</span>`;
  }
  const catalogChannel = findCatalogChannel(name);
  if (catalogChannel) {
    return `<a class="channel-chip channel-chip-link" href="#canales" data-agenda-channel="${esc(keyOf(catalogChannel))}" title="Abrir ${safeName} en Mi TV">${safeName} 🔗</a>`;
  }
  return `<span class="channel-chip">${safeName}</span>`;
}

function loadFavorites() {
  try {
    return new Set(JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]'));
  } catch {
    return new Set();
  }
}
function saveFavorites() {
  localStorage.setItem(FAVORITES_KEY, JSON.stringify([...state.favorites]));
  updateFavoriteCount();
}
function esc(value='') {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function keyOf(channel) {
  return `${String(channel.name || '').trim().toLowerCase()}|${String(channel.code || '').trim().toLowerCase()}`;
}
function countryName(code) {
  const raw=String(code||'').trim();
  if(!raw)return 'País no identificado';
  if(['other','others','unknown','xx'].includes(raw.toLowerCase()))return 'Otros';
  try {
    return new Intl.DisplayNames(['es'], {type:'region'}).of(raw.toUpperCase()) || raw.toUpperCase();
  } catch {
    return raw.toUpperCase();
  }
}
function showNotice(message) {
  const n=$('#notice');
  n.textContent=message;
  n.classList.add('show');
  clearTimeout(showNotice.timer);
  showNotice.timer=setTimeout(()=>n.classList.remove('show'),3200);
}
function setView(view) {
  state.view=view;
  $$('.nav-btn').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
  $$('.view').forEach(v=>v.classList.toggle('active',v.id===`${view}-view`));
  const titles={
    channels:['Canales de televisión','Explora el catálogo disponible y guarda tus canales favoritos.'],
    sports:['Agenda deportiva','Eventos de CDN Live TV y de tu agenda personalizada de Futbolenlatv.'],
    favorites:['Tus favoritos','Tus canales y eventos guardados en este navegador.']
  };
  $('#page-title').textContent=titles[view][0];
  $('#page-subtitle').textContent=titles[view][1];
  $('#competition-filter').style.display=view==='sports'?'':'none';
  $('#channel-letter-filter').hidden=view!=='channels';
  $('#search-input').placeholder=view==='sports'?'Buscar equipo, competición o canal…':view==='favorites'?'Buscar en tus favoritos…':'Buscar canal…';
  renderAll();
}
function extractChannels(payload) {
  return Array.isArray(payload?.channels) ? payload.channels : [];
}
function dateKeyFromValue(value) {
  const raw=String(value||'');
  const iso=raw.match(/(\d{4})-(\d{2})-(\d{2})/);
  if(iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  const local=raw.match(/\b(\d{1,2})\/(\d{1,2})\/(\d{4})\b/);
  if(local) return `${local[3]}-${local[2].padStart(2,'0')}-${local[1].padStart(2,'0')}`;
  if(/^\d{10,13}$/.test(raw)) {
    const d=new Date(Number(raw.length===10?raw+'000':raw));
    if(!Number.isNaN(d.getTime())) {
      const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d);
      const obj=Object.fromEntries(parts.map(p=>[p.type,p.value]));
      return `${obj.year}-${obj.month}-${obj.day}`;
    }
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
    personalFeatured:ev.featured===true,
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
  } catch {
    return null;
  }
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
  const filtered=filteredChannels(list);
  const target=state.view==='favorites'?$('#favorites-grid'):$('#channels-grid');
  target.innerHTML=filtered.length?filtered.map(channelCard).join(''):'<div class="empty-state">No hay canales reproducibles que coincidan con la búsqueda.</div>';
  $('#channels-caption').textContent=`${filtered.length} canales reproducibles mostrados`;
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
  const date=String(ev.date||dateKeyFromValue(ev.start||ev.time)||'');
  const time=eventTimeLabel(ev);
  return `${date||'9999-99-99'}T${time.match(/\d{1,2}:\d{2}/)?.[0]||'99:99'}`;
}
function eventTimeLabel(ev) {
  const raw=String(ev.start||ev.time||'');
  const match=raw.match(/\d{1,2}:\d{2}/);
  if(match)return match[0];
  if(/^\d{10,13}$/.test(raw)) {
    const d=new Date(Number(raw.length===10?raw+'000':raw));
    if(!Number.isNaN(d.getTime()))return new Intl.DateTimeFormat('es-ES',{timeZone:'Europe/Madrid',hour:'2-digit',minute:'2-digit',hour12:false}).format(d);
  }
  return raw;
}
function eventCard(ev) {
  const status=String(ev.status||'').toLowerCase(), channels=Array.isArray(ev.channels)?ev.channels:[];
  const title=eventTitle(ev), when=[eventDateLabel(ev),eventTimeLabel(ev)].filter(Boolean).join(' · ')||'Horario no indicado';
  const chips=channels.map(renderAgendaChannel).join('');
  const id=eventId(ev), saved=state.favorites.has(`e:${id}`);
  const sourceLabel=ev.source==='futbolenlatv'?'Futbolenlatv':ev.source==='both'?'CDN + Futbolenlatv':'CDN Live TV';
  const statusLabel=status==='live'?'EN DIRECTO':status==='finished'?'FINALIZADO':status==='upcoming'?'PRÓXIMO':status==='agenda'?'AGENDA PERSONALIZADA':status.toUpperCase()||'ESTADO NO INDICADO';
  const featured=ev.personalFeatured?'<span class="featured-tag">★ Selección de tu agenda</span>':'';
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
  const obj=Object.fromEntries(parts.map(p=>[p.type,p.value]));
  return `${obj.year}-${obj.month}-${obj.day}`;
}
function populateCompetitionFilter() {
  const select=$('#competition-filter');
  if(!select)return;
  const previous=state.competition;
  const values=[...new Set(state.events.map(ev=>String(ev.tournament||ev.competition||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'es'));
  select.innerHTML='<option value="all">Todas las competiciones</option>'+values.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');
  state.competition=values.includes(previous)?previous:'all';
  select.value=state.competition;
}
function filteredEvents(list) {
  const q=$('#search-input').value.trim().toLocaleLowerCase('es');
  const today=todayKey();
  return list.filter(ev=>{
    const date=ev.date||dateKeyFromValue(ev.start||ev.time)||'';
    const sportOk=state.sport==='all'||sportKey(ev.sport)===state.sport;
    const sourceOk=state.source==='all'||ev.source===state.source||ev.source==='both';
    const comp=String(ev.tournament||ev.competition||'').trim();
    const compOk=state.competition==='all'||comp===state.competition;
    let dayOk=true;
    if(state.daypart==='upcoming')dayOk=Boolean(date&&date>today);
    else if(state.daypart==='featured')dayOk=ev.personalFeatured===true;
    else if(['madrugada','manana','tarde','noche'].includes(state.daypart))dayOk=date===today&&timeSlot(ev)===state.daypart;
    return sportOk&&sourceOk&&compOk&&dayOk&&(!q||eventSearchText(ev).includes(q));
  });
}

/*
 * Cuenta los favoritos que realmente pueden verse en la pestaña Favoritos.
 * No elimina ni modifica las claves guardadas en localStorage.
 */
function updateFavoriteCount() {
  const counter=$('#fav-count');
  if(!counter)return;

  const visibleChannels=state.channels.filter(ch=>
    state.favorites.has(`c:${keyOf(ch)}`) &&
    isPlaybackAllowed(ch) &&
    (!$('#search-input').value.trim() ||
      String(ch.name||'').toLocaleLowerCase('es').includes($('#search-input').value.trim().toLocaleLowerCase('es')))
  ).length;

  const favoriteEvents=state.events.filter(ev=>
    state.favorites.has(`e:${eventId(ev)}`)
  );
  const visibleEvents=filteredEvents(favoriteEvents).length;

  counter.textContent=visibleChannels+visibleEvents;
}

function renderEvents() {
  const list=state.view==='favorites'?state.events.filter(ev=>state.favorites.has(`e:${eventId(ev)}`)):state.events;
  const filtered=filteredEvents(list).sort((a,b)=>eventSortKey(a).localeCompare(eventSortKey(b)));
  const target=state.view==='favorites'?$('#favorite-events'):$('#events-list');
  target.innerHTML=filtered.length?filtered.map(eventCard).join(''):'<div class="empty-state">No hay eventos para mostrar con estos filtros.</div>';
  $$('[data-fav-event]').forEach(btn=>btn.addEventListener('click',()=>toggleFavorite(`e:${btn.dataset.favEvent}`)));
  $$('[data-agenda-channel]').forEach(link=>link.addEventListener('click',event=>{
    event.preventDefault();
    const channel=state.channels.find(item=>keyOf(item)===link.dataset.agendaChannel);
    if(channel)openPlayer(channel);
  }));
  updateFavoriteCount();
}
function bindChannelActions() {
  $$('[data-fav-channel]').forEach(btn=>btn.addEventListener('click',event=>{
    event.stopPropagation();
    toggleFavorite(`c:${btn.dataset.favChannel}`);
  }));
  $$('[data-channel-card]').forEach(card=>{
    const open=()=>{const ch=state.channels.find(x=>keyOf(x)===card.dataset.channelCard);if(ch)openPlayer(ch);};
    card.addEventListener('click',event=>{if(!event.target.closest('[data-fav-channel]'))open();});
    card.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();open();}});
  });
}
function toggleFavorite(key) {
  if(state.favorites.has(key))state.favorites.delete(key);
  else state.favorites.add(key);
  saveFavorites();
  renderAll();
}
function openPlayer(channel) {
  const url=safePlayerUrl(channel);
  if(!url){showNotice('Este canal no tiene una página oficial de reproducción disponible.');return;}
  $('#player-title').textContent=channel.name;
  $('#player-content').innerHTML=`<iframe src="${esc(url)}" title="${esc(channel.name)}" allow="autoplay; encrypted-media; fullscreen; picture-in-picture" allowfullscreen></iframe>`;
  $('#player-dialog').showModal();
}
function renderAll() {
  updateFavoriteCount();
  $('#channel-total').textContent=state.channels.filter(isPlaybackAllowed).length||'0';
  $('#event-total').textContent=state.events.length||'0';
  if(state.view==='channels')renderChannels();
  if(state.view==='sports')renderEvents();
  if(state.view==='favorites'){
    renderChannels();
    renderEvents();
  }
}
function eventTeams(ev) {
  if(ev.homeTeam&&ev.awayTeam)return [ev.homeTeam,ev.awayTeam];
  if(!['football','basketball'].includes(sportKey(ev.sport)))return null;
  const parts=String(ev.eventTitle||'').split(/\s+-\s+/);
  return parts.length===2&&parts.every(Boolean)?parts:null;
}
function mergeAgenda(cdnEvents, personalEvents) {
  // No se eliminan coincidencias aproximadas: solo se fusionan duplicados exactos
  // con fecha, hora y nombres de los dos equipos idénticos.
  const merged=[...cdnEvents,...personalEvents];
  const index=new Map();
  const out=[];
  for(const ev of merged) {
    const date=ev.date||dateKeyFromValue(ev.start||ev.time)||'';
    const time=eventTimeLabel(ev).match(/\d{1,2}:\d{2}/)?.[0]||'';
    const teams=eventTeams(ev);
    if(!teams||!date||!time){out.push(ev);continue;}
    const norm=s=>String(s).toLocaleLowerCase('es').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,' ').trim();
    const key=`${sportKey(ev.sport)}|${date}|${time}|${teams.map(norm).sort().join('|')}`;
    if(!index.has(key)){index.set(key,out.length);out.push(ev);continue;}
    const existing=out[index.get(key)];
    const old=Array.isArray(existing.channels)?existing.channels:[];
    const fresh=Array.isArray(ev.channels)?ev.channels:[];
    const channelKey=c=>String(typeof c==='string'?c:(c.channel_name||c.name||'')).toLowerCase();
    existing.channels=[...old,...fresh.filter(c=>!old.some(o=>channelKey(o)===channelKey(c)))];
    existing.source='both';
    existing.featured=existing.featured||ev.featured;
    existing.personalFeatured=existing.personalFeatured||ev.personalFeatured===true;
  }
  return out;
}
async function fetchStaticJson(path) {
  const separator=path.includes('?')?'&':'?';
  const response=await fetch(`${path}${separator}v=${Date.now()}`,{cache:'no-store'});
  const json=await response.json();
  if(!response.ok||json.ok===false)throw new Error(json.error||`HTTP ${response.status}`);
  return json;
}
async function loadData() {
  const button=$('#refresh-btn');
  button.disabled=true;
  state.sourceErrors=[];
  try {
    const paths=[API.channels,API.events,API.futbolenlatv];
    const labels=['CDN Live TV (canales)','CDN Live TV (eventos)','Futbolenlatv'];
    const parsed=await Promise.all(paths.map(async(path,i)=>{
      try {
        return await fetchStaticJson(path);
      } catch(err) {
        state.sourceErrors.push(`${labels[i]}: ${err.message}`);
        return null;
      }
    }));
    const [channelsJson,eventsJson,ftvJson]=parsed;
    if(channelsJson)state.channels=extractChannels(channelsJson.data).filter(isPlaybackAllowed).sort((a,b)=>String(a.name||'').localeCompare(String(b.name||''),'es',{sensitivity:'base',numeric:true}));
    const cdnEvents=eventsJson?extractCdnEvents(eventsJson.data):[];
    const personalEvents=ftvJson?normalizeFutbolenlatv(ftvJson.data):[];
    state.events=mergeAgenda(cdnEvents,personalEvents);
    populateCompetitionFilter();
    renderAll();
    if(state.sourceErrors.length) showNotice(`Datos parcialmente actualizados. ${state.sourceErrors.length} archivo(s) no disponibles.`);
    else showNotice('Canales y agendas actualizados.');
    if(!channelsJson)$('#channels-grid').innerHTML='<div class="empty-state">Todavía no hay datos de canales. Comprueba que se haya ejecutado el workflow de actualización.</div>';
    if(!eventsJson&&!ftvJson)$('#events-list').innerHTML='<div class="empty-state">Todavía no hay datos de agenda disponibles.</div>';
  } catch(err) {
    showNotice(err.message||'No se pudieron cargar los datos.');
  } finally {
    button.disabled=false;
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
$$('.sport-tab').forEach(b=>b.addEventListener('click',()=>{
  state.sport=b.dataset.sport;
  $$('.sport-tab').forEach(x=>x.classList.toggle('active',x===b));
  renderEvents();
}));
$$('.date-tab').forEach(b=>b.addEventListener('click',()=>{
  state.daypart=b.dataset.daypart;
  $$('.date-tab').forEach(x=>x.classList.toggle('active',x===b));
  renderEvents();
}));
$('#competition-filter').addEventListener('change',()=>{
  state.competition=$('#competition-filter').value;
  renderEvents();
});
$$('.source-tab').forEach(b=>b.addEventListener('click',()=>{
  state.source=b.dataset.source;
  $$('.source-tab').forEach(x=>x.classList.toggle('active',x===b));
  renderEvents();
}));
$('#close-player').addEventListener('click',()=>$('#player-dialog').close());
$('#player-dialog').addEventListener('close',()=>$('#player-content').innerHTML='<p>Selecciona un canal reproducible para abrir su reproductor.</p>');
$('#channel-letter-filter').hidden=true;
saveFavorites();
setView('sports');
loadData();
