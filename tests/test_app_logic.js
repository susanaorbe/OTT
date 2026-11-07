const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '..', 'docs', 'app.js'), 'utf8');
function section(startName, endName) {
  const start = source.indexOf(`function ${startName}(`);
  const end = source.indexOf(`\nfunction ${endName}(`, start);
  assert.ok(start >= 0 && end > start, `${startName} section exists`);
  return source.slice(start, end);
}

const context = {
  state: { channels: [], competition: 'all', source: 'all', sport: 'all', daypart: 'all', favorites: new Set(), hiddenChannels: new Set(), hiddenSelection: new Set(), channelMode: 'all', channelLetter: 'all', events: [] },
  URL,
  $: () => ({ value: '' }),
  keyOf: channel => `${String(channel.name || '').trim().toLowerCase()}|${String(channel.code || '').trim().toLowerCase()}`, 
  esc: value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])),
  channelValueName: channel => typeof channel === 'string' ? channel : (channel?.channel_name || channel?.name || ''),
  findCatalogChannel: () => null,
  eventChannelsForCurrentSource: ev => Array.isArray(ev?.channels) ? ev.channels : [],
  eventSearchText: ev => `${ev.eventTitle || ev.event || ''} ${ev.tournament || ''} ${(ev.channels || []).map(c => typeof c === 'string' ? c : c.channel_name || '').join(' ')}`.toLowerCase(),
  dateKeyFromValue: value => String(value || '').slice(0, 10),
  todayKey: () => '2026-11-07',
  timeSlot: () => 'tarde',
  eventTimeLabel: ev => String(ev.start || ev.time || ''),
  sportKey: value => String(value || '').toLowerCase(),
};
vm.createContext(context);
vm.runInContext([
  section('safePlayerUrl', 'channelCard'),
  section('normalizeAgendaChannelName', 'normalizeChannelMatchName'),
  section('normalizeChannelMatchName', 'findCatalogChannel'),
  section('findCatalogChannel', 'channelValueName'),
  section('renderAgendaChannel', 'loadFavorites'),
  section('dateKeyFromValue', 'extractCdnEvents'),
  section('extractCdnEvents', 'isPlaybackAllowed'),
  section('channelCard', 'filteredChannels'),
  section('filteredChannels', 'renderChannelModeControls'),
  section('eventTitle', 'eventDateLabel'),
  section('filteredEvents', 'renderEvents'),
  section('eventDateLabel', 'eventCard'),
  section('eventCard', 'eventSearchText'),
  section('eventId', 'showNotice'),
  section('madridLocalTimestamp', 'scheduleEventAutoRefresh'),
  section('isPadelEvent', 'eventMergeKey'),
  section('eventMergeKey', 'combineEventSources'),
  section('combineEventSources', 'sportKey'),
].join('\n'), context);

test('keeps all CDN event categories, including events without associated channels', () => {
  const payload = {
    'cdn-live-tv': {
      Soccer: [{ gameID: '1', event: 'Match A', tournament: 'League A', start: '2026-11-07 10:00', channels: [] }],
      Badminton: [{ gameID: '2', event: 'Tournament B', tournament: 'BWF', start: '2026-11-08 11:00', channels: [] }],
      Motorsport: [{ gameID: '3', event: 'Race C', tournament: 'Motor Series', start: '2026-11-09 12:00', channels: [{ channel_name: 'Channel C' }] }]
    }
  };
  const events = context.extractCdnEvents(payload);
  assert.equal(events.length, 3);
  assert.deepEqual(Array.from(events, e => e.gameID), ['1', '2', '3']);
  assert.equal(events[1].sport, 'Badminton');
  assert.equal(events[0].channels.length, 0);
});

test('channel cards omit country and keep offline channels in the visible catalogue', () => {
  const channel = { name: 'Example Channel', code: 'GB', status: 'offline', playback_allowed: false };
  const html = context.channelCard(channel);
  assert.match(html, /Example Channel/);
  assert.doesNotMatch(html, /channel-country|GB/);
  assert.equal(context.filteredChannels([channel]).length, 1);
});

test('renders direct CDN event channel URLs as player links', () => {
  const url = 'https://cdnlivetv.tv/api/v1/channels/player/?name=DAZN%20F1&code=&user=cdnlivetv&plan=free';
  const html = context.renderAgendaChannel({ channel_name: 'DAZN F1', url });
  assert.match(html, /data-agenda-player-url=/);
  assert.match(html, /DAZN F1/);
});

test('rejects non-official player URLs', () => {
  assert.equal(context.safePlayerUrl({ url: 'https://example.com/player' }), null);
  assert.equal(context.safePlayerUrl({ url: 'http://cdnlivetv.tv/api/v1/channels/player/?name=A&code=&user=cdnlivetv&plan=free' }), null);
});

test('restores competition, sport, source and date filters without discarding CDN events', () => {
  const events = [
    { tournament: 'League A', event: 'Match A', channels: [] },
    { tournament: 'League B', event: 'Match B', channels: [] },
    { tournament: 'League A', event: 'Match C', channels: [] }
  ];
  context.state.competition = 'all';
  context.state.sport = 'all'; context.state.source = 'all'; context.state.daypart = 'all';
  assert.equal(context.filteredEvents(events).length, 3);
  context.state.competition = 'League A';
  assert.equal(context.filteredEvents(events).length, 2);
  context.state.competition = 'League B';
  assert.equal(context.filteredEvents(events).length, 1);
  context.state.competition = 'all';
  context.state.sport = 'soccer';
  assert.equal(context.filteredEvents(events.map(e => ({ ...e, sport: 'soccer' }))).length, 3);
  context.state.sport = 'all';
  context.state.source = 'cdn';
  assert.equal(context.filteredEvents(events.map(e => ({ ...e, source: 'cdn' }))).length, 3);
  context.state.source = 'futbolenlatv';
  assert.equal(context.filteredEvents(events.map(e => ({ ...e, source: 'futbolenlatv' }))).length, 3);
});


test('resolves Futbolenlatv channel aliases only to exact unique CDN targets', () => {
  context.state.channels = [
    { name: 'Tennis Channel HD US', playback_allowed: true, player_url: 'https://cdnlivetv.tv/api/v1/channels/player/?name=Tennis%20Channel%20HD%20US&code=&user=cdnlivetv&plan=free' },
    { name: 'Sport TV 4 HD PT', playback_allowed: true, player_url: 'https://cdnlivetv.tv/api/v1/channels/player/?name=Sport%20TV%204%20HD%20PT&code=&user=cdnlivetv&plan=free' },
    { name: 'LaLiga TV FHD UK', playback_allowed: true, player_url: 'https://cdnlivetv.tv/api/v1/channels/player/?name=LaLiga%20TV%20FHD%20UK&code=&user=cdnlivetv&plan=free' },
    { name: 'DAZN La Liga HD' },
    { name: 'Teledeporte FHD' },
    { name: 'Real Madrid TV. ES' },
    { name: 'Movistar Deportes 1 FHD' }
  ];
  assert.equal(context.findCatalogChannel('Tennis Channel')?.name, 'Tennis Channel HD US');
  assert.equal(context.findCatalogChannel('DAZN MotoGP')?.name, 'Sport TV 4 HD PT');
  assert.equal(context.findCatalogChannel('M* LALIGA')?.name, 'LaLiga TV FHD UK');
  assert.equal(context.findCatalogChannel('M+ LALIGA')?.name, 'LaLiga TV FHD UK');
  assert.equal(context.findCatalogChannel('DAZN LaLiga')?.name, 'DAZN La Liga HD');
  assert.equal(context.findCatalogChannel('Teledeporte')?.name, 'Teledeporte FHD');
  assert.equal(context.findCatalogChannel('Real Madrid TV')?.name, 'Real Madrid TV. ES');
  assert.equal(context.findCatalogChannel('M+ Deportes')?.name, 'Movistar Deportes 1 FHD');
  assert.equal(context.findCatalogChannel('M+ Deportes 5'), null);
  context.state.channels.push({ name: 'Tennis Channel HD US' });
  assert.equal(context.findCatalogChannel('Tennis Channel'), null);
});

test('excludes padel events from both sources before merging', () => {
  assert.equal(context.isPadelEvent({ sport: 'Pádel', tournament: 'Campeonato del Mundo' }), true);
  assert.equal(context.isPadelEvent({ sport: 'Tenis', tournament: 'ATP Finals' }), false);
  const events = context.combineEventSources(
    [
      { gameID: 'p1', sport: 'Padel', date: '2026-11-07', start: '12:00', eventTitle: 'Final' },
      { gameID: 'c1', sport: 'Fútbol', date: '2026-11-07', start: '12:00', eventTitle: 'Partido' }
    ],
    [
      { id: 'p2', sport: 'Pádel', date: '2026-11-07', time: '16:00', eventTitle: 'Final' },
      { id: 'f1', sport: 'Tenis', date: '2026-11-07', time: '16:00', eventTitle: 'Final tenis' }
    ]
  );
  assert.equal(events.some(event => /padel/i.test(event.sport)), false);
  assert.equal(events.length, 2);
});


test('marks the latest started event separately for each selected source', () => {
  context.state.events = [
    { id: 'cdn-old', source: 'cdn', date: '2026-11-07', start: '10:00', eventTitle: 'CDN antiguo' },
    { id: 'cdn-a', source: 'cdn', date: '2026-11-07', start: '12:00', eventTitle: 'CDN A' },
    { id: 'cdn-b', source: 'cdn', date: '2026-11-07', start: '12:00', eventTitle: 'CDN B' },
    { id: 'ftv-old', source: 'futbolenlatv', date: '2026-11-07', start: '09:00', eventTitle: 'FTV antiguo' },
    { id: 'ftv-a', source: 'futbolenlatv', date: '2026-11-07', start: '11:00', eventTitle: 'FTV A' },
    { id: 'ftv-b', source: 'futbolenlatv', date: '2026-11-07', start: '11:00', eventTitle: 'FTV B' }
  ];
  const now = context.madridLocalTimestamp('2026-11-07', '13:00');
  context.state.source = 'all';
  assert.deepEqual(Array.from(context.latestStartedEventIds(now)).sort(), ['cdn-a', 'cdn-b', 'ftv-a', 'ftv-b']);
  context.state.source = 'futbolenlatv';
  assert.deepEqual(Array.from(context.latestStartedEventIds(now)).sort(), ['ftv-a', 'ftv-b']);
  context.state.source = 'cdn';
  assert.deepEqual(Array.from(context.latestStartedEventIds(now)).sort(), ['cdn-a', 'cdn-b']);
});

test('shows the DESTACADO label on featured events', () => {
  const html = context.eventCard({
    id: 'featured-1', date: '2026-11-07', start: '12:00', sport: 'Fútbol', icon: '⚽',
    tournament: 'Liga', eventTitle: 'Partido destacado', featured: true, source: 'futbolenlatv', channels: []
  });
  assert.match(html, /DESTACADO/);
});


test('keeps only Agenda and Canales in navigation and removes the Padel sport tab', () => {
  const html = fs.readFileSync(path.join(__dirname, '..', 'docs', 'index.html'), 'utf8');
  assert.match(html, /data-view="sports"/);
  assert.match(html, /data-view="channels"/);
  assert.doesNotMatch(html, /data-view="favorites"/);
  assert.doesNotMatch(html, /data-sport="padel"/);
  const sourceOrder = ['Futbolenlatv', 'CDN Live TV', 'Todas las fuentes'];
  const sourcePositions = sourceOrder.map(label => html.indexOf(`>${label}</button>`));
  assert.ok(sourcePositions.every(position => position >= 0));
  assert.deepEqual([...sourcePositions].sort((a, b) => a - b), sourcePositions);
});
