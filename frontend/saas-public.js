(() => {
  const apiBase = window.API_BASE_URL || (location.hostname === 'localhost' ? 'http://localhost:8000/api/v1' : 'https://ideal-marcenaria-api.onrender.com/api/v1');
  const $ = (s, root = document) => root.querySelector(s);
  let selectedPlan = 'starter';
  let billingRefreshInFlight = false;

  const planNames = {
    starter: 'Essencial',
    professional: 'Profissional',
    business: 'Empresa',
  };

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
    return labels[subscription.status] || subscription.status || 'Em processamento';
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
      window.location.assign(data.checkout_url);
    } catch (error) {
      const message = $('#billing-message');
      if (message) {
        message.className = 'form-message error';
        message.textContent = error.message;
      }
      if (button) {
        button.disabled = false;
        button.textContent = previous;
      }
    }
  }

  async function refreshBillingPanel() {
    const panel = $('#saas-billing-panel');
    if (!panel || billingRefreshInFlight || typeof window.api !== 'function') return;
    billingRefreshInFlight = true;
    try {
      const data = await billingApi('/billing/subscription');
      const subscription = data?.subscription || null;
      const planCode = data?.plan_code || subscription?.plan_code || 'starter';
      const planName = planNames[planCode] || planCode;
      const period = subscription?.current_period_end
        ? new Date(subscription.current_period_end).toLocaleDateString('pt-BR')
        : '—';
      const status = billingStatusLabel(subscription);
      const usage = data?.usage || {};
      const usageRows = Object.entries(usage)
        .filter(([, value]) => value && typeof value === 'object' && 'used' in value)
        .slice(0, 4)
        .map(([key, value]) => `<span>${key}: <strong>${value.used}${value.limit == null ? '' : ` / ${value.limit}`}</strong></span>`)
        .join('');

      panel.innerHTML = `
        <div class="panel-title">
          <div><span class="eyebrow">Assinatura SaaS</span><h3>Plano ${planName}</h3></div>
          <span class="badge success">${status}</span>
        </div>
        <p>Próxima renovação/período: <strong>${period}</strong></p>
        <div class="trust">${usageRows || '<span>Uso mensal disponível no seu plano.</span>'}</div>
        <div class="toolbar-actions" style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn secondary" type="button" data-billing-plan="starter">Essencial · R$ 149/mês</button>
          <button class="btn primary" type="button" data-billing-plan="professional">Profissional · R$ 299/mês</button>
          <button class="btn secondary" type="button" data-billing-plan="business">Empresa · R$ 599/mês</button>
        </div>
        <div id="billing-message" class="form-message" role="status" aria-live="polite"></div>`;

      panel.querySelectorAll('[data-billing-plan]').forEach((button) => {
        button.addEventListener('click', () => startCheckout(button.dataset.billingPlan, button));
      });
    } catch (error) {
      panel.innerHTML = `<div class="panel-title"><div><span class="eyebrow">Assinatura SaaS</span><h3>Planos e cobrança</h3></div></div><p>${error.message}</p>`;
    } finally {
      billingRefreshInFlight = false;
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

  function handleBillingReturn() {
    const params = new URLSearchParams(location.search);
    const result = params.get('billing');
    if (!result) return;
    const notice = document.createElement('div');
    notice.className = `billing-return ${result === 'success' ? 'success' : ''}`;
    notice.setAttribute('role', 'status');
    notice.textContent = result === 'success'
      ? 'Pagamento concluído. Entre na plataforma para confirmar sua assinatura.'
      : 'Pagamento não concluído. Você pode tentar novamente quando quiser.';
    Object.assign(notice.style, {
      position: 'fixed', top: '16px', left: '50%', transform: 'translateX(-50%)', zIndex: '9999',
      maxWidth: 'min(92vw, 680px)', padding: '14px 18px', borderRadius: '14px',
      background: result === 'success' ? '#0f3d2e' : '#332814', color: '#fff', boxShadow: '0 14px 36px rgba(0,0,0,.28)'
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
    const observer = new MutationObserver(() => queueMicrotask(injectBillingPanel));
    if (admin) observer.observe(admin, { attributes: true, attributeFilter: ['class'] });
    if (dashboard) observer.observe(dashboard, { childList: true });
  });
})();
