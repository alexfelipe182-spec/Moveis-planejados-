const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8').replace(/\nboot\(\);\s*$/, '');

function context() {
  const sandbox = {
    URLSearchParams,
    AbortController,
    setTimeout,
    clearTimeout,
    location: { hostname: 'localhost' },
    document: { cookie: '', querySelector: () => null, querySelectorAll: () => [] },
    fetch: async () => { throw new Error('Unexpected request'); },
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(`${source}\nglobalThis.workspaceHtmlForTest=workspaceHtml;globalThis.platformHtmlForTest=platformHtml;globalThis.workspaceCanWriteForTest=workspaceCanWrite;globalThis.stateForTest=state;`, sandbox);
  return sandbox;
}

test('workspace view makes sandbox billing and access state explicit', () => {
  const c = context();
  const html = c.workspaceHtmlForTest(
    [{ code:'pro', name:'Profissional', monthly_price_cents:9900, max_users:10, features:{ intelligence:true } }],
    { plan_code:'pro', plan_name:'Profissional', status:'past_due', provider:'sandbox', access_allowed:false },
    { user_count:2 },
  );
  assert.match(html, /Plano e equipe/);
  assert.match(html, /Acesso pendente/);
  assert.match(html, /Ambiente sandbox/);
  assert.match(html, /2 de 10 usuários/);
  assert.match(html, /Adicionar membro/);
});

test('platform view contains aggregates and tenant metadata, not operational records', () => {
  const c = context();
  const html = c.platformHtmlForTest(
    { organizations:2, users:5, subscriptions:2, subscription_statuses:{ active:1, trial:1 } },
    [{ id:10, name:'Marcenaria A', slug:'a', status:'active', subscription_status:'trial', plan_id:1, user_count:2 }],
  );
  assert.match(html, /Administração da plataforma/);
  assert.match(html, /Marcenaria A/);
  assert.match(html, /2 marcenarias/);
  assert.doesNotMatch(html, /clientes|orçamentos/i);
});

test('admin bootstrap declares role-scoped SaaS navigation and sections', () => {
  assert.match(source, /data-section="workspace"/);
  assert.match(source, /data-section="platform"/);
  assert.match(source, /is_platform_admin/);
  assert.match(source, /\/billing\/subscription/);
  assert.match(source, /\/onboarding\/members/);
  assert.match(source, /\/platform\/organizations/);
});

test('read-only subscription sends mutation attempts to the billing area', () => {
  const c = context();
  const notices = [], sections = [];
  c.toast = (message, type) => notices.push({ message, type });
  c.showSection = section => sections.push(section);
  c.stateForTest.workspaceAccess = false;
  assert.equal(c.workspaceCanWriteForTest(), false);
  assert.equal(notices[0].type, 'error');
  assert.match(notices[0].message, /somente para leitura/);
  assert.deepEqual(sections, ['workspace']);
});
