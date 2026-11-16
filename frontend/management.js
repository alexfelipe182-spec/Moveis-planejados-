(() => {
  const number = new Intl.NumberFormat('pt-BR');
  const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  const names = {
    active: 'Ativa', trialing: 'Em teste', trial_expired: 'Teste encerrado',
    canceled: 'Cancelada', past_due: 'Pagamento pendente', unpaid: 'Não paga',
    incomplete: 'Incompleta', incomplete_expired: 'Incompleta expirada',
    pending: 'Pendente', analysis: 'Em análise', sent: 'Enviado',
    approved: 'Aprovado', accepted: 'Aceito', declined: 'Recusado',
    rejected: 'Rejeitado', completed: 'Concluído', planning: 'Planejamento',
    measurement: 'Medição', technical_design: 'Projeto técnico', purchasing: 'Compras',
    production: 'Produção', installation: 'Instalação', in_progress: 'Em andamento',
    starter: 'Essencial', professional: 'Profissional', business: 'Empresa',
  };
  const label = (value) => names[value] || value;
  const date = (value) => value.split('-').reverse().join('/');

  function element(tag, content, className) {
    const node = document.createElement(tag);
    if (content !== undefined) node.textContent = content;
    if (className) node.className = className;
    return node;
  }

  function panel(container, title) {
    const box = element('div', undefined, 'panel');
    box.append(element('h3', title));
    container.append(box);
    return box;
  }

  function table(box, headings, rows, empty) {
    if (!rows.length) {
      box.append(element('p', empty, 'muted'));
      return;
    }
    const scroll = element('div', undefined, 'table-wrap');
    scroll.style.overflowX = 'auto';
    const grid = element('table');
    const head = grid.createTHead().insertRow();
    headings.forEach((heading) => {
      const cell = element('th', heading);
      cell.scope = 'col';
      head.append(cell);
    });
    const body = grid.createTBody();
    rows.forEach((row) => {
      const line = body.insertRow();
      row.forEach((value) => line.append(element('td', value)));
    });
    scroll.append(grid);
    box.append(scroll);
  }

  function action(box, title, handler) {
    const button = element('button', title, 'btn secondary');
    button.type = 'button';
    button.addEventListener('click', handler);
    box.append(button);
  }

  function exportReport(box, filename, headings, rows) {
    action(box, 'Exportar CSV', () => {
      const csv = [headings, ...rows].map((row) => row.map((value) => {
        let cell = String(value);
        if (/^(?:\s*[=+\-@]|[\t\r\n])/.test(cell)) cell = "'" + cell;
        return '"' + cell.replaceAll('"', '""') + '"';
      }).join(';')).join('\r\n');
      const url = URL.createObjectURL(new Blob(['\uFEFF', csv], { type: 'text/csv;charset=utf-8' }));
      const link = element('a');
      link.href = url;
      link.download = filename;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }

  function overview(container, entries) {
    const tiles = element('div', undefined, 'dashboard-kpis');
    entries.forEach(([title, value]) => {
      const tile = element('div', undefined, 'dashboard-kpi');
      tile.append(element('span', title), element('strong', value));
      tiles.append(tile);
    });
    container.append(tiles);
  }

  function renderBusiness(container, data) {
    overview(container, [
      ['Clientes cadastrados', number.format(data.customers)],
      ['Projetos listados na agenda', number.format(data.schedule.length)],
      ['Orçamentos cadastrados', number.format(data.quotes.reduce((total, row) => total + row.count, 0))],
    ]);
    const links = panel(container, 'Atalhos da operação');
    [
      ['Clientes', 'customers'], ['Produtos', 'products'], ['Orçamentos', 'quotes'],
      ['Produção', 'projects'], ['Serviços', 'categories'], ['Insumos', 'materials'],
    ].forEach(([title, section]) => action(links, title, () => window.showSection(section)));

    const schedule = panel(container, 'Agenda de projetos');
    schedule.append(element('p', date(data.today) + ' a ' + date(data.end), 'muted'));
    table(schedule, ['Data', 'Projeto', 'Etapa'], data.schedule.map((row) => [
      date(row.project_date), row.name, label(row.status),
    ]), 'Nenhum projeto previsto para o período.');
    if (data.schedule_truncated) schedule.append(element('p', 'São exibidos os 50 primeiros projetos do período.'));

    const report = panel(container, 'Relatório de orçamentos');
    report.append(element('p', 'Os valores representam propostas cadastradas.', 'muted'));
    const headings = ['Situação', 'Quantidade', 'Valor dos orçamentos'];
    const rows = data.quotes.map((row) => [label(row.status), number.format(row.count), money.format(row.total)]);
    table(report, headings, rows, 'Nenhum orçamento cadastrado.');
    if (rows.length) exportReport(report, 'orcamentos-por-situacao.csv', headings, rows);
  }

  function renderPlatform(container, data) {
    const counts = data.subscription_statuses;
    overview(container, [
      ['Marcenarias cadastradas', number.format(data.tenants)],
      ['Cadastros habilitados', number.format(data.active_tenants)],
      ['Assinaturas em teste', number.format(counts.trialing || 0)],
      ['Receita mensal estimada por planos Stripe ativos', money.format(data.estimated_mrr_brl)],
    ]);
    const subscriptions = panel(container, 'Situação das assinaturas');
    const headings = ['Situação', 'Quantidade'];
    const statuses = Object.entries(counts).map(([status, count]) => [label(status), number.format(count)]);
    table(subscriptions, headings, statuses, 'Nenhuma assinatura cadastrada.');
    if (statuses.length) exportReport(subscriptions, 'assinaturas-por-situacao.csv', headings, statuses);
    table(panel(container, 'Últimas marcenarias cadastradas'), ['Marcenaria', 'Plano', 'Cadastro'],
      data.latest_tenants.map((row) => [row.name, label(row.plan_code), row.is_active ? 'Habilitado' : 'Desabilitado']),
      'Nenhuma marcenaria cadastrada.');
  }

  const requests = new Map();
  let session = 0;
  async function load(mode) {
    const container = document.getElementById(mode);
    const platform = mode === 'platform-management';
    const request = Symbol();
    requests.set(mode, request);
    container.replaceChildren(element('p', 'Carregando…', 'muted'));
    try {
      const data = await window.api(platform ? '/platform/dashboard' : '/admin/management');
      if (requests.get(mode) !== request) return;
      container.replaceChildren();
      (platform ? renderPlatform : renderBusiness)(container, data);
    } catch (error) {
      if (requests.get(mode) !== request) return;
      container.replaceChildren(element('p', error.message, 'panel'));
      action(container, 'Tentar novamente', () => load(mode));
    }
  }

  document.addEventListener('mm:auth-changed', async () => {
    const current = ++session;
    requests.clear();
    document.getElementById('management').replaceChildren();
    document.getElementById('platform-management').replaceChildren();
    const button = document.getElementById('platform-management-nav');
    button.classList.add('hidden');
    if (document.getElementById('admin-app').classList.contains('hidden')) return;
    try {
      const data = await window.api('/platform/access');
      if (current === session && data.is_platform_owner === true) button.classList.remove('hidden');
    } catch {
      // The owner shortcut stays hidden when auth cannot be verified.
    }
  });
  window.mmManagement = { load };
})();
