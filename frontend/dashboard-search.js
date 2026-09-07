(() => {
  const resources = [
    { key: 'customers', label: 'Clientes', endpoint: '/customers' },
    { key: 'quotes', label: 'Orçamentos', endpoint: '/quotes' },
    { key: 'projects', label: 'Projetos', endpoint: '/projects' },
    { key: 'products', label: 'Produtos', endpoint: '/products' },
  ];

  let searchSequence = 0;

  const normalize = (value) => String(value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();

  const escapeHtml = (value = '') => String(value).replace(/[&<>'\"]/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '\"': '&quot;',
  })[character]);

  function matchesQuery(row, query) {
    const needle = normalize(query);
    return Object.values(row || {}).some((value) => normalize(value).includes(needle));
  }

  function resultsContainer() {
    const search = document.querySelector('#dashboard .dashboard-search');
    if (!search) return null;
    let results = search.querySelector('.dashboard-search-results');
    if (!results) {
      results = document.createElement('div');
      results.className = 'dashboard-search-results';
      results.setAttribute('role', 'status');
      results.setAttribute('aria-live', 'polite');
      search.appendChild(results);
    }
    return results;
  }

  function installStyles() {
    if (document.querySelector('#mm-dashboard-search-style')) return;
    const style = document.createElement('style');
    style.id = 'mm-dashboard-search-style';
    style.textContent = `
      #dashboard .dashboard-search{position:relative;display:flex;gap:8px;align-items:center}
      #dashboard .dashboard-search input{min-width:min(360px,56vw)}
      #dashboard .dashboard-search .dashboard-search-trigger{white-space:nowrap}
      #dashboard .dashboard-search-results{position:absolute;right:0;top:calc(100% + 8px);z-index:50;width:min(430px,calc(100vw - 28px));display:none;padding:10px;background:#fff;border:1px solid rgba(13,89,61,.16);border-radius:14px;box-shadow:0 18px 44px rgba(9,54,38,.16)}
      #dashboard .dashboard-search-results.open{display:grid;gap:6px}
      #dashboard .dashboard-search-results button{width:100%;display:flex;justify-content:space-between;gap:12px;align-items:center;border:0;background:#f6faf7;border-radius:10px;padding:10px 12px;text-align:left;font:inherit;color:#102119;cursor:pointer}
      #dashboard .dashboard-search-results button:hover,#dashboard .dashboard-search-results button:focus-visible{background:#eaf6ef;outline:2px solid rgba(13,89,61,.22);outline-offset:1px}
      #dashboard .dashboard-search-results strong{color:#102119}
      #dashboard .dashboard-search-results small{color:#53645b}
      #dashboard .dashboard-search-results .empty{padding:10px 12px;color:#53645b}
      body.dark #dashboard .dashboard-search-results{background:#122019;border-color:rgba(255,255,255,.12)}
      body.dark #dashboard .dashboard-search-results button{background:#182a21;color:#f8fafc}
      body.dark #dashboard .dashboard-search-results strong{color:#f8fafc}
      body.dark #dashboard .dashboard-search-results small,body.dark #dashboard .dashboard-search-results .empty{color:#cbd5d1}
      @media(max-width:760px){#dashboard .dashboard-search{width:100%;align-items:stretch}#dashboard .dashboard-search input{min-width:0;flex:1}#dashboard .dashboard-search-results{left:0;right:auto}}
    `;
    document.head.appendChild(style);
  }

  async function openFilteredResource(resource, query) {
    const section = document.querySelector(`#${resource}`);
    if (!section) return;

    document.querySelectorAll('.admin-section').forEach((item) => item.classList.add('hidden'));
    section.classList.remove('hidden');
    document.querySelectorAll('#admin-nav .nav').forEach((button) => {
      button.classList.toggle('active', button.dataset.section === resource);
    });
    const title = document.querySelector('#admin-title');
    const meta = resources.find((item) => item.key === resource);
    if (title) title.textContent = meta?.label || 'Resultados';

    await loadResource(resource);
    state.search = query;
    renderResource(resource);
  }

  function renderSearchResults(query, groups) {
    const results = resultsContainer();
    if (!results) return;
    const populated = groups.filter((group) => group.count > 0);
    if (!populated.length) {
      results.innerHTML = `<div class="empty">Nenhum resultado para <strong>${escapeHtml(query)}</strong>.</div>`;
      results.classList.add('open');
      return;
    }

    results.innerHTML = populated.map((group) => `
      <button type="button" data-dashboard-search-resource="${group.key}">
        <strong>${escapeHtml(group.label)}</strong>
        <small>${group.count} ${group.count === 1 ? 'resultado' : 'resultados'} →</small>
      </button>`).join('');
    results.classList.add('open');
    results.querySelectorAll('[data-dashboard-search-resource]').forEach((button) => {
      button.addEventListener('click', async () => {
        results.classList.remove('open');
        await openFilteredResource(button.dataset.dashboardSearchResource, query);
      });
    });
  }

  async function searchDashboard(query) {
    const trimmed = String(query || '').trim();
    if (trimmed.length < 2) {
      toast('Digite pelo menos 2 caracteres para buscar.', 'error');
      return;
    }

    const sequence = ++searchSequence;
    const results = resultsContainer();
    if (results) {
      results.innerHTML = '<div class="empty">Buscando...</div>';
      results.classList.add('open');
    }

    try {
      const groups = await Promise.all(resources.map(async (resource) => {
        const rows = await api(`${resource.endpoint}?limit=100`);
        return {
          ...resource,
          count: (rows || []).filter((row) => matchesQuery(row, trimmed)).length,
        };
      }));
      if (sequence !== searchSequence) return;
      renderSearchResults(trimmed, groups);
    } catch (error) {
      if (sequence !== searchSequence) return;
      if (results) {
        results.innerHTML = `<div class="empty">${escapeHtml(error.message || 'Não foi possível concluir a busca.')}</div>`;
        results.classList.add('open');
      }
    }
  }

  function bindSearch() {
    installStyles();
    const input = document.querySelector('#dashboard .dashboard-search input');
    const search = input?.closest('.dashboard-search');
    if (!input || !search || input.dataset.mmDashboardSearchBound) return;

    input.dataset.mmDashboardSearchBound = 'true';
    input.placeholder = 'Buscar clientes, projetos, orçamentos...';
    input.setAttribute('autocomplete', 'off');
    input.setAttribute('aria-label', 'Buscar clientes, projetos, orçamentos e produtos');

    let trigger = search.querySelector('.dashboard-search-trigger');
    if (!trigger) {
      trigger = document.createElement('button');
      trigger.type = 'button';
      trigger.className = 'btn secondary dashboard-search-trigger';
      trigger.textContent = 'Buscar';
      search.appendChild(trigger);
    }

    const run = () => searchDashboard(input.value);
    trigger.addEventListener('click', run);
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        run();
      }
      if (event.key === 'Escape') resultsContainer()?.classList.remove('open');
    });
  }

  function init() {
    bindSearch();
    const dashboard = document.querySelector('#dashboard');
    if (dashboard) new MutationObserver(bindSearch).observe(dashboard, { childList: true, subtree: true });
    document.addEventListener('click', (event) => {
      const search = document.querySelector('#dashboard .dashboard-search');
      if (search?.contains(event.target)) return;
      resultsContainer()?.classList.remove('open');
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
