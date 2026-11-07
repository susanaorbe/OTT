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
  state: { channels: [], competition: 'all', source: 'cdn', favorites: new Set(), hiddenChannels: new Set(), hiddenSelection: new Set(), channelMode: 'all', channelLetter: 'all' },
  URL,
  $: () => ({ value: '' }),
  keyOf: channel => `${String(channel.name || '').trim().toLowerCase()}|${String(channel.code || '').trim().toLowerCase()}`, 
  esc: value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])),
  channelValueName: channel => typeof channel === 'string' ? channel : (channel?.channel_name || channel?.name || ''),
  findCatalogChannel: () => null,
  eventChannelsForCurrentSource: ev => Array.isArray(ev?.channels) ? ev.channels : [],
  eventSearchText: ev => `${ev.eventTitle || ev.event || ''} ${ev.tournament || ''} ${(ev.channels || []).map(c => typeof c === 'string' ? c : c.channel_name || '').join(' ')}`.toLowerCase(),
  dateKeyFromValue: value => String(value || '').slice(0, 10),
};
vm.createContext(context);
vm.runInContext([
  section('safePlayerUrl', 'channelCard'),
  section('renderAgendaChannel', 'loadFavorites'),
  section('dateKeyFromValue', 'extractCdnEvents'),
  section('extractCdnEvents', 'isPlaybackAllowed'),
  section('channelCard', 'filteredChannels'),
  section('filteredChannels', 'renderChannelModeControls'),
  section('eventTitle', 'eventDateLabel'),
  section('filteredEvents', 'renderEvents'),
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

test('competition dropdown is the only agenda filter', () => {
  const events = [
    { tournament: 'League A', event: 'Match A', channels: [] },
    { tournament: 'League B', event: 'Match B', channels: [] },
    { tournament: 'League A', event: 'Match C', channels: [] }
  ];
  context.state.competition = 'all';
  assert.equal(context.filteredEvents(events).length, 3);
  context.state.competition = 'League A';
  assert.equal(context.filteredEvents(events).length, 2);
  context.state.competition = 'League B';
  assert.equal(context.filteredEvents(events).length, 1);
});
