(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  function installStyles() {
    if ($('#mm-account-menu-style')) return;
    const style = document.createElement('style');
    style.id = 'mm-account-menu-style';
    style.textContent = `
      #admin-app .top-actions{position:relative}
      #admin-app .user-pill{cursor:pointer;user-select:none}
      #admin-app #logout{display:none!important}
      #admin-app #account-settings-nav,
      #admin-app #direct-relogin{display:none!important}

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

      #mm-account-menu{position:absolute;right:0;top:calc(100% + 10px);width:min(290px,calc(100vw - 24px));padding:10px;background:#fff;border:1px solid rgba(13,89,61,.16);border-radius:16px;box-shadow:0 18px 50px rgba(9,54,38,.18);display:none;z-index:1000}
      #mm-account-menu.open{display:grid;gap:6px}
      #mm-account-menu .mm-account-head{padding:8px 10px 10px;border-bottom:1px solid rgba(13,89,61,.10);margin-bottom:2px}
      #mm-account-menu .mm-account-head strong{display:block;color:#102119;font-size:14px}
      #mm-account-menu .mm-account-head small{display:block;color:#617168;margin-top:2px}
      #mm-account-menu button{width:100%;border:0;background:transparent;border-radius:10px;padding:10px 12px;text-align:left;color:#102119;font:inherit;font-weight:700;cursor:pointer}
      #mm-account-menu button:hover,#mm-account-menu button:focus-visible{background:#eef8f2;outline:none}
      #mm-account-menu button[data-danger="true"]{color:#9b2c2c}

      #admin-app .smart-result-card strong,
      #admin-app .smart-quote-grid strong{
        color:#111827!important;
        opacity:1!important;
        font-weight:800!important;
        text-shadow:none!important;
      }
      #admin-app .smart-result-card small,
      #admin-app .smart-quote-grid small{
        color:#374151!important;
        opacity:1!important;
        font-weight:700;
      }
      #admin-app .smart-result-badges{display:flex;align-items:center;justify-content:flex-end;gap:8px;flex-wrap:wrap}
      #admin-app .smart-result-badges .badge:first-child{background:#eaf7ef;border-color:#b9dec7;color:#125c36;font-weight:800}
      #admin-app .smart-quote-create .btn[aria-busy="true"]{cursor:progress;opacity:.72;pointer-events:none}
      #admin-app .smart-quote-create .btn:disabled{cursor:not-allowed;filter:saturate(.72)}
      #admin-app .smart-quote-result .empty{border-style:dashed;background:#fbfcfb}
      #admin-app .smart-quote-result .empty strong{display:block;color:#111827;margin-bottom:5px}
      #admin-app .smart-quote-result .empty p{margin:0;color:#4b5563}

      #admin-app .integration-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:14px}
      #admin-app .integration-card{border:1px solid rgba(13,89,61,.14);background:#fbfdfb;border-radius:14px;padding:14px;min-width:0}
      #admin-app .integration-card-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:7px}
      #admin-app .integration-card-head strong{color:#111827;font-size:14px}
      #admin-app .integration-card p{margin:0;color:#5b685f;font-size:13px;line-height:1.45}
      #admin-app .integration-state{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:5px 8px;font-size:11px;font-weight:800;white-space:nowrap}
      #admin-app .integration-state::before{content:'';width:7px;height:7px;border-radius:50%;background:currentColor;box-shadow:0 0 0 3px currentColor inset;opacity:.9}
      #admin-app .integration-state.ready{background:#eaf7ef;color:#12623a}
      #admin-app .integration-state.partial{background:#fff6df;color:#8b5b00}
      #admin-app .integration-state.missing{background:#fff0f0;color:#9b2c2c}
      #admin-app .integration-loading{margin-top:14px;padding:14px;border-radius:14px;background:#f6f8f7;color:#536158}

      body.dark #admin-app .smart-result-card strong,
      body.dark #admin-app .smart-quote-grid strong,
      body.dark #admin-app .smart-quote-result .empty strong,
      body.dark #admin-app .integration-card-head strong{
        color:#f8fafc!important;
      }
      body.dark #admin-app .smart-result-card small,
      body.dark #admin-app .smart-quote-grid small{
        color:#d1d5db!important;
      }
      body.dark #admin-app .smart-result-badges .badge:first-child{background:#153f2b;border-color:#2d6849;color:#d9fbe7}
      body.dark #admin-app .smart-quote-result .empty p{color:#d1d5db}
      body.dark #admin-app .integration-card{background:#132019;border-color:#284033}
      body.dark #admin-app .integration-card p{color:#c7d1ca}
      body.dark #admin-app .integration-loading{background:#132019;color:#c7d1ca}

      @media(max-width:900px){#admin-app .integration-grid{grid-template-columns:1fr}}
      @media(max-width:760px){
        #mm-account-menu{position:fixed;right:12px;top:72px;width:min(320px,calc(100vw - 24px))}
        #admin-app .smart-result-badges{justify-content:flex-start;width:100%}
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

  function stateBadge(label, state) {
    return `<span class="integration-state ${state}">${label}</span>`;
  }

  async function renderIntegrationStatus() {
    const target = $('#settings-integrations');
    if (!target || typeof window.api !== 'function') return;
    try {
      const data = await window.api('/admin/integrations');
      if (!target.isConnected) return;
      const openaiReady = Boolean(data?.openai?.configured);
      const emailReady = Boolean(data?.email?.configured);
      const stripeReady = Boolean(data?.stripe?.fully_configured);
      const stripePartial = Boolean(data?.stripe?.checkout_ready || data?.stripe?.secret_configured || data?.stripe?.webhook_configured);
      const stripeState = stripeReady ? 'ready' : stripePartial ? 'partial' : 'missing';
      const stripeLabel = stripeReady ? 'Completo' : stripePartial ? 'Parcial' : 'Pendente';
      const prices = data?.stripe?.prices_configured || {};
      const readyPlans = Object.entries(prices).filter(([, ready]) => ready).map(([plan]) => ({ starter:'Essencial', professional:'Profissional', business:'Empresa' }[plan] || plan));
      target.innerHTML = `
        <div class="integration-grid">
          <div class="integration-card">
            <div class="integration-card-head"><strong>Inteligência Artificial</strong>${stateBadge(openaiReady ? 'Configurada' : 'Modo assistido', openaiReady ? 'ready' : 'partial')}</div>
            <p>${openaiReady ? `OpenAI ativa com ${String(data.openai.model || 'modelo configurado').replace(/[&<>'\"]/g, '')}.` : 'A plataforma continua funcionando em modo assistido local, sem inventar preços.'}</p>
          </div>
          <div class="integration-card">
            <div class="integration-card-head"><strong>E-mail de recuperação</strong>${stateBadge(emailReady ? 'Configurado' : 'Pendente', emailReady ? 'ready' : 'missing')}</div>
            <p>${emailReady ? 'SMTP configurado para envio de links de recuperação.' : 'Configure o SMTP de produção para entregar links de redefinição de senha.'}</p>
          </div>
          <div class="integration-card">
            <div class="integration-card-head"><strong>Stripe</strong>${stateBadge(stripeLabel, stripeState)}</div>
            <p>${stripeReady ? 'Checkout, portal, webhook e preços dos três planos configurados.' : readyPlans.length ? `Preços configurados: ${readyPlans.join(', ')}. Ainda há itens pendentes para a cobrança completa.` : 'Configuração de cobrança ainda não está completa.'}</p>
          </div>
        </div>`;
    } catch (error) {
      if (!target.isConnected) return;
      target.innerHTML = `<div class="integration-loading">Não foi possível consultar o diagnóstico das integrações agora: ${String(error?.message || 'erro desconhecido').replace(/[&<>'\"]/g, '')}</div>`;
    }
  }

  function renderSettings() {
    const section = ensureSettingsSection();
    if (!section) return;
    section.innerHTML = `
      <div class="panel">
        <div class="panel-title"><div><span class="eyebrow">Configurações</span><h2>Conta e integrações</h2></div></div>
        <p class="muted">Gerencie sua sessão e acompanhe a prontidão das integrações de produção.</p>
        <div class="panel" style="margin-top:16px"><strong>${accountName().replace(/[&<>'\"]/g, '')}</strong><p class="muted">Administrador da marcenaria</p></div>
        <div id="settings-integrations" class="integration-loading" aria-live="polite">Verificando OpenAI, e-mail e Stripe...</div>
        <div class="toolbar-actions" style="margin-top:18px;display:flex;gap:10px;flex-wrap:wrap">
          <button id="settings-relogin" class="btn primary" type="button">↻ Sair e entrar novamente</button>
          <button id="settings-logout" class="btn secondary" type="button">↪ Sair da conta</button>
          <button id="settings-dashboard" class="btn secondary" type="button">⌂ Voltar ao Dashboard</button>
        </div>
      </div>`;
    $('#settings-relogin')?.addEventListener('click', () => performLogout(true));
    $('#settings-logout')?.addEventListener('click', () => performLogout(false));
    $('#settings-dashboard')?.addEventListener('click', () => window.showSection?.('dashboard'));
    renderIntegrationStatus();
  }

  function showSettings() {
    closeMenu();
    const section = ensureSettingsSection();
    if (!section) return;
    $$('.admin-section').forEach((item) => item.classList.add('hidden'));
    section.classList.remove('hidden');
    $$('#admin-nav .nav').forEach((button) => button.classList.remove('active'));
    const title = $('#admin-title');
    if (title) title.textContent = 'Configurações';
    renderSettings();
  }

  function performLogout(relogin) {
    if (relogin) sessionStorage.setItem('mm-relogin', '1');
    const logout = $('#logout');
    if (logout) logout.click();
    else if (typeof window.logout === 'function') window.logout();
    else location.reload();
  }

  function closeMenu() {
    const menu = $('#mm-account-menu');
    const pill = $('.user-pill');
    menu?.classList.remove('open');
    pill?.setAttribute('aria-expanded', 'false');
  }

  function toggleMenu() {
    const menu = $('#mm-account-menu');
    const pill = $('.user-pill');
    if (!menu || !pill) return;
    const open = !menu.classList.contains('open');
    menu.classList.toggle('open', open);
    pill.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) {
      const name = $('#mm-account-name');
      if (name) name.textContent = accountName();
      menu.querySelector('button')?.focus({ preventScroll: true });
    }
  }

  function ensureMenu() {
    installStyles();
    ensureSettingsSection();
    const actions = $('.top-actions');
    const pill = $('.user-pill');
    if (!actions || !pill) return;

    let menu = $('#mm-account-menu');
    if (!menu) {
      menu = document.createElement('div');
      menu.id = 'mm-account-menu';
      menu.setAttribute('role', 'menu');
      menu.innerHTML = `
        <div class="mm-account-head"><strong id="mm-account-name">${accountName().replace(/[&<>'\"]/g, '')}</strong><small>Administrador</small></div>
        <button id="mm-menu-settings" type="button" role="menuitem">⚙ Configurações</button>
        <button id="mm-menu-relogin" type="button" role="menuitem">↻ Sair e entrar novamente</button>
        <button id="mm-menu-logout" type="button" role="menuitem" data-danger="true">↪ Sair da conta</button>`;
      actions.appendChild(menu);
      $('#mm-menu-settings')?.addEventListener('click', showSettings);
      $('#mm-menu-relogin')?.addEventListener('click', () => performLogout(true));
      $('#mm-menu-logout')?.addEventListener('click', () => performLogout(false));
    }

    if (!pill.dataset.mmAccountMenuBound) {
      pill.setAttribute('role', 'button');
      pill.setAttribute('tabindex', '0');
      pill.setAttribute('aria-haspopup', 'menu');
      pill.setAttribute('aria-expanded', 'false');
      pill.addEventListener('click', (event) => {
        event.stopPropagation();
        toggleMenu();
      });
      pill.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          toggleMenu();
        }
      });
      pill.dataset.mmAccountMenuBound = 'true';
    }
  }

  function init() {
    ensureMenu();
    document.addEventListener('click', (event) => {
      const menu = $('#mm-account-menu');
      const pill = $('.user-pill');
      if (menu?.contains(event.target) || pill?.contains(event.target)) return;
      closeMenu();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeMenu();
    });
    const admin = $('#admin-app');
    if (admin) new MutationObserver(ensureMenu).observe(admin, { attributes: true, attributeFilter: ['class'] });
    if (sessionStorage.getItem('mm-relogin') === '1') {
      sessionStorage.removeItem('mm-relogin');
      setTimeout(() => {
        if (typeof window.openAuth === 'function') window.openAuth('login');
        else $('#open-login')?.click();
      }, 180);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();