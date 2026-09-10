const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const root = path.resolve(__dirname, '..');
const readRoot = (name) => fs.readFileSync(path.join(root, name), 'utf8');

test('frontend assets resolve from the root on nested SPA routes', () => {
  assert.match(readRoot('frontend/index.html'), /<base href="\/">/);
});

test('production and development servers have distinct entry points', () => {
  assert.match(readRoot('frontend_server.py'), /Starlette/);
  assert.match(readRoot('frontend_server.py'), /app = Starlette/);
  assert.match(readRoot('scripts/serve_frontend.py'), /Development\/test server only/);
  assert.match(readRoot('requirements-frontend.txt'), /uvicorn\[standard\]/);
});

test('the Blueprint does not duplicate the existing frontend service', () => {
  const blueprint = readRoot('render.yaml');
  assert.doesNotMatch(blueprint, /name:\s*multi-marcenarias\s*$/m);
  assert.match(blueprint, /frontend oficial multi-marcenarias é um serviço existente/);
});
