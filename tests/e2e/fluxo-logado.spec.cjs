const { randomUUID } = require('node:crypto');
const { test, expect } = require('playwright/test');

const site = new URL(process.env.E2E_BASE_URL || 'http://localhost:3000');
const apiOrigin = new URL(process.env.E2E_API_URL || 'http://localhost:8000').origin;
const email = process.env.E2E_EMAIL;
const password = process.env.E2E_PASSWORD;
const productionHosts = new Set([
  'multi-marcenarias.onrender.com',
  'ideal-marcenaria-api.onrender.com',
  'ideal-marcenaria.onrender.com',
]);
test.use({ serviceWorkers: 'block' });

const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

async function apiAction(page, method, path, click) {
  const [response] = await Promise.all([
    page.waitForResponse(res => {
      const url = new URL(res.url());
      return url.origin === apiOrigin &&
        url.pathname === '/api/v1' + path &&
        res.request().method() === method;
    }),
    click(),
  ]);
  expect(response.ok(), method + ' ' + path + ' retornou HTTP ' + response.status()).toBe(true);
  return response;
}

async function login(page) {
  await page.locator('#open-login').filter({ visible: true }).click();
  const form = page.locator('#login-form');
  await expect(form).toBeVisible();
  await form.getByLabel('E-mail', { exact: true }).fill(email);
  await form.locator('#login-password').fill(password);
  await apiAction(page, 'POST', '/auth/login',
    () => form.getByRole('button', { name: 'Entrar', exact: true }).click());
  await expect(page.locator('#admin-app')).toBeVisible();
}

async function section(page, id, name) {
  await page.locator('#admin-nav').getByRole('button', { name }).click();
  const panel = page.locator('#' + id);
  await expect(panel.getByRole('table')).toBeVisible();
  return panel;
}

function rowWith(page, panel, text) {
  return panel.getByRole('row').filter({ has: page.getByRole('cell', { name: text, exact: true }) });
}

test('cliente, produto e orçamento persistem após novo login', async ({ page, context }) => {
  test.setTimeout(120_000);
  if (!email || !password) throw new Error('Defina E2E_EMAIL e E2E_PASSWORD para um administrador de teste.');
  if (productionHosts.has(site.hostname) || productionHosts.has(new URL(apiOrigin).hostname)) {
    throw new Error('Use um ambiente de teste com banco separado. Este roteiro cria registros.');
  }

  // O app pode definir outra API no HTML. Bloqueia escritas fora da API de teste.
  await context.route('**/*', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (/^(GET|HEAD|OPTIONS)$/i.test(request.method()) ||
        (url.origin === apiOrigin && url.pathname.startsWith('/api/v1/'))) {
      return route.continue();
    }
    return route.abort('blockedbyclient');
  });

  const key = randomUUID();
  const customerName = 'Cliente QA ' + key;
  const productName = 'Produto QA ' + key;
  const quoteName = 'Orçamento QA ' + key;
  const price = 249.90;
  const quantity = 2;
  const total = 499.80;
  const modal = page.locator('#modal');

  await test.step('Entrar como administrador de teste', async () => {
    await page.goto(site.href);
    await login(page);
  });

  const customer = await test.step('Cadastrar cliente', async () => {
    const panel = await section(page, 'customers', /Clientes/);
    await panel.getByRole('button', { name: /Novo/ }).click();
    await modal.getByLabel('Nome', { exact: true }).fill(customerName);
    await modal.getByLabel('E-mail', { exact: true }).fill('qa+' + key + '@example.com');
    const response = await apiAction(page, 'POST', '/customers',
      () => modal.getByRole('button', { name: 'Cadastrar', exact: true }).click());
    await expect(modal).toBeHidden();
    await expect(rowWith(page, panel, customerName)).toBeVisible();
    return response.json();
  });

  const product = await test.step('Cadastrar produto com preço', async () => {
    const panel = await section(page, 'products', /Produtos/);
    await panel.getByRole('button', { name: /Novo/ }).click();
    const category = modal.getByLabel('Categoria', { exact: true });
    const options = category.locator('option:not([value=""])');
    await expect(options.first(), 'Cadastre uma categoria no ambiente de teste').toBeAttached();
    await category.selectOption(await options.first().getAttribute('value'));
    await modal.getByLabel('Nome', { exact: true }).fill(productName);
    await modal.getByLabel('Valor', { exact: true }).fill(price.toFixed(2));
    const response = await apiAction(page, 'POST', '/products',
      () => modal.getByRole('button', { name: 'Cadastrar', exact: true }).click());
    await expect(modal).toBeHidden();
    await expect(rowWith(page, panel, productName)).toContainText(currency.format(price));
    const saved = await response.json();
    expect(Number(saved.price)).toBe(price);
    return saved;
  });

  const quote = await test.step('Salvar orçamento e adicionar o móvel', async () => {
    const panel = await section(page, 'quotes', /Orçamentos/);
    await panel.getByRole('button', { name: /Novo/ }).click();
    await modal.getByLabel('Cliente', { exact: true }).selectOption(String(customer.id));
    await modal.getByLabel('Descrição', { exact: true }).fill(quoteName);
    await modal.getByLabel('Material', { exact: true }).fill(total.toFixed(2));
    await modal.getByLabel('Margem de lucro (%)', { exact: true }).fill('0');
    await modal.getByRole('checkbox', { name: /Revisei/ }).check();
    await apiAction(page, 'POST', '/quotes/estimate',
      () => modal.getByRole('button', { name: 'Calcular preço' }).click());
    const response = await apiAction(page, 'POST', '/quotes',
      () => modal.getByRole('button', { name: 'Salvar orçamento' }).click());
    const saved = await response.json();
    expect(Number(saved.customer_id)).toBe(Number(customer.id));

    // A tela de itens usa nome e preço digitados, sem selecionar um ID de catálogo.
    await modal.getByLabel('Nome do móvel', { exact: true }).fill(product.name);
    await modal.getByLabel('Quantidade', { exact: true }).fill(String(quantity));
    await modal.getByLabel('Preço unitário', { exact: true }).fill(Number(product.price).toFixed(2));
    await apiAction(page, 'POST', '/quotes/' + saved.id + '/items',
      () => modal.getByRole('button', { name: /Adicionar móvel/ }).click());
    await expect(modal.locator('#quote-items-list')).toContainText(productName);
    await expect(modal.locator('#quote-items-total')).toHaveText(currency.format(total));
    await modal.getByRole('button', { name: 'Fechar', exact: true }).and(modal.locator('#quote-items-close')).click();
    return saved;
  });

  await test.step('Sair e voltar ao login', async () => {
    await Promise.all([
      page.waitForEvent('domcontentloaded'),
      apiAction(page, 'POST', '/auth/logout', () => page.locator('#logout').click()),
    ]);
    // O logout atual recarrega a página pública. O formulário abre pelo botão Entrar.
    await expect(page.locator('#admin-app')).toBeHidden();
    await expect(page.locator('#open-login').filter({ visible: true })).toBeVisible();
  });

  await test.step('Entrar novamente', () => login(page));

  await test.step('Confirmar cliente, valor e item persistidos', async () => {
    const panel = await section(page, 'quotes', /Orçamentos/);
    const row = rowWith(page, panel, quoteName);
    await expect(row.getByRole('cell', { name: customerName, exact: true })).toBeVisible();
    await expect(row.getByRole('cell', { name: currency.format(total), exact: true })).toBeVisible();

    // A tabela não mostra produtos. Consulta de leitura usando a sessão do navegador.
    const items = await page.evaluate(id => window.api('/quotes/' + id + '/items'), quote.id);
    expect(items).toHaveLength(1);
    expect(items[0].name).toBe(productName);
    expect(Number(items[0].quantity)).toBe(quantity);
    expect(Number(items[0].unit_price)).toBe(price);
    expect(Number(items[0].subtotal)).toBe(total);
  });
});
