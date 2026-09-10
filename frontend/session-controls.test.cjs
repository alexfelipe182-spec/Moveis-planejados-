const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const frontendDir = __dirname;
const sessionControls = fs.readFileSync(path.join(frontendDir, 'session-controls.js'), 'utf8');
const indexHtml = fs.readFileSync(path.join(frontendDir, 'index.html'), 'utf8');
const notifications = fs.readFileSync(path.join(frontendDir, 'notifications.js'), 'utf8');
const accountMenu = fs.readFileSync(path.join(frontendDir, 'account-menu-v2.js'), 'utf8');

test('logout hardening owns every visible logout and relogin entry point', () => {
  for (const selector of [
    '#logout',
    '#mm-menu-logout',
    '#settings-logout',
    '[data-account-action="logout"]',
    '#mm-menu-relogin',
    '#settings-relogin',
    '#direct-relogin',
    '[data-account-action="relogin"]',
  ]) {
    assert.match(sessionControls, new RegExp(selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
  assert.match(sessionControls, /abortRefreshRequests\(\)/);
  assert.match(sessionControls, /window\.location\.replace\('\/'\)/);
  assert.match(sessionControls, /sessionStorage\.setItem\(SIGNED_OUT_KEY, '1'\)/);
});

test('fresh login explicitly clears the signed-out guard', () => {
  assert.match(sessionControls, /event\.target\?\.id === 'login-form'/);
  assert.match(sessionControls, /sessionStorage\.removeItem\(SIGNED_OUT_KEY\)/);
});

test('dynamic action buttons are normalized without touching submit buttons', () => {
  assert.match(sessionControls, /button\[onclick\]:not\(\[type\]\)/);
  assert.match(sessionControls, /button\.nav:not\(\[type\]\)/);
  assert.match(sessionControls, /button\.dashboard-kpi:not\(\[type\]\)/);
  assert.match(sessionControls, /button\.small-btn:not\(\[type\]\)/);
  assert.match(sessionControls, /setAttribute\('type', 'button'\)/);
  assert.doesNotMatch(sessionControls, /button\[type="submit"\]/);
});

test('literal public, notification and account-menu buttons declare a type', () => {
  const sources = [indexHtml, notifications, accountMenu];
  for (const source of sources) {
    const literalButtons = [...source.matchAll(/<button\b[^>]*>/g)].map((match) => match[0]);
    const missingType = literalButtons.filter((button) => !/\btype=/.test(button));
    assert.deepEqual(missingType, []);
  }
});
