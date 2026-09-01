const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8').split('function openAuth')[0];
const response = (status, body = {}) => ({ status, ok: status < 400, json: async () => body });
function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

function createClient(handler) {
  const calls = [];
  const context = {
    URLSearchParams,
    document: { cookie: '', querySelector: () => null, querySelectorAll: () => [] },
    location: { hostname: 'site.example' },
    window: { API_BASE_URL: 'https://api.example/api/v1' },
    fetch: async (url, options) => {
      calls.push({ url, options: { ...options, headers: { ...options.headers } } });
      return handler(url, options, calls.length);
    },
  };
  vm.createContext(context);
  vm.runInContext(`${source}\nglobalThis.testApi = api; globalThis.testState = state;`, context);
  context.testState.csrfToken = 'csrf-old';
  return { api: context.testApi, state: context.testState, calls };
}

test('401 refreshes once and replays the body with the rotated CSRF token', async () => {
  const replies = [response(401, { detail: 'Token expirado' }), response(200, { csrf_token: 'csrf-new' }), response(201, { id: 42 })];
  const { api, state, calls } = createClient(() => replies.shift());
  const body = { name: 'Cliente' };
  const result = await api('/customers', { method: 'POST', body });
  assert.deepEqual(result, { id: 42 });
  assert.equal(calls.length, 3);
  assert.equal(calls[1].url, 'https://api.example/api/v1/auth/refresh');
  assert.equal(calls[1].options.headers['X-CSRF-Token'], 'csrf-old');
  assert.equal(calls[2].options.headers['X-CSRF-Token'], 'csrf-new');
  assert.equal(calls[2].options.body, JSON.stringify(body));
  assert.deepEqual(body, { name: 'Cliente' });
  assert.equal(state.csrfToken, 'csrf-new');
});

test('concurrent 401 responses share the same refresh request', async () => {
  const bothStarted = deferred();
  const refreshing = deferred();
  const releaseRefresh = deferred();
  let originalRequests = 0;
  let refreshes = 0;
  const { api } = createClient(async (url, options) => {
    if (url.endsWith('/auth/refresh')) {
      refreshes += 1;
      refreshing.resolve();
      await releaseRefresh.promise;
      return response(200, { csrf_token: 'csrf-new' });
    }
    if (options.headers['X-CSRF-Token'] === 'csrf-old') {
      originalRequests += 1;
      if (originalRequests === 2) bothStarted.resolve();
      await bothStarted.promise;
      return response(401);
    }
    return response(200);
  });
  const first = api('/customers', { method: 'POST', body: { name: 'Cliente' } });
  const second = api('/quotes', { method: 'POST', body: { description: 'Orçamento' } });
  await refreshing.promise;
  releaseRefresh.resolve();
  await Promise.all([first, second]);
  assert.equal(refreshes, 1);
});

test('a delayed 401 reuses an already renewed session instead of refreshing again', async () => {
  const delayed = deferred();
  const issued = deferred();
  let quoteCalls = 0;
  let refreshes = 0;
  const { api } = createClient(async (url, options) => {
    if (url.endsWith('/auth/refresh')) {
      refreshes += 1;
      return response(200, { csrf_token: 'csrf-new' });
    }
    if (url.endsWith('/quotes') && ++quoteCalls === 1) {
      issued.resolve();
      return delayed.promise;
    }
    return response(options.headers['X-CSRF-Token'] === 'csrf-old' ? 401 : 200);
  });
  const late = api('/quotes', { method: 'POST', body: { description: 'Orçamento' } });
  await issued.promise;
  await api('/customers', { method: 'POST', body: { name: 'Cliente' } });
  delayed.resolve(response(401));
  await late;
  assert.equal(refreshes, 1);
});

test('a refresh service failure is not masked as invalid authentication', async () => {
  const { api, calls } = createClient((url) => url.endsWith('/auth/refresh')
    ? response(503, { detail: 'Serviço temporariamente indisponível' })
    : response(401, { detail: 'Token expirado' }));
  await assert.rejects(api('/me'), /Serviço temporariamente indisponível/);
  assert.equal(calls.length, 2);
});

test('failed login does not try to refresh an unrelated session', async () => {
  const { api, calls } = createClient(() => response(401, { detail: 'E-mail ou senha inválidos' }));
  await assert.rejects(api('/auth/login', { method: 'POST', body: new URLSearchParams({ username: 'test@example.com', password: 'invalid' }) }), /E-mail ou senha inválidos/);
  assert.equal(calls.length, 1);
});

test('login bearer keeps the cross-site session working when cookies are blocked', async () => {
  const { api, calls } = createClient((url) => url.endsWith('/auth/login')
    ? response(200, { access_token: 'access-for-this-session', csrf_token: 'csrf-new' })
    : response(200, { id: 7, is_admin: true }));

  await api('/auth/login', {
    method: 'POST',
    body: new URLSearchParams({ username: 'admin@example.com', password: 'test-only' }),
  });
  await api('/me');

  assert.equal(calls[1].options.headers.Authorization, 'Bearer access-for-this-session');
});

test('a repeated 401 after renewal does not create a refresh loop', async () => {
  const { api, calls } = createClient((url) => url.endsWith('/auth/refresh')
    ? response(200, { csrf_token: 'csrf-new' })
    : response(401, { detail: 'Acesso inválido' }));
  await assert.rejects(api('/me'), /Acesso inválido/);
  assert.equal(calls.length, 3);
});

test('a failed response cannot overwrite the CSRF token', async () => {
  const { api, state } = createClient(() => response(403, { detail: 'Acesso negado', csrf_token: 'not-a-session' }));
  await assert.rejects(api('/customers'), /Acesso negado/);
  assert.equal(state.csrfToken, 'csrf-old');
});

test('a failed refresh releases the shared promise for a later attempt', async () => {
  let refreshes = 0;
  let renewed = false;
  const { api } = createClient((url) => {
    if (url.endsWith('/auth/refresh')) {
      if (++refreshes === 1) return response(503, { detail: 'Serviço indisponível' });
      renewed = true;
      return response(200, { csrf_token: 'csrf-new' });
    }
    return response(renewed ? 200 : 401);
  });
  await assert.rejects(api('/me'), /Serviço indisponível/);
  await api('/me');
  assert.equal(refreshes, 2);
});

test('loading a CSRF token alone does not mark an expired session as renewed', async () => {
  const delayed = deferred();
  const issued = deferred();
  let meCalls = 0;
  let refreshes = 0;
  const { api } = createClient((url) => {
    if (url.endsWith('/auth/csrf')) return response(200, { csrf_token: 'csrf-loaded' });
    if (url.endsWith('/auth/refresh')) {
      refreshes += 1;
      return response(200, { csrf_token: 'csrf-new' });
    }
    if (++meCalls === 1) {
      issued.resolve();
      return delayed.promise;
    }
    return response(200);
  });
  const original = api('/me');
  await issued.promise;
  await api('/auth/csrf');
  delayed.resolve(response(401));
  await original;
  assert.equal(refreshes, 1);
});

test('a network error does not automatically replay a write', async () => {
  const { api, calls } = createClient(() => { throw new Error('Network unavailable'); });
  await assert.rejects(api('/customers', { method: 'POST', body: { name: 'Cliente' } }), /Network unavailable/);
  assert.equal(calls.length, 1);
});

test('the official landing page exposes the final brand, contact and canonical URL', () => {
  const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
  assert.match(html, /rel="canonical" href="https:\/\/multi-marcenarias\.onrender\.com\/"/);
  assert.match(html, /rel="icon"[^>]+logo-multi-marcenarias-512\.png/);
  assert.match(html, /property="og:image"[^>]+logo-multi-marcenarias-social\.png/);
  assert.match(html, /wa\.me\/5513981236650/);
  assert.match(html, /\+55 \(13\) 98123-6650/);
  assert.doesNotMatch(html, /multi-marcenarias-demo|multi-marcenarias-homologacao|ideal-marcenaria\.onrender\.com/i);
});

test('the official logo assets are present and wired into every logo mark', () => {
  const assets = path.join(__dirname, 'assets');
  assert.ok(fs.statSync(path.join(assets, 'logo-multi-marcenarias-512.png')).size > 10_000);
  assert.ok(fs.statSync(path.join(assets, 'logo-multi-marcenarias-social.png')).size > 10_000);
  const css = fs.readFileSync(path.join(__dirname, 'commercial.css'), 'utf8');
  assert.match(css, /\.logo-mark[^{]*\{[^}]*logo-multi-marcenarias-512\.png/s);
});

test('the public WhatsApp fallback uses the official business contact', () => {
  assert.match(fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8'), /5513981236650/);
});

test('the proposal extension does not install a second registration flow', () => {
  const submitListeners = [];
  const registerForm = {};
  const context = {
    document: {
      addEventListener: (event, listener) => {
        if (event === 'submit') submitListeners.push(listener);
      },
      getElementById: id => (id === 'register-form' ? registerForm : null),
      querySelector: () => null,
    },
    window: { renderResource: () => undefined },
    state: { customers: [], tenant: null, rows: [], search: '', status: '' },
    escapeHtml: value => String(value ?? ''),
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'quote-proposal.js'), 'utf8'), context);

  assert.equal(submitListeners.length, 0);
});

test('the quote decision extension preserves the centralized authenticated fetch', () => {
  const authenticatedFetch = async () => response(200);
  const context = {
    Headers,
    Request,
    confirm: () => true,
    document: { createElement: () => ({ addEventListener: () => {}, dataset: {} }), querySelector: () => null },
    window: { fetch: authenticatedFetch, renderResource: () => undefined },
    state: { rows: [], search: '', status: '' },
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'quote-decisions.js'), 'utf8'), context);

  assert.equal(context.window.fetch, authenticatedFetch);
});

test('smart quote analysis and AI draft use the centralized authenticated API client', async () => {
  const calls = [];
  const estimate = {
    base_cost: '2500.00',
    suggested_total: '3250.00',
    profit_margin: '30.00',
    warnings: [],
    recommendations: [],
  };
  const panel = {};
  const context = {
    FormData,
    api: async (path, options) => {
      calls.push({ path, options });
      return estimate;
    },
    document: {
      createElement: () => ({}),
      querySelector: selector => (selector === '#smart-quote-result' ? panel : null),
    },
    fetch: async () => { throw new Error('raw fetch bypassed authenticated API client'); },
    location: { hostname: 'site.example' },
    window: { API_BASE_URL: 'https://api.example/api/v1', createItem: () => undefined },
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'smart-quotes.js'), 'utf8'), context);

  const result = await context.window.analyzeSmartQuote({ material_cost: 800 });
  const draftPayload = {
    customer_id: 7,
    request_text: 'Armário de três metros em MDF branco.',
    profit_margin: 30,
  };
  await context.window.createSmartQuoteDraft(draftPayload);

  assert.equal(result, estimate);
  assert.equal(calls.length, 2);
  assert.equal(calls[0].path, '/quotes/estimate');
  assert.equal(calls[0].options.method, 'POST');
  assert.deepEqual(calls[0].options.body, { material_cost: 800 });
  assert.equal(calls[1].path, '/quotes/draft');
  assert.equal(calls[1].options.method, 'POST');
  assert.deepEqual(calls[1].options.body, draftPayload);
});

test('decided quotes cannot be edited or deleted from the management table', () => {
  const fullSource = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');
  const resourceSource = fullSource.slice(
    fullSource.indexOf('const configs='),
    fullSource.indexOf('async function boot'),
  );
  const section = { innerHTML: '' };
  const context = {
    FormData,
    confirm: () => true,
    state: {
      rows: [{ id: 81, customer_id: 7, description: 'Armário', total: 3500, status: 'approved' }],
      customers: [{ id: 7, name: 'Cliente' }],
      categories: [],
      search: '',
      status: '',
    },
    statusLabels: { approved: 'Aprovado' },
    escapeHtml: value => String(value ?? ''),
    money: value => `R$ ${value}`,
    $: selector => (selector === '#quotes' ? section : null),
    $$: () => [],
  };
  vm.createContext(context);
  vm.runInContext(`${resourceSource}\nglobalThis.testRenderResource=renderResource;`, context);

  context.testRenderResource('quotes');

  assert.doesNotMatch(section.innerHTML, />Editar</);
  assert.doesNotMatch(section.innerHTML, />Excluir</);
});

test('quote technical edit form omits protected status and calculated total', () => {
  const fullSource = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');
  const resourceSource = fullSource.slice(
    fullSource.indexOf('const configs='),
    fullSource.indexOf('async function boot'),
  );
  const context = {
    FormData,
    state: { customers: [{ id: 7, name: 'Cliente' }], categories: [] },
    escapeHtml: value => String(value ?? ''),
  };
  vm.createContext(context);
  vm.runInContext(`${resourceSource}\nglobalThis.testFormHtml=formHtml;`, context);

  const html = context.testFormHtml('quotes', {
    customer_id: 7,
    description: 'Armário',
    status: 'analysis',
    total: 3500,
    material_cost: 1200,
    hardware_cost: 400,
    labor_cost: 700,
    finishing_cost: 200,
    profit_margin: 30,
  });

  assert.doesNotMatch(html, /name="status"/);
  assert.doesNotMatch(html, /name="total"/);
  assert.match(html, /name="material_cost"/);
  assert.match(html, /name="profit_margin"/);
});

test('operations forms expose suppliers and materials without bypassing project workflow', () => {
  const fullSource = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');
  const resourceSource = fullSource.slice(
    fullSource.indexOf('const configs='),
    fullSource.indexOf('async function boot'),
  );
  const context = {
    FormData,
    state: {
      customers: [{ id: 7, name: 'Cliente' }],
      categories: [],
      suppliers: [{ id: 4, name: 'Fornecedor MDF' }],
    },
    escapeHtml: value => String(value ?? ''),
  };
  vm.createContext(context);
  vm.runInContext(
    `${resourceSource}\nglobalThis.testFormHtml=formHtml;globalThis.testConfigs=configs;`,
    context,
  );

  assert.equal(context.testConfigs.suppliers.endpoint, '/suppliers');
  assert.equal(context.testConfigs.materials.endpoint, '/materials');
  const material = context.testFormHtml('materials', {});
  assert.match(material, /name="supplier_id"/);
  assert.match(material, /name="unit_cost"/);
  assert.match(material, /name="waste_percent"/);
  const project = context.testFormHtml('projects', {
    customer_id: 7,
    name: 'Cozinha',
    status: 'production',
  });
  assert.doesNotMatch(project, /name="status"/);
});
