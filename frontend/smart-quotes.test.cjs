const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const source = fs.readFileSync(path.join(__dirname, 'smart-quotes.js'), 'utf8');

class Element {
  constructor(value = '') { this.value = value; this.checked = false; this.disabled = false; this.listeners = {}; this.nodes = new Map(); this.isConnected = true; this.classList = { remove() {}, add() {} }; }
  querySelector(selector) { if (!this.nodes.has(selector)) this.nodes.set(selector, new Element()); return this.nodes.get(selector); }
  addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); }
  setAttribute() {}
  async fire(name, event = {}) { for (const handler of this.listeners[name] || []) await handler({ target: this, ...event }); }
}

async function harness() {
  const form = new Element();
  const smart = form.querySelector('.smart-quote-create');
  const doc = new Element();
  doc.nodes.set('#item-form', form);
  const calls = [], pending = [], toasts = [];
  const context = {
    document: doc, closeModal() {}, toast: message => toasts.push(message), showSection() {}, loadResource() {},
    api: async (route, options) => {
      if (route.startsWith('/customers')) return [{ id: 1, name: 'Cliente' }];
      calls.push({ route, options });
      return new Promise((resolve, reject) => pending.push({ resolve, reject }));
    },
    window: { createItem() {}, crypto: { randomUUID: () => 'stable-request-key' } },
    $: selector => doc.querySelector(selector),
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  await context.window.openSmartQuote();
  const field = name => smart.querySelector(`[name="${name}"]`);
  const button = name => smart.querySelector(`[data-smart-${name}]`);
  field('customer_id').value = '1'; field('description').value = 'Armário revisado';
  field('request_text').value = 'Armário de cozinha MDF'; field('profit_margin').value = '30';
  field('material_cost').value = '100';
  return { context, smart, doc, calls, pending, field, button, toasts };
}

const estimate = { base_cost: '100', suggested_total: '130', profit_margin: '30', interpretation_source: 'assisted_local' };
const draft = { ...estimate, brief: { normalized_description: 'Armário técnico', missing_data: ['Altura'], questions: ['Qual altura?'], risks: ['<script>attack</script>'], confidence_score: 40 }, unpriced_items: [] };

test('requires human review, blocks simultaneous actions, and rejects stale calculation', async () => {
  const h = await harness();
  await h.button('analyze').fire('click');
  assert.equal(h.calls.length, 0);
  h.field('human_reviewed').checked = true;
  const request = h.button('analyze').fire('click');
  await h.button('interpret').fire('click'); await h.button('analyze').fire('click'); await h.button('save').fire('click');
  assert.equal(h.calls.length, 1);
  h.field('material_cost').value = '250'; await h.field('material_cost').fire('input');
  h.pending[0].resolve(estimate); await request;
  assert.equal(h.button('save').disabled, true);
  assert.equal(h.field('human_reviewed').checked, false);
});

test('shows missing data and questions safely; interpretation alone cannot save', async () => {
  const h = await harness();
  const request = h.button('interpret').fire('click');
  h.pending[0].resolve(draft); await request;
  const html = h.smart.querySelector('#smart-quote-brief').innerHTML;
  assert.match(html, /Dados faltantes/); assert.match(html, /Qual altura/);
  assert.match(html, /&lt;script&gt;/); assert.doesNotMatch(html, /<script>/);
  assert.match(h.smart.querySelector('#smart-quote-state').textContent, /Fallback local/);
  assert.equal(h.button('save').disabled, true);
  await h.button('save').fire('click'); assert.equal(h.calls.length, 1);
});

test('retries saving with the same idempotency key and prevents double submission', async () => {
  const h = await harness();
  h.field('human_reviewed').checked = true;
  const calc = h.button('analyze').fire('click'); h.pending[0].resolve(estimate); await calc;
  assert.equal(h.button('save').disabled, false);
  const save = h.button('save').fire('click'); await h.button('save').fire('click');
  assert.equal(h.calls.length, 2);
  h.pending[1].reject(new Error('Conexão interrompida')); await save;
  assert.equal(h.button('save').disabled, false);
  const retry = h.button('save').fire('click');
  assert.equal(h.calls[1].options.headers['Idempotency-Key'], h.calls[2].options.headers['Idempotency-Key']);
  h.pending[2].reject(new Error('Tente novamente')); await retry;
});

test('zero totals and closed modal responses cannot enable save', async () => {
  const h = await harness(); h.field('human_reviewed').checked = true;
  const calc = h.button('analyze').fire('click'); h.pending[0].resolve({ ...estimate, suggested_total: '0' }); await calc;
  assert.equal(h.button('save').disabled, true);
  const another = h.button('interpret').fire('click'); h.smart.isConnected = false;
  h.pending[1].resolve(draft); await another;
  assert.equal(h.field('description').value, 'Armário revisado');
});

test('module initialization and Enter do not install duplicate CRUD handlers', async () => {
  const h = await harness();
  vm.runInContext(source, h.context);
  assert.equal(h.doc.listeners.submit.length, 1);
  let prevented = 0, stopped = 0;
  await h.doc.fire('submit', { target: { querySelector: () => h.smart }, preventDefault: () => prevented++, stopImmediatePropagation: () => stopped++ });
  assert.equal(prevented, 1); assert.equal(stopped, 1);
});
