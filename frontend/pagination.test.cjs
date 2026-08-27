const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8').replace(/\nboot\(\);\s*$/, '');
function reply(rows, total = rows.length, offset = 0, limit = 25) {
  const headers = { 'X-Total-Count': String(total), 'X-Page-Offset': String(offset), 'X-Page-Limit': String(limit) };
  return { status: 200, ok: true, json: async () => rows, headers: { get: name => headers[name] ?? null } };
}
function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}
class Element {
  constructor() { this.innerHTML = ''; this.value = ''; this.dataset = {}; this.events = {}; this.isConnected = true; this.children = []; this.classList = { contains: () => false }; }
  addEventListener(name, handler) { this.events[name] = handler; }
  querySelector(selector) { return this.selectors?.[selector] || null; }
  querySelectorAll(selector) { return this.lists?.[selector] || []; }
  prepend(child) { this.children.unshift(child); }
  appendChild(child) { this.children.push(child); }
  emit(name) { return this.events[name]?.({ target: this }); }
}
function client(handler) {
  const sections = Object.fromEntries(['customers', 'categories', 'quotes', 'products', 'projects', 'users', 'activities'].map(name => [name, new Element()]));
  const calls = [], timers = new Map();
  let timerId = 0;
  const context = {
    URLSearchParams,
    location: { hostname: 'site.example' },
    API_BASE_URL: 'https://api.example/api/v1',
    document: { cookie: '', activeElement: null, querySelector: selector => sections[selector.slice(1)] || null, querySelectorAll: () => [], createElement: () => new Element() },
    fetch: async (url, options) => { const parsed = new URL(url); calls.push(parsed); return handler(parsed, options, calls.length); },
    setTimeout: fn => { timers.set(++timerId, fn); return timerId; },
    clearTimeout: id => timers.delete(id),
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(`${source}\nglobalThis.testState = state;`, context);
  return { context, state: context.testState, sections, calls, runTimers: async () => { const tasks = [...timers.values()]; timers.clear(); await Promise.all(tasks.map(fn => fn())); } };
}

test('list navigation reaches records after 100 with truthful totals', async () => {
  const all = Array.from({ length: 135 }, (_, index) => ({ id: index + 1, name: `Cliente ${index + 1}` }));
  const { context, state, calls, sections } = client(url => {
    const offset = Number(url.searchParams.get('offset'));
    const limit = Number(url.searchParams.get('limit'));
    return reply(all.slice(offset, offset + limit), all.length, offset, limit);
  });
  await context.loadResource('customers');
  for (let page = 0; page < 4; page += 1) await context.changePage('customers', 1);
  assert.equal(state.offset, 100);
  assert.equal(state.rows[0].id, 101);
  assert.equal(state.total, 135);
  assert.match(sections.customers.innerHTML, /135 registro\(s\) encontrados/);
  assert.match(sections.customers.innerHTML, /Página 5 de 6/);
  assert.equal(calls[4].searchParams.get('offset'), '100');
  assert.equal(calls[4].searchParams.get('limit'), '25');
});

test('debounced search sends q to the API and invalidates in-flight old rows immediately', async () => {
  const old = deferred();
  const { context, state, runTimers, calls } = client(url => url.searchParams.get('q') === 'Novo' ? reply([{ id: 135, name: 'Novo' }], 1) : old.promise);
  const pending = context.loadResource('customers');
  context.setSearch('customers', 'No');
  context.setSearch('customers', 'Novo');
  old.resolve(reply([{ id: 1, name: 'Antigo' }], 135));
  await pending;
  assert.equal(state.rows.length, 0, 'a stale response must not appear during the debounce');
  await runTimers();
  assert.equal(calls.length, 2, 'one search request for the final input');
  assert.equal(state.rows[0].id, 135);
  assert.equal(state.total, 1);
});

test('switching resource prevents a late response from overwriting the current section', async () => {
  const old = deferred();
  const { context, state } = client(url => url.pathname.endsWith('/customers') ? old.promise : reply([{ id: 140, name: 'Categoria' }], 1));
  const pending = context.loadResource('customers');
  await context.loadResource('categories');
  old.resolve(reply([{ id: 1, name: 'Cliente' }], 1));
  await pending;
  assert.equal(state.listResource, 'categories');
  assert.equal(state.rows[0].name, 'Categoria');
});

test('related-customer search is not locally re-filtered and status is sent to the server', async () => {
  const { context, state, calls, sections } = client(url => url.pathname.endsWith('/customers')
    ? reply([{ id: 135, name: 'Maria & Filhos' }], 1)
    : reply([{ id: 301, description: 'Armário', customer_id: 135, status: 'sent', total: 300 }], 1));
  state.listResource = 'quotes'; state.search = 'Maria & Filhos'; state.status = 'sent';
  await context.loadResource('quotes');
  assert.equal(calls[0].searchParams.get('q'), 'Maria & Filhos');
  assert.equal(calls[0].searchParams.get('status'), 'sent');
  assert.deepEqual(calls[1].searchParams.getAll('ids'), ['135']);
  assert.match(sections.quotes.innerHTML, /Armário/);
  assert.match(sections.quotes.innerHTML, /Maria &amp; Filhos/);
  assert.match(sections.quotes.innerHTML, /data-row-id="301"/);
});

test('empty last page moves to the nearest existing page and retains filters', async () => {
  const { context, state, calls } = client(url => Number(url.searchParams.get('offset')) >= 125
    ? reply([], 124, 125) : reply([{ id: 121, name: 'Encontrado' }], 124, 100));
  state.listResource = 'customers'; state.offset = 125; state.search = 'Encontrado';
  await context.loadResource('customers');
  assert.equal(state.offset, 100);
  assert.equal(state.rows[0].id, 121);
  assert.equal(calls[1].searchParams.get('q'), 'Encontrado');
});

test('changing page size resets offset but preserves the query', async () => {
  const { context, state, calls } = client(() => reply([], 0));
  state.listResource = 'customers'; state.offset = 100; state.search = 'Termo';
  await context.setPageSize('customers', '50');
  assert.equal(calls[0].searchParams.get('offset'), '0');
  assert.equal(calls[0].searchParams.get('limit'), '50');
  assert.equal(calls[0].searchParams.get('q'), 'Termo');
});

test('collection failure shows a retry error instead of claiming an empty database', async () => {
  const { context, state, sections } = client(() => { throw new Error('Serviço indisponível'); });
  await context.loadResource('customers');
  assert.equal(state.total, null);
  assert.match(sections.customers.innerHTML, /Serviço indisponível/);
  assert.match(sections.customers.innerHTML, /Tentar novamente/);
  assert.doesNotMatch(sections.customers.innerHTML, /Nenhum cliente cadastrado/);
});

function lookup(collection = 'customers', selectedId = '') {
  const root = new Element(), element = new Element(), input = new Element(), select = new Element(), previous = new Element(), next = new Element(), info = new Element();
  element.dataset.collection = collection;
  select.dataset.lookupSelected = selectedId;
  element.selectors = { '[data-lookup-search]': input, select, '[data-lookup-prev]': previous, '[data-lookup-next]': next, '[data-lookup-info]': info };
  root.lists = { '.record-lookup': [element] };
  return { root, element, input, select, previous, next, info };
}

test('a selected customer beyond page 100 remains selected while browsing other options', async () => {
  const row = { id: 135, name: 'Cliente selecionado' };
  const { context, calls } = client(url => url.searchParams.has('ids') ? reply([row], 1) : reply([{ id: 1, name: 'Primeiro cliente' }], 135));
  const field = lookup('customers', '135');
  await context.setupRecordLookups(field.root);
  assert.equal(calls[0].searchParams.get('ids'), '135');
  assert.equal(field.select.value, '135');
  assert.match(field.select.innerHTML, /Cliente selecionado/);
  assert.match(field.select.innerHTML, /Primeiro cliente/);
  assert.equal(field.next.disabled, false);
});

test('reference picker performs global search and real next-page requests', async () => {
  const { context, calls, runTimers } = client(url => reply([{ id: 135, name: 'Último' }], 51, Number(url.searchParams.get('offset'))));
  const field = lookup();
  await context.setupRecordLookups(field.root);
  field.input.value = 'Último';
  field.input.emit('input');
  await runTimers();
  await field.next.emit('click');
  assert.equal(calls[1].searchParams.get('q'), 'Último');
  assert.equal(calls[2].searchParams.get('offset'), '25');
  assert.equal(calls[2].searchParams.get('q'), 'Último');
});

test('reference picker discards late responses from a previous search', async () => {
  const old = deferred();
  const { context, runTimers } = client(url => url.searchParams.has('q') ? reply([{ id: 135, name: 'Novo resultado' }], 1) : old.promise);
  const field = lookup();
  const initial = context.setupRecordLookups(field.root);
  field.input.value = 'Novo'; field.input.emit('input');
  await runTimers();
  old.resolve(reply([{ id: 1, name: 'Antigo resultado' }], 1));
  await initial;
  assert.match(field.select.innerHTML, /Novo resultado/);
  assert.doesNotMatch(field.select.innerHTML, /Antigo resultado/);
});

test('quote decorators bind server-filtered rows by ID, not a second local search', async () => {
  const { context, state, sections } = client(() => reply([], 0));
  const tr = new Element(), actions = new Element();
  tr.dataset.rowId = '301'; tr.selectors = { '.actions': actions };
  sections.quotes.lists = { 'tbody tr': [tr] };
  state.listResource = 'quotes'; state.search = 'Maria'; state.total = 1;
  state.rows = [{ id: 301, description: 'Armário', customer_id: 135, status: 'analysis' }];
  state.customers = [{ id: 135, name: 'Maria' }];
  for (const filename of ['quote-decisions.js', 'quote-proposal.js']) vm.runInContext(fs.readFileSync(path.join(__dirname, filename), 'utf8'), context);
  context.renderResource('quotes');
  assert.ok(actions.children.some(button => button.dataset.quoteDecision === 'approved'));
  assert.ok(actions.children.some(button => button.dataset.quoteItems === '301'));
  assert.ok(actions.children.some(button => button.dataset.quoteProposal === '301'));
});

test('quote edit fields use costs and dedicated transitions rather than an editable total or status', () => {
  const { context } = client(() => reply([], 0));
  const html = context.quoteTechnicalForm({ customer_id: 135, description: 'Armário', material_cost: 250 });
  assert.match(html, /name="material_cost"/);
  assert.match(html, /data-lookup-selected="135"/);
  assert.doesNotMatch(html, /name="status"/);
  assert.doesNotMatch(html, /name="total"/);
});
