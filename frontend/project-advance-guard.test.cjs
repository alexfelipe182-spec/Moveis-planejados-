const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

test('bloqueia clique duplo enquanto o projeto esta avancando', async () => {
  const source = fs.readFileSync(path.join(__dirname, 'quote-decisions.js'), 'utf8');
  let resolveAdvance;
  let advanceCalls = 0;
  const button = {
    disabled: false,
    textContent: 'Avançar →',
    dataset: {},
    isConnected: true,
    getAttribute(name) {
      return name === 'onclick' ? "advanceProject(2,'purchasing')" : '';
    },
    setAttribute() {},
    removeAttribute() {},
  };

  const context = {
    console,
    confirm: () => true,
    api: async () => ({}),
    toast: () => {},
    loadResource: async () => {},
    state: { rows: [], search: '', status: '' },
    document: {
      querySelector: () => null,
      querySelectorAll: selector => selector === '#projects button' ? [button] : [],
      createElement: () => ({ dataset: {}, addEventListener() {}, set type(_) {}, set className(_) {}, set textContent(_) {} }),
    },
    window: {
      renderResource: () => undefined,
      advanceProject: async () => {
        advanceCalls += 1;
        await new Promise(resolve => { resolveAdvance = resolve; });
      },
    },
  };

  vm.runInNewContext(source, context);

  const first = context.window.advanceProject(2, 'purchasing');
  const second = context.window.advanceProject(2, 'purchasing');

  assert.equal(advanceCalls, 1);
  assert.equal(button.disabled, true);
  assert.equal(button.textContent, 'Avançando...');

  await second;
  resolveAdvance();
  await first;

  assert.equal(button.disabled, false);
  assert.equal(button.textContent, 'Avançar →');
});
