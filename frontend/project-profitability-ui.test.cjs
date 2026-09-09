const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

test('adiciona botão e consulta rentabilidade do projeto vendido', async () => {
  const source = fs.readFileSync(path.join(__dirname, 'project-profitability.js'), 'utf8');
  const calls = [];
  let modalOpened = false;
  const title = { textContent: '' };
  const form = { innerHTML: '' };
  const modal = {
    classList: { remove(name) { if (name === 'hidden') modalOpened = true; } },
    setAttribute() {},
  };
  const style = { id: '', textContent: '' };
  const head = { appendChild() {} };

  const context = {
    console,
    api: async (path) => {
      calls.push(path);
      return {
        project_id: 2,
        quote_id: 2,
        sold_total: '7020.00',
        expected_cost: '5400.00',
        real_cost: '2500.00',
        real_profit: '4520.00',
        real_margin_percent: '64.39',
        cost_variance: '-2900.00',
        cost_variance_percent: '-53.70',
        health: 'healthy',
      };
    },
    toast: () => {},
    closeModal: () => {},
    rowActions: () => '<button>Editar</button>',
    document: {
      head,
      querySelector(selector) {
        if (selector === '#mm-profitability-style') return null;
        if (selector === '#modal-title') return title;
        if (selector === '#item-form') return form;
        if (selector === '#modal') return modal;
        if (selector === '[data-project-profitability="2"]') return null;
        return null;
      },
      createElement(tag) {
        return tag === 'style' ? style : {};
      },
    },
    window: {},
  };

  vm.runInNewContext(source, context);

  const actions = context.rowActions('projects', { id: 2, quote_id: 2 });
  assert.match(actions, /Rentabilidade/);
  assert.match(actions, /data-project-profitability="2"/);

  await context.window.openProjectProfitability(2);

  assert.deepEqual(calls, ['/projects/2/profitability']);
  assert.equal(title.textContent, 'Rentabilidade — Projeto #2');
  assert.equal(modalOpened, true);
  assert.match(form.innerHTML, /R\$\s*7\.020,00/);
  assert.match(form.innerHTML, /R\$\s*2\.500,00/);
  assert.match(form.innerHTML, /64,39%/);
  assert.match(form.innerHTML, /rentabilidade só é definitiva/i);
});

test('loader usa versão explícita para evitar cache antigo', () => {
  const loader = fs.readFileSync(path.join(__dirname, 'quote-decisions.js'), 'utf8');
  assert.match(loader, /project-profitability\.js\?v=20260909-1/);
});
