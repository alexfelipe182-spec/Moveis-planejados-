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
  const escapeHtml = (value = '') => String(value).replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
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
    message.textContent = 'Criando sua marcenaria...';

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
      message.textContent = 'Marcenaria criada com sucesso. Entre com seu e-mail para acessar o painel.';
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
    if (!subscription) return 'Sem assinatura ativa';
    const labels = {
      active: 'Ativa',
      trialing: 'Período de teste',
      past_due: 'Pagamento pendente',
      unpaid: 'Pagamento não concluído',
      canceled: 'Cancelada',
      incomplete: 'Aguardando pagamento',
      incomplete_expired: 'Expirada',
    };
    return labels[subscription.status] || 'Em processamento';
  }

  function billingStatusTone(subscription) {
    if (!subscription) return '';
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
      button.textContent = 'Abrindo pagamento...';
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

  async function refreshBillingPanel() {
    if (!$('#saas-billing-panel') || typeof window.api !== 'function') return;
    try {
      const data = await loadBillingData();
      const panel = $('#saas-billing-panel');
      if (!panel) return;
      const subscription = data?.subscription || null;
      const planCode = data?.plan_code || subscription?.plan_code || 'starter';
      const planName = planNames[planCode] || planNames.starter;
      const period = subscription?.current_period_end
        ? new Date(subscription.current_period_end).toLocaleDateString('pt-BR')
        : '—';
      const status = billingStatusLabel(subscription);
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
      const hasActiveSubscription = ['active', 'trialing'].includes(subscription?.status);
      const actions = data?.can_manage_billing
        ? '<button class="btn primary" type="button" data-billing-portal>Gerenciar assinatura</button>'
        : hasActiveSubscription
          ? '<span class="muted">Assinatura administrada pela plataforma.</span>'
          : `<button class="btn secondary" type="button" data-billing-plan="starter">Essencial · R$ 149/mês</button>
             <button class="btn primary" type="button" data-billing-plan="professional">Profissional · R$ 299/mês</button>
             <button class="btn secondary" type="button" data-billing-plan="business">Empresa · R$ 599/mês</button>`;

      panel.innerHTML = `
        <div class="panel-title">
          <div><span class="eyebrow">Assinatura SaaS</span><h3>Plano ${escapeHtml(planName)}</h3></div>
          <span class="badge ${billingStatusTone(subscription)}">${escapeHtml(status)}</span>
        </div>
        <p>Próxima renovação/período: <strong>${escapeHtml(period)}</strong></p>
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
      success: 'Pagamento concluído. Entre na plataforma para confirmar sua assinatura.',
      cancelled: 'Pagamento não concluído. Você pode tentar novamente quando quiser.',
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
