const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const read = (name) => fs.readFileSync(path.join(__dirname, name), 'utf8');

test('the notification assets are loaded by the official frontend', () => {
  const html = read('index.html');
  assert.match(html, /<link rel="stylesheet" href="\.\/notifications\.css">/);
  assert.match(html, /<script src="\.\/notifications\.js"><\/script>/);
  assert.match(html, /class="reference-public-notification"[^>]+aria-label="Notificações"/);
});

test('notifications use real tenant activity data and safe rendering', () => {
  const source = read('notifications.js');
  assert.match(source, /api\('\/activities\?limit=20'\)/);
  assert.match(source, /state\.user\.tenant_id/);
  assert.match(source, /escapeHtml\(activity\.description\)/);
  assert.doesNotMatch(source, /mock|fake|fixture/i);
});

test('unread state is tenant scoped and the gold marker is conditional', () => {
  const source = read('notifications.js');
  const css = read('notifications.css');
  assert.match(source, /mm-notifications-read:/);
  assert.match(source, /dot\.hidden = count === 0/);
  assert.match(source, /saveReadMarker\(newest\)/);
  assert.match(css, /notification-dot\[hidden\]/);
});

test('the panel supports keyboard, outside click and responsive positioning', () => {
  const source = read('notifications.js');
  const css = read('notifications.css');
  assert.match(source, /event\.key === 'Escape'/);
  assert.match(source, /!panel\?\.contains\(event\.target\)/);
  assert.match(source, /aria-expanded/);
  assert.match(source, /aria-live/);
  assert.match(css, /@media \(max-width: 760px\)/);
});

test('signed-out notification access opens authentication without fake data', () => {
  const source = read('notifications.js');
  assert.match(source, /if \(!state\.user\)/);
  assert.match(source, /openAuth\('login'\)/);
  assert.match(source, /Nenhuma notificação por enquanto/);
});
