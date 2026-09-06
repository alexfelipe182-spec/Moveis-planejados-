(() => {
  const apiBase = window.API_BASE_URL || (location.hostname === 'localhost' ? 'http://localhost:8000/api/v1' : 'https://ideal-marcenaria-api.onrender.com/api/v1');
  const $ = (s, root = document) => root.querySelector(s);
  let selectedPlan = 'starter';
  let billingRequestPromise = null;
  let billingRenderQueued = false;

  const planNames = {
    starter: 'Essencial',
    professional: 'Profissional',
    business: 'Empresa',
  };
  const usageNames = {
    users: 'Usuários',
    customers: 'Clientes',
    projects: 'Projetos',
    quotes_month: 'Orçamentos no mês',
    ai_month: 'Análises com IA no mês',
  };
  const stripeOrigins = new Set(['https://checkout.stripe.com', 'https://billing.stripe.com']);
  const escapeHtml = (value = '') => String(value).replace(/[&<>'\"]/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '\"': '&quot;',
  })[character]);

  function showRegister(plan = 'starter') {
    selectedPlan = plan;
    const overlay = $('#auth-overlay');
    overlay?.classList.remove('hidden');
    overlay?.setAttribute('aria-hidden', 'false');
    ['login', 'register', 'recovery', 'reset'].forEach((view) => {
      $(`#${view}-view`)?.classList.toggle('hidden', view !== 'register');
    });
    const planInput = $('#register-plan');
    if (planInput) planInput.value = plan;
    $('#register-business-name')?.focus();
  }

  async function registerBusiness(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
    const form = event.currentTarget;
    const message = $('#register-message');
    if (!form || !message) return;

    message.className = 'form-message';
    message.textContent = 'Criando sua marcenaria e ativando 30 dias grátis...';

    const payload = {
      business_name: $('#register-business-name')?.value.trim(),
      owner_name: $('#register-name')?.value.trim(),
      email: $('#register-email')?.value.trim().toLowerCase(),
      password: $('#register-password')?.value,
      plan_code: $('#register-plan')?.value || selectedPlan || 'starter',
    };

    try {
      const response = await fetch(`${apiBase}/auth/register-business`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Erro ${response.status}`);
      message.classList.add('success');
      message.textContent = 'Marcenaria criada. Seus 30 dias grátis estão ativos — entre para começar a usar a plataforma.';
      form.reset();
      setTimeout(() => {
        $('#login-email').value = payload.email;
        ['login', 'register', 'recovery', 'reset'].forEach((view) => {
          $(`#${view}-view`)?.classList.toggle('hidden', view !== 'login');
        });
        $('#login-password')?.focus();
      }, 900);
    } catch (error) {
      message.classList.add('error');
      message.textContent = error.message;
    }
  }

  function billingApi(path, options = {}) {
    if (typeof window.api === 'function') return window.api(path, options);
    throw new Error('Sessão administrativa indisponível. Entre novamente.');
  }

  function billingStatusLabel(subscription) {
    if (!subscription) return 'Plano necessário';
    const labels = {
      active: 'Ativa',
      trialing: 'Teste grátis ativo',
      trial_expired: 'Teste grátis encerrado',
      past_due: 'Pagamento pendente',
      unpaid: 'Pagamento não concluído',
      canceled: 'Cancelada',
      incomplete: 'Aguardando pagamento',
      incomplete_expired: 'Expirada',
    };
    return labels[subscription.status] || 'Em processamento';
  }

  function billingStatusTone(subscription) {
    if (!subscription) return 'warning';
    if (['active', 'trialing'].includes(subscription.status)) return 'success';
    if (['past_due', 'incomplete'].includes(subscription.status)) return 'warning';
    return 'danger';
  }

  function errorMessage(error) {
    return typeof error?.message === 'string' && error.message !== '[object Object]'
      ? error.message
      : 'Não foi possível concluir a operação de cobrança.';
  }

  function redirectToStripe(value) {
    let destination;
    try {
      destination = new URL(value);
    } catch (_) {
      throw new Error('O provedor de pagamento retornou um endereço inválido.');
    }
    if (!stripeOrigins.has(destination.origin)) {
      throw new Error('O provedor de pagamento retornou um endereço não permitido.');
    }
    window.location.assign(destination.href);
  }

  async function startCheckout(planCode, button) {
    if (!planNames[planCode]) return;
    const previous = button?.textContent;
    if (button) {
      button.disabled = true;
      button.textContent = 'Abrindo assinatura...';
    }
    try {
      const data = await billingApi('/billing/checkout', {
        method: 'POST',
        body: { plan_code: planCode },
      });
      if (!data?.checkout_url) throw new Error('O provedor de pagamento não retornou o checkout.');
      redirectToStripe(data.checkout_url);
    } catch (error) {
      const message = $('#billing-message');
      if (message) {
        message.className = 'form-message error';
        message.textContent = errorMessage(error);
      }
      if (button) {
        button.disabled = false;
        button.textContent = previous;
      }
    }
  }

  async function openBillingPortal(button) {
    const previous = button?.textContent;
    if (button) {
      button.disabled = true;
      button.textContent = 'Abrindo portal...';
    }
    try {
      const data = await billingApi('/billing/portal', { method: 'POST' });
      if (!data?.portal_url) throw new Error('O provedor não retornou o portal de cobrança.');
      redirectToStripe(data.portal_url);
    } catch (error) {
      const message = $('#billing-message');
      if (message) {
        message.className = 'form-message error';
        message.textContent = errorMessage(error);
      }
      if (button) {
        button.disabled = false;
        button.textContent = previous;
      }
    }
  }

  function loadBillingData() {
    if (!billingRequestPromise) {
      billingRequestPromise = billingApi('/billing/subscription')
        .finally(() => { billingRequestPromise = null; });
    }
    return billingRequestPromise;
  }

  function planButtons() {
    return `<button class="btn secondary" type="button" data-billing-plan="starter">Essencial · R$ 149/mês</button>
      <button class="btn primary" type="button" data-billing-plan="professional">Profissional · R$ 299/mês</button>
      <button class="btn secondary" type="button" data-billing-plan="business">Empresa · R$ 599/mês</button>`;
  }

  async function refreshBillingPanel() {
    if (!$('#saas-billing-panel') || typeof window.api !== 'function') return;
    try {
      const data = await loadBillingData();
      const panel = $('#saas-billing-panel');
      if (!panel) return;
      const subscription = data?.subscription || null;
      const planCode = data?.plan_code || subscription?.plan_code || 'starter';
      const planName = planNames[planCode] || planNames.starter;
      const status = billingStatusLabel(subscription);
      const trialDays = Number(data?.trial_days_remaining || subscription?.trial_days_remaining || 0);
      const isTrial = subscription?.status === 'trialing';
      const isTrialExpired = subscription?.status === 'trial_expired';
      const periodSource = (isTrial || isTrialExpired) ? subscription?.trial_end : subscription?.current_period_end;
      const period = periodSource ? new Date(periodSource).toLocaleDateString('pt-BR') : '—';
      const periodLabel = (isTrial || isTrialExpired) ? 'Teste grátis até' : 'Próxima renovação/período';
      const usage = data?.usage?.usage || {};
      const limits = data?.usage?.limits || {};
      const usageRows = Object.entries(usage)
        .filter(([key, value]) => usageNames[key] && Number.isFinite(Number(value)))
        .map(([key, value]) => {
          const limit = limits[key];
          const limitLabel = limit == null ? 'Ilimitado' : Number(limit).toLocaleString('pt-BR');
          return `<span>${usageNames[key]}: <strong>${Number(value).toLocaleString('pt-BR')} / ${limitLabel}</strong></span>`;
        })
        .join('');

      let trialMessage = '';
      if (isTrial) {
        trialMessage = `<p><strong>${trialDays} ${trialDays === 1 ? 'dia restante' : 'dias restantes'}</strong> no seu teste grátis de 30 dias. Você pode escolher um plano agora e a cobrança começa após o período gratuito.</p>`;
      } else if (isTrialExpired) {
        trialMessage = '<p><strong>Seu período gratuito terminou.</strong> Escolha um plano para continuar usando os recursos da plataforma.</p>';
      }

      let actions;
      if (data?.can_manage_billing) {
        actions = '<button class="btn primary" type="button" data-billing-portal>Gerenciar assinatura</button>';
      } else if (subscription?.status === 'active') {
        actions = '<span class="muted">Assinatura administrada pela plataforma.</span>';
      } else {
        actions = planButtons();
      }

      panel.innerHTML = `
        <div class="panel-title">
          <div><span class="eyebrow">Assinatura SaaS</span><h3>Plano ${escapeHtml(planName)}</h3></div>
          <span class="badge ${billingStatusTone(subscription)}">${escapeHtml(status)}</span>
        </div>
        ${trialMessage}
        <p>${escapeHtml(periodLabel)}: <strong>${escapeHtml(period)}</strong></p>
        <div class="trust">${usageRows || '<span>Uso mensal disponível no seu plano.</span>'}</div>
        <div class="toolbar-actions" style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap">
          ${actions}
        </div>
        <div id="billing-message" class="form-message" role="status" aria-live="polite"></div>`;

      panel.querySelectorAll('[data-billing-plan]').forEach((button) => {
        button.addEventListener('click', () => startCheckout(button.dataset.billingPlan, button));
      });
      panel.querySelector('[data-billing-portal]')?.addEventListener('click', (event) => {
        openBillingPortal(event.currentTarget);
      });
    } catch (error) {
      const panel = $('#saas-billing-panel');
      if (panel) {
        panel.innerHTML = `<div class="panel-title"><div><span class="eyebrow">Assinatura SaaS</span><h3>Planos e cobrança</h3></div></div><p>${escapeHtml(errorMessage(error))}</p>`;
      }
    }
  }

  function injectBillingPanel() {
    const admin = $('#admin-app');
    const dashboard = $('#dashboard');
    if (!admin || admin.classList.contains('hidden') || !dashboard) return;
    if (!$('#saas-billing-panel', dashboard)) {
      const panel = document.createElement('div');
      panel.id = 'saas-billing-panel';
      panel.className = 'panel';
      panel.innerHTML = '<div class="panel loading">Carregando assinatura...</div>';
      dashboard.appendChild(panel);
    }
    refreshBillingPanel();
  }

  function scheduleBillingPanel() {
    if (billingRenderQueued) return;
    billingRenderQueued = true;
    queueMicrotask(() => {
      billingRenderQueued = false;
      injectBillingPanel();
    });
  }

  function handleBillingReturn() {
    const params = new URLSearchParams(location.search);
    const result = params.get('billing');
    const messages = {
      success: 'Assinatura configurada. Seu período grátis continua até a data mostrada no painel.',
      cancelled: 'Assinatura não concluída. Seu teste grátis continua normalmente enquanto estiver dentro dos 30 dias.',
      portal: 'Configurações de cobrança atualizadas.',
    };
    if (!messages[result]) return;
    const notice = document.createElement('div');
    notice.className = `billing-return ${result === 'cancelled' ? '' : 'success'}`;
    notice.setAttribute('role', 'status');
    notice.textContent = messages[result];
    Object.assign(notice.style, {
      position: 'fixed', top: '16px', left: '50%', transform: 'translateX(-50%)', zIndex: '9999',
      maxWidth: 'min(92vw, 680px)', padding: '14px 18px', borderRadius: '14px',
      background: result === 'cancelled' ? '#332814' : '#0f3d2e', color: '#fff', boxShadow: '0 14px 36px rgba(0,0,0,.28)'
    });
    document.body.appendChild(notice);
    history.replaceState({}, '', location.pathname + location.hash);
    setTimeout(() => notice.remove(), 8000);
  }

  document.addEventListener('DOMContentLoaded', () => {
    const form = $('#register-form');
    form?.addEventListener('submit', registerBusiness, true);

    document.querySelectorAll('[data-plan]').forEach((button) => {
      button.addEventListener('click', () => showRegister(button.dataset.plan || 'starter'));
    });

    const showRegisterButton = $('#show-register');
    showRegisterButton?.addEventListener('click', () => {
      selectedPlan = 'starter';
      const planInput = $('#register-plan');
      if (planInput) planInput.value = 'starter';
    });

    handleBillingReturn();
    injectBillingPanel();

    const admin = $('#admin-app');
    const dashboard = $('#dashboard');
    const observer = new MutationObserver(scheduleBillingPanel);
    if (admin) observer.observe(admin, { attributes: true, attributeFilter: ['class'] });
    if (dashboard) observer.observe(dashboard, { childList: true });
  });
})();

(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  function ensureSidebarStyle() {
    if ($('#mm-account-sidebar-style')) return;
    const style = document.createElement('style');
    style.id = 'mm-account-sidebar-style';
    style.textContent = `
      @media (min-width:761px){
        #admin-app .sidebar{height:100vh;max-height:100vh;display:flex;flex-direction:column;overflow:hidden}
        #admin-app .side-brand{flex:0 0 auto}
        #admin-app #admin-nav{flex:1 1 auto;min-height:0;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;padding-right:4px;scrollbar-width:thin}
        #admin-app .side-bottom{flex:0 0 auto;display:grid;gap:6px;margin-top:6px;padding-top:7px;padding-bottom:max(8px,env(safe-area-inset-bottom));background:inherit;z-index:4}
        #admin-app .side-bottom .logout{display:flex!important;width:100%;min-height:38px;align-items:center;gap:8px;justify-content:flex-start}
        #admin-app .side-plan-card{display:none!important}
      }
      @media (min-width:761px) and (max-height:900px){
        #admin-app .sidebar{padding-top:8px;padding-bottom:6px}
        #admin-app .side-brand{padding-top:3px;padding-bottom:5px;margin-bottom:3px}
        #admin-app #admin-nav .nav{min-height:32px;padding-top:6px;padding-bottom:6px;margin-top:1px;margin-bottom:1px}
        #admin-app .side-bottom>a{display:none!important}
        #admin-app .side-bottom .logout{min-height:34px;padding-top:6px;padding-bottom:6px}
      }
      @media (max-width:760px){
        #admin-app .side-bottom{display:flex;gap:4px;max-width:48vw;overflow-x:auto;scrollbar-width:none}
        #admin-app .side-bottom::-webkit-scrollbar{display:none}
        #admin-app .side-bottom .logout{flex:0 0 auto;min-width:42px;padding:9px 10px}
        #admin-app .side-bottom .logout span{display:none}
      }
    `;
    document.head.appendChild(style);
  }

  function accountName() {
    return $('#user-badge')?.textContent?.trim() || 'Administrador';
  }

  function ensureSettingsSection() {
    let section = $('#account-settings');
    if (section) return section;
    const main = $('.admin-main');
    if (!main) return null;
    section = document.createElement('section');
    section.id = 'account-settings';
    section.className = 'admin-section hidden';
    main.appendChild(section);
    return section;
  }

  function renderSettings() {
    const section = ensureSettingsSection();
    if (!section) return;
    section.innerHTML = `
      <div class="panel">
        <div class="panel-title"><div><span class="eyebrow">Configurações</span><h2>Conta e acesso</h2></div></div>
        <p class="muted">Gerencie sua sessão e troque de conta com segurança.</p>
        <div class="panel" style="margin-top:16px"><strong>${accountName()}</strong><p class="muted">Administrador da marcenaria</p></div>
        <div class="toolbar-actions" style="margin-top:18px;display:flex;gap:10px;flex-wrap:wrap">
          <button id="settings-relogin" class="btn primary" type="button">↻ Sair e entrar novamente</button>
          <button id="settings-logout" class="btn secondary" type="button">↪ Sair da conta</button>
          <button id="settings-dashboard" class="btn secondary" type="button">⌂ Voltar ao Dashboard</button>
        </div>
      </div>`;
    $('#settings-relogin')?.addEventListener('click', relogin);
    $('#settings-logout')?.addEventListener('click', () => window.logout?.());
    $('#settings-dashboard')?.addEventListener('click', () => window.showSection?.('dashboard'));
  }

  function showSettings() {
    const section = ensureSettingsSection();
    if (!section) return;
    $$('.admin-section').forEach((item) => item.classList.add('hidden'));
    section.classList.remove('hidden');
    $$('#admin-nav .nav').forEach((button) => button.classList.remove('active'));
    const title = $('#admin-title');
    if (title) title.textContent = 'Configurações';
    renderSettings();
  }

  function relogin() {
    sessionStorage.setItem('mm-relogin', '1');
    if (typeof window.logout === 'function') window.logout();
    else location.reload();
  }

  function ensureControls() {
    ensureSidebarStyle();
    ensureSettingsSection();
    const bottom = $('.side-bottom');
    const logoutButton = $('#logout');
    if (!bottom || !logoutButton) return;

    let settingsButton = $('#account-settings-nav');
    if (!settingsButton) {
      settingsButton = document.createElement('button');
      settingsButton.id = 'account-settings-nav';
      settingsButton.type = 'button';
      settingsButton.innerHTML = '⚙ <span>Configurações</span>';
    }
    settingsButton.className = 'logout account-control';
    settingsButton.removeAttribute('data-section');
    bottom.insertBefore(settingsButton, logoutButton);
    if (!settingsButton.dataset.mmBound) {
      settingsButton.addEventListener('click', showSettings);
      settingsButton.dataset.mmBound = 'true';
    }

    let reloginButton = $('#direct-relogin');
    if (!reloginButton) {
      reloginButton = document.createElement('button');
      reloginButton.id = 'direct-relogin';
      reloginButton.type = 'button';
      reloginButton.innerHTML = '↻ <span>Sair e entrar novamente</span>';
    }
    reloginButton.className = 'logout account-control';
    bottom.insertBefore(reloginButton, logoutButton);
    if (!reloginButton.dataset.mmBound) {
      reloginButton.addEventListener('click', relogin);
      reloginButton.dataset.mmBound = 'true';
    }

    logoutButton.style.display = '';
    const pill = $('.user-pill');
    if (pill && !pill.dataset.mmBound) {
      pill.setAttribute('role', 'button');
      pill.setAttribute('tabindex', '0');
      pill.addEventListener('click', showSettings);
      pill.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          showSettings();
        }
      });
      pill.dataset.mmBound = 'true';
    }
  }

  function initAccountControls() {
    ensureControls();
    const admin = $('#admin-app');
    if (admin) {
      new MutationObserver(ensureControls).observe(admin, { attributes: true, attributeFilter: ['class'] });
    }
    if (sessionStorage.getItem('mm-relogin') === '1') {
      sessionStorage.removeItem('mm-relogin');
      setTimeout(() => window.openAuth?.('login'), 180);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initAccountControls);
  else initAccountControls();
})();
