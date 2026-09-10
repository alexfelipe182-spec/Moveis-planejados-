const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const read = (name) => fs.readFileSync(path.join(__dirname, name), 'utf8');

test('authenticated dashboard adopts the public reference shell', () => {
  const source = read('authenticated-reference.js');

  assert.match(source, /reference-public-dashboard/);
  assert.match(source, /reference-authenticated-dashboard/);
  assert.match(source, /reference-public-sidebar/);
  assert.match(source, /reference-public-topbar/);
  assert.match(source, /mm:auth-changed/);
});

test('authenticated reference keeps mobile navigation usable', () => {
  const css = read('authenticated-reference.css');

  assert.match(css, /@media\(max-width:760px\)/);
  assert.match(css, /position:fixed!important/);
  assert.match(css, /#admin-nav\.reference-public-nav/);
  assert.match(css, /display:flex!important/);
  assert.match(css, /env\(safe-area-inset-bottom\)/);
});
