const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const calls = [];
const responses = [
  { status: 401, body: { detail: 'Token expirado' } },
  { status: 200, body: { csrf_token: 'csrf-new' } },
  { status: 201, body: { id: 42 } },
];

const context = {
  URLSearchParams,
  document: { cookie: '', querySelector: () => null, querySelectorAll: () => [] },
  location: { hostname: 'site.example' },
  window: { API_BASE_URL: 'https://api.example/api/v1' },
  fetch: async (url, options) => {
    calls.push({ url, options: { ...options, headers: { ...options.headers } } });
    const response = responses.shift();
    return { status: response.status, ok: response.status < 400, json: async () => response.body };
  },
};

vm.createContext(context);
const source = fs.readFileSync('frontend/app.js', 'utf8').split('function openAuth')[0];
vm.runInContext(`${source}\nglobalThis.testApi = api; globalThis.testState = state;`, context);

(async () => {
  context.testState.csrfToken = 'csrf-old';
  const result = await context.testApi('/customers', { method: 'POST', body: { name: 'Cliente' } });

  assert.deepEqual(result, { id: 42 });
  assert.equal(calls.length, 3);
  assert.equal(calls[0].url, 'https://api.example/api/v1/customers');
  assert.equal(calls[0].options.headers['X-CSRF-Token'], 'csrf-old');
  assert.equal(calls[1].url, 'https://api.example/api/v1/auth/refresh');
  assert.equal(calls[1].options.headers['X-CSRF-Token'], 'csrf-old');
  assert.equal(calls[2].url, 'https://api.example/api/v1/customers');
  assert.equal(calls[2].options.headers['X-CSRF-Token'], 'csrf-new');
  assert.equal(context.testState.csrfToken, 'csrf-new');
  console.log('frontend session refresh: ok');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
