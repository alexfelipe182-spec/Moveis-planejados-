const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

test('smart quote values use forced dark text in the light interface', () => {
  const accountMenu = fs.readFileSync(path.join(__dirname, 'account-menu-v2.js'), 'utf8');
  const loader = fs.readFileSync(path.join(__dirname, 'saas-public.js'), 'utf8');

  assert.match(accountMenu, /#admin-app \.smart-quote-grid strong\{[\s\S]*color:#111111!important;[\s\S]*-webkit-text-fill-color:#111111!important;/);
  assert.match(accountMenu, /#admin-app \.smart-result-card strong,[\s\S]*#admin-app \.smart-quote-grid strong/);
  assert.match(accountMenu, /body\.dark #admin-app \.smart-quote-grid strong[\s\S]*-webkit-text-fill-color:#f8fafc!important;/);
  assert.match(loader, /account-menu-v2\.js\?v=20260908-contrast-1/);
});
