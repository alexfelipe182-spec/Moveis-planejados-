const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const read = (name) => fs.readFileSync(path.join(__dirname, name), 'utf8');

test('quote decisions only owns quote decision behavior', () => {
  const source = read('quote-decisions.js');
  assert.match(source, /decideQuote/);
  assert.match(source, /setQuoteCommercialStatus/);
  assert.doesNotMatch(source, /account-settings-nav|direct-relogin|injectFixedControls|mm-direct-relogin/);
});

test('account menu owns account controls and sidebar layout', () => {
  const source = read('account-menu-v2.js');
  assert.match(source, /mm-menu-settings/);
  assert.match(source, /mm-menu-relogin/);
  assert.match(source, /mm-menu-logout/);
  assert.match(source, /#admin-app #admin-nav\{flex:1 1 auto/);
});

test('dashboard search is functional and uses the authenticated API client', () => {
  const source = read('dashboard-search.js');
  assert.match(source, /searchDashboard/);
  assert.match(source, /api\(`\$\{resource\.endpoint\}\?limit=100`\)/);
  assert.match(source, /data-dashboard-search-resource/);
  assert.doesNotMatch(source, /\bfetch\s*\(/);
});

test('saas loader includes account menu and dashboard search with cache versions', () => {
  const source = read('saas-public.js');
  assert.match(source, /account-menu-v2\.js\?v=/);
  assert.match(source, /dashboard-search\.js\?v=/);
});
