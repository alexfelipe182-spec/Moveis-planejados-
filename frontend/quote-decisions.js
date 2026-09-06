(() => {
  const decisionLabels = { approved: 'Aprovar', rejected: 'Rejeitar' };
  const commercialLabels = { accepted: 'Cliente aceitou', declined: 'Cliente recusou' };
  const quoteStatusLabels = {
    sent: 'Enviado • aguardando cliente',
    accepted: 'Aceito pelo cliente',
    declined: 'Recusado pelo cliente',
  };

  async function decideQuote(quoteId, decision) {
    if (!decisionLabels[decision]) throw new Error('Decisão de orçamento inválida.');
    const action = decisionLabels[decision].toLowerCase();
    if (!confirm(`${decisionLabels[decision]} o orçamento #${quoteId}?`)) return;
    try {
      await api(`/quotes/${quoteId}/decision`, { method: 'PATCH', body: { status: decision } });
      toast(`Orçamento #${quoteId} ${action === 'aprovar' ? 'aprovado' : 'rejeitado'} com sucesso.`);
      await loadResource('quotes');
    } catch (error) {
      toast(error.message, 'error');
    }
  }

  async function setCommercialStatus(quoteId, status) {
    if (!commercialLabels[status]) throw new Error('Status comercial inválido.');
    if (!confirm(`${commercialLabels[status]} na proposta #${quoteId}?`)) return;
    try {
      await api(`/quotes/${quoteId}/commercial-status`, { method: 'PATCH', body: { status } });
      toast(`Resposta do cliente registrada na proposta #${quoteId}.`);
      await loadResource('quotes');
    } catch (error) {
      toast(error.message, 'error');
    }
  }

  function button(text, className, dataset, onClick) {
    const element = document.createElement('button');
    element.type = 'button';
    element.className = className;
    Object.entries(dataset).forEach(([key, value]) => { element.dataset[key] = value; });
    element.textContent = text;
    element.addEventListener('click', onClick);
    return element;
  }

  function visibleQuotes() {
    let rows = state.rows.filter(row => !state.search || Object.values(row).some(value => String(value ?? '').toLowerCase().includes(state.search.toLowerCase())));
    if (state.status) rows = rows.filter(row => row.status === state.status);
    return rows;
  }

  function enhanceCommercialStatuses() {
    const section = document.querySelector('#quotes');
    if (!section || section.classList.contains('hidden')) return;

    const filter = section.querySelector('select.filter');
    if (filter) {
      Object.entries(quoteStatusLabels).forEach(([value, label]) => {
        if (filter.querySelector(`option[value="${value}"]`)) return;
        const option = document.createElement('option');
        option.value = value;
        option.textContent = label;
        filter.appendChild(option);
      });
      filter.value = state.status || '';
    }

    const quotes = visibleQuotes();
    [...section.querySelectorAll('tbody tr')].forEach((tr, index) => {
      const quote = quotes[index];
      if (!quote || !quoteStatusLabels[quote.status]) return;
      const statusCell = tr.querySelectorAll('td')[3];
      const badge = statusCell?.querySelector('.badge');
      if (badge) badge.textContent = quoteStatusLabels[quote.status];
    });
  }

  function addDecisionButtons() {
    const section = document.querySelector('#quotes');
    if (!section || section.classList.contains('hidden')) return;
    const rows = [...section.querySelectorAll('tbody tr')];
    const quotes = visibleQuotes();
    rows.forEach((tr, index) => {
      const quote = quotes[index];
      const actions = tr.querySelector('.actions');
      if (!quote || !actions || actions.querySelector('[data-quote-decision], [data-commercial-status]')) return;

      if (quote.status === 'analysis') {
        actions.prepend(button('Rejeitar', 'small-btn danger', { quoteDecision: 'rejected' }, () => decideQuote(quote.id, 'rejected')));
        actions.prepend(button('Aprovar', 'small-btn', { quoteDecision: 'approved' }, () => decideQuote(quote.id, 'approved')));
      }

      if (quote.status === 'sent') {
        actions.prepend(button('Cliente recusou', 'small-btn danger', { commercialStatus: 'declined' }, () => setCommercialStatus(quote.id, 'declined')));
        actions.prepend(button('Cliente aceitou', 'small-btn', { commercialStatus: 'accepted' }, () => setCommercialStatus(quote.id, 'accepted')));
      }
    });
  }

  const originalRenderResource = window.renderResource;
  window.renderResource = function(resource) {
    const result = originalRenderResource(resource);
    if (resource === 'quotes') {
      enhanceCommercialStatuses();
      addDecisionButtons();
    }
    return result;
  };

  window.decideQuote = decideQuote;
  window.setQuoteCommercialStatus = setCommercialStatus;
})();

(() => {
  if (typeof document === 'undefined' || !document.body || typeof document.createElement !== 'function') return;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  function injectSidebarLayout() {
    if (!document.head || $('#mm-sidebar-layout-fix')) return;
    const style = document.createElement('style');
    style.id = 'mm-sidebar-layout-fix';
    style.textContent = `
      @media (min-width:761px){
        #admin-app .sidebar{height:100vh;max-height:100vh;overflow:hidden;display:flex;flex-direction:column}
        #admin-app .side-brand{flex:0 0 auto}
        #admin-app #admin-nav{flex:1 1 auto;min-height:0;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;padding-right:4px;scrollbar-width:thin;scrollbar-color:#b5cfc1 transparent}
        #admin-app #admin-nav::-webkit-scrollbar{width:6px}
        #admin-app #admin-nav::-webkit-scrollbar-track{background:transparent}
        #admin-app #admin-nav::-webkit-scrollbar-thumb{background:#b5cfc1;border-radius:999px}
        #admin-app .side-bottom{flex:0 0 auto;margin-top:8px;padding-top:8px;padding-bottom:max(10px,env(safe-area-inset-bottom))}
      }
      @media (min-width:761px) and (max-height:900px){
        #admin-app .sidebar{padding-top:10px;padding-bottom:8px}
        #admin-app .side-brand{padding-top:4px;padding-bottom:6px;margin-bottom:4px}
        #admin-app #admin-nav .nav{min-height:34px;padding-top:7px;padding-bottom:7px;margin-top:1px;margin-bottom:1px}
        #admin-app .side-plan-card{display:none!important}
        #admin-app .side-bottom{padding-top:5px}
        #admin-app .logout{padding-top:8px;padding-bottom:8px}
      }
    `;
    document.head.appendChild(style);
  }

  function accountData() {
    let user = null;
    try {
      if (typeof state !== 'undefined' && state?.user) user = state.user;
    } catch (_) {
      user = null;
    }
    return {
      name: user?.name || $('#user-badge')?.textContent?.trim() || 'Administrador',
      email: user?.email || '',
    };
  }

  function escapeText(value = '') {
    return String(value).replace(/[&<>'"]/g, character => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
    })[character]);
  }

  function renderSettings() {
    const section = $('#account-settings');
    if (!section) return;
    const user = accountData();
    section.innerHTML = `
      <div class="panel">
        <div class="panel-title">
          <div><span class="eyebrow">Configurações</span><h2>Conta e acesso</h2></div>
        </div>
        <p class="muted">Gerencie sua sessão e troque de conta com segurança.</p>
        <div class="panel" style="margin-top:16px">
          <strong>${escapeText(user.name)}</strong>
          <p class="muted">${escapeText(user.email || 'Administrador da marcenaria')}</p>
        </div>
        <div class="toolbar-actions" style="margin-top:18px;display:flex;gap:10px;flex-wrap:wrap">
          <button id="settings-relogin" class="btn primary" type="button">↻ Sair e entrar novamente</button>
          <button id="settings-logout" class="btn secondary" type="button">↪ Sair da conta</button>
          <button id="settings-dashboard" class="btn secondary" type="button">⌂ Voltar ao Dashboard</button>
        </div>
      </div>`;
    $('#settings-relogin')?.addEventListener('click', () => endSession(true));
    $('#settings-logout')?.addEventListener('click', () => endSession(false));
    $('#settings-dashboard')?.addEventListener('click', () => {
      if (typeof showSection === 'function') showSection('dashboard');
    });
  }

  function showAccountSettings() {
    const section = $('#account-settings');
    if (!section) return;
    $$('.admin-section').forEach(item => item.classList.add('hidden'));
    section.classList.remove('hidden');
    $$('#admin-nav .nav').forEach(button => button.classList.remove('active'));
    $('#account-settings-nav')?.classList.add('active');
    const title = $('#admin-title');
    if (title) title.textContent = 'Configurações';
    renderSettings();
  }

  function endSession(reopenLogin) {
    if (reopenLogin) sessionStorage.setItem('mm-direct-relogin', '1');
    else sessionStorage.removeItem('mm-direct-relogin');

    if (typeof logout === 'function') {
      logout();
      return;
    }
    location.reload();
  }

  function injectFixedControls() {
    const nav = $('#admin-nav');
    const adminMain = $('.admin-main');
    const sideBottom = $('.side-bottom');
    if (!nav || !adminMain || !sideBottom) return;

    injectSidebarLayout();

    if (!$('#account-settings')) {
      const section = document.createElement('section');
      section.id = 'account-settings';
      section.className = 'admin-section hidden';
      adminMain.appendChild(section);
    }

    if (!$('#account-settings-nav')) {
      const settingsButton = document.createElement('button');
      settingsButton.id = 'account-settings-nav';
      settingsButton.className = 'nav';
      settingsButton.type = 'button';
      settingsButton.innerHTML = '<span class="nav-icon" aria-hidden="true">⚙</span><span class="nav-label">Configurações</span>';
      settingsButton.addEventListener('click', showAccountSettings);
      nav.appendChild(settingsButton);
    }

    if (!$('#direct-relogin')) {
      const reloginButton = document.createElement('button');
      reloginButton.id = 'direct-relogin';
      reloginButton.className = 'logout';
      reloginButton.type = 'button';
      reloginButton.innerHTML = '↻ <span>Sair e entrar novamente</span>';
      reloginButton.addEventListener('click', () => endSession(true));
      const logoutButton = $('#logout');
      sideBottom.insertBefore(reloginButton, logoutButton || null);
    }
  }

  injectFixedControls();

  if (sessionStorage.getItem('mm-direct-relogin') === '1') {
    sessionStorage.removeItem('mm-direct-relogin');
    setTimeout(() => {
      if (typeof openAuth === 'function') openAuth('login');
    }, 180);
  }
})();