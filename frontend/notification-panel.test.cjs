const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');

const source = fs.readFileSync(path.join(__dirname, 'notification-panel.js'), 'utf8');
const quoteDecisions = fs.readFileSync(path.join(__dirname, 'quote-decisions.js'), 'utf8');

test('notification panel starts without fake notifications', () => {
  assert.match(source, /normalizeNotifications\(window\.MM_NOTIFICATIONS\)/);
  assert.match(source, /Nenhuma notificação/);
  assert.match(source, /legacyDot\.hidden = unreadCount === 0/);
});

test('notification panel exposes accessible expanded state', () => {
  assert.match(source, /aria-expanded/);
  assert.match(source, /aria-controls/);
  assert.match(source, /aria-haspopup/);
});

test('notification panel supports read state and dismissal', () => {
  assert.match(source, /Marcar como lida/);
  assert.match(source, /event\.key === 'Escape'/);
  assert.match(source, /document\.addEventListener\('click'/);
});

test('notification panel is loaded by the existing frontend bundle chain', () => {
  assert.match(quoteDecisions, /notification-panel\.js\?v=20260909-1/);
  assert.match(quoteDecisions, /data-mm-notification-panel/);
});
