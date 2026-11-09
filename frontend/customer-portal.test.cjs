const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const read = name => fs.readFileSync(path.join(__dirname, name), 'utf8');

test('customer portal is loaded by the published frontend', () => {
  const html = read('index.html');
  assert.match(html, /customer-portal\.css/);
  assert.match(html, /customer-portal\.js/);
});

test('customer portal uses its own cookie session and csrf protection', () => {
  const source = read('customer-portal.js');
  assert.match(source, /customer_csrf_token/);
  assert.match(source, /credentials:'include'/);
  assert.match(source, /X-CSRF-Token/);
  assert.match(source, /\/quotes\/\$\{id\}\/decision/);
  assert.doesNotMatch(source, /material_cost|hardware_cost|labor_cost|finishing_cost/);
});

test('customer portal provides the complete customer navigation', () => {
  const source = read('customer-portal.js');
  for (const label of ['Visão geral', 'Orçamentos', 'Projetos', 'Mensagens', 'Meus dados']) {
    assert.match(source, new RegExp(label));
  }
  assert.match(source, /Ativar meu portal/);
  assert.match(source, /Visualizar \/ Salvar PDF/);
  assert.match(source, /Aceitar proposta/);
});
