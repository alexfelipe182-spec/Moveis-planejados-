(() => {
  const API_BASE = window.API_BASE_URL || (location.hostname === 'localhost'
    ? 'http://localhost:8000/api/v1'
    : 'https://ideal-marcenaria-api.onrender.com/api/v1');
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  function csrfToken() {
    return document.cookie
      .split('; ')
      .find((entry) => entry.startsWith('csrf_token='))
      ?.split('=')[1] || '';
  }

  function normalizeButtons(root = document) {
    if (root instanceof HTMLButtonElement && !root.hasAttribute('type')) root.type = 'button';
    if (!root.querySelectorAll) return;
    root.querySelectorAll('button:not([type])').forEach((button) => {
      button.type = 'button';
    });
  }

  function injectStyles() {
    if ($('#mm-account-controls-style')) return;
    const style = document.createElement('style');
    style.id = 'mm-account-controls-style';
    style.textContent = `
      #admin-app button{touch-action:manipulation;-webkit-tap-highlight-color:transparent}
      #admin-app button:disabled{cursor:not-allowed;opacity:.62}
      .mm-account-wrap{position:relative;display:flex;align-items:center}
      .mm-account-trigger{cursor:pointer;user-select:none;outline:none;transition:border-color .18s ease,box-shadow .18s ease,transform .18s ease}
      .mm-account-trigger:hover{border-color:rgba(8,122,79,.34);box-shadow:0 8px 22px rgba(8,122,79,.10)}
      .mm-account-trigger:focus-visible{outline:3px solid rgba(8,122,79,.20);outline-offset:2px}
      .mm-account-chevron{margin-left:2px;font-size:.72rem;color:inherit;opacity:.72}
      .mm-account-menu{position:absolute;right:0;top:calc(100% + 10px);z-index:120;width:min(290px,calc(100vw - 28px));padding:8px;border:1px solid rgba(8,122,79,.16);border-radius:16px;background:#fff;box-shadow:0 18px 55px rgba(20,45,33,.18)}
      .mm-account-menu.hidden{display:none!important}
      .mm-account-menu-head{padding:10px 12px 8px;border-bottom:1px solid #e7eee9;margin-bottom:6px}
      .mm-account-menu-head strong,.mm-account-menu-head small{display:block;color:#111}
      .mm-account-menu-head small{margin-top:3px;color:#5c6962;font-size:.76rem}
      .mm-account-menu button{width:100%;display:flex;align-items:center;gap:10px;padding:11px 12px;border:0;border-radius:11px;background:transparent;color:#1d2b24;text-align:left;font-weight:700;cursor:pointer}
      .mm-account-menu button:hover{background:#edf8f2;color:#066b45}
      .mm-account-menu button.mm-danger{color:#9b3232}
      .mm-account-menu button.mm-danger:hover{background:#fff0f0;color:#822828}
      .mm-settings-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:18px}
      .mm-settings-card{padding:24px;border:1px solid rgba(8,122,79,.13);border-radius:20px;background:#fff;box-shadow:0 8px 26px rgba(25,55,39,.06)}
      .mm-settings-card h2,.mm-settings-card h3{margin-bottom:8px}
      .mm-settings-user{display:flex;align-items:center;gap:14px;margin:18px 0;padding:16px;border-radius:15px;background:#f5faf7;border:1px solid #e2eee7}
      .mm-settings-avatar{display:grid;place-items:center;width:48px;height:48px;border-radius:50%;background:#087a4f;color:#fff;font-weight:850;font-size:1.1rem}
      .mm-settings-user strong,.mm-settings-user small{display:block}
      .mm-settings-user small{color:#68756e;margin-top:3px}
      .mm-settings-actions{display:grid;gap:10px;margin-top:18px}
      .mm-settings-actions .btn{width:100%;justify-content:center}
      .mm-settings-note{padding:13px 14px;border-radius:13px;background:#f8faf8;color:#55645c;font-size:.88rem;line-height:1.55;border:1px solid #e7eee9}
      @media(max-width:760px){
        .mm-account-menu{position:fixed;right:14px;top:74px}
        .mm-settings-grid{grid-template-columns:1fr}
        .mm-settings-card{padding:19px}
      }
    `;
    document.head.appendChild(style);
  }

  function currentUser() {
    let user = null;
    try {
      if (typeof state !== 'undefined' && state?.user) user = state.user;
    } catch (_) {
      user = null;
    }
    const name = user?.name || $('#user-badge')?.textContent?.trim() || 'Administrador';
    return {
      name,
      email: user?.email || '',
      initials: name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'MM',
    };
  }

  function closeAccountMenu() {
    const menu = $('#mm-account-menu');
    const trigger = $('.mm-account-trigger');
    menu?.classList.add('hidden');
    trigger?.setAttribute('aria-expanded', 'false');
  }

  function toggleAccountMenu() {
    const menu = $('#mm-account-menu');
    const trigger = $('.mm-account-trigger');
    if (!menu || !trigger) return;
    const willOpen = menu.classList.contains('hidden');
    menu.classList.toggle('hidden', !willOpen);
    trigger.setAttribute('aria-expanded', String(willOpen));
    if (willOpen) {
      const user = currentUser();
      $('#mm-account-menu-name').textContent = user.name;
      $('#mm-account-menu-email').textContent = user.email || 'Conta administrativa';
    }
  }

  function ensureSettingsSection() {
    const adminMain = $('.admin-main');
    const nav = $('#admin-nav');
    if (!adminMain || !nav) return null;

    let section = $('#account-settings');
    if (!section) {
      section = document.createElement('section');
      section.id = 'account-settings';
      section.className = 'admin-section hidden';
      adminMain.appendChild(section);
    }

    let navButton = $('#account-settings-nav');
    if (!navButton) {
      navButton = document.createElement('button');
      navButton.id = 'account-settings-nav';
      navButton.className = 'nav';
      navButton.type = 'button';
      navButton.dataset.section = 'account-settings';
      navButton.innerHTML = '⚙ <span>Configurações</span>';
      nav.appendChild(navButton);
      navButton.addEventListener('click', showSettings);
    }
    return section;
  }

  function renderSettings() {
    const section = ensureSettingsSection();
    if (!section) return;
    const user = currentUser();
    section.innerHTML = `
      <div class="mm-settings-grid">
        <article class="mm-settings-card">
          <span class="eyebrow">Configurações da conta</span>
          <h2>Conta e acesso</h2>
          <p class="muted">Gerencie sua sessão e alterne entre contas com segurança.</p>
          <div class="mm-settings-user">
            <span class="mm-settings-avatar" aria-hidden="true">${user.initials}</span>
            <span><strong>${user.name.replace(/[&<>'"]/g, '')}</strong><small>${(user.email || 'Administrador da marcenaria').replace(/[&<>'"]/g, '')}</small></span>
          </div>
          <div class="mm-settings-note">Ao usar “Sair e entrar novamente”, sua sessão atual é encerrada e a tela de login abre automaticamente para você escolher outra conta.</div>
          <div class="mm-settings-actions">
            <button class="btn primary" type="button" data-account-action="relogin">↻ Sair e entrar novamente</button>
            <button class="btn secondary" type="button" data-account-action="logout">↪ Sair da conta</button>
          </div>
        </article>
        <article class="mm-settings-card">
          <span class="eyebrow">Preferências</span>
          <h3>Painel</h3>
          <p class="muted">Acesse rapidamente as principais preferências da plataforma.</p>
          <div class="mm-settings-actions">
            <button class="btn secondary" type="button" data-account-action="dashboard">⌂ Voltar ao Dashboard</button>
            <button class="btn secondary" type="button" data-account-action="theme">☾ Alternar tema</button>
          </div>
        </article>
      </div>`;
    normalizeButtons(section);
  }

  function showSettings() {
    const section = ensureSettingsSection();
    if (!section) return;
    $$('.admin-section').forEach((item) => item.classList.add('hidden'));
    section.classList.remove('hidden');
    $$('#admin-nav .nav').forEach((button) => button.classList.remove('active'));
    $('#account-settings-nav')?.classList.add('active');
    const title = $('#admin-title');
    if (title) title.textContent = 'Configurações';
    renderSettings();
    closeAccountMenu();
  }

  function showLoginOverlay() {
    const overlay = $('#auth-overlay');
    if (!overlay) return;
    $('#admin-app')?.classList.add('hidden');
    $('#public-site')?.classList.remove('hidden');
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
    ['login', 'register', 'recovery', 'reset'].forEach((view) => {
      $(`#${view}-view`)?.classList.toggle('hidden', view !== 'login');
    });
    setTimeout(() => $('#login-email')?.focus(), 30);
  }

  async function fallbackLogout() {
    const headers = {};
    const token = csrfToken();
    if (token) headers['X-CSRF-Token'] = token;
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
        headers,
      });
    } finally {
      location.reload();
    }
  }

  function logoutCurrentAccount(reopenLogin = false) {
    if (reopenLogin) sessionStorage.setItem('mm-reopen-login', '1');
    if (typeof window.logout === 'function') {
      window.logout();
      return;
    }
    fallbackLogout();
  }

  function handleAccountAction(action) {
    if (action === 'settings') showSettings();
    if (action === 'logout') logoutCurrentAccount(false);
    if (action === 'relogin') logoutCurrentAccount(true);
    if (action === 'dashboard' && typeof window.showSection === 'function') window.showSection('dashboard');
    if (action === 'theme') $('#theme-toggle')?.click();
  }

  function injectAccountMenu() {
    const topActions = $('.top-actions');
    const userPill = $('.user-pill');
    if (!topActions || !userPill || $('#mm-account-menu')) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'mm-account-wrap';
    userPill.parentNode.insertBefore(wrapper, userPill);
    wrapper.appendChild(userPill);

    userPill.classList.add('mm-account-trigger');
    userPill.setAttribute('role', 'button');
    userPill.setAttribute('tabindex', '0');
    userPill.setAttribute('aria-haspopup', 'menu');
    userPill.setAttribute('aria-expanded', 'false');
    userPill.setAttribute('title', 'Abrir configurações da conta');
    userPill.insertAdjacentHTML('beforeend', '<span class="mm-account-chevron" aria-hidden="true">▾</span>');

    const menu = document.createElement('div');
    menu.id = 'mm-account-menu';
    menu.className = 'mm-account-menu hidden';
    menu.setAttribute('role', 'menu');
    menu.innerHTML = `
      <div class="mm-account-menu-head">
        <strong id="mm-account-menu-name">Conta</strong>
        <small id="mm-account-menu-email">Conta administrativa</small>
      </div>
      <button type="button" role="menuitem" data-account-action="settings">⚙ Configurações da conta</button>
      <button type="button" role="menuitem" data-account-action="relogin">↻ Sair e entrar novamente</button>
      <button type="button" role="menuitem" class="mm-danger" data-account-action="logout">↪ Sair</button>`;
    wrapper.appendChild(menu);

    userPill.addEventListener('click', toggleAccountMenu);
    userPill.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggleAccountMenu();
      }
      if (event.key === 'Escape') closeAccountMenu();
    });
  }

  function setupDelegatedActions() {
    document.addEventListener('click', (event) => {
      const actionButton = event.target.closest('[data-account-action]');
      if (actionButton) {
        event.preventDefault();
        handleAccountAction(actionButton.dataset.accountAction);
        return;
      }
      if (!event.target.closest('.mm-account-wrap')) closeAccountMenu();
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeAccountMenu();
    });
  }

  function watchDynamicButtons() {
    if (!document.body) return;
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) normalizeButtons(node);
        });
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function init() {
    injectStyles();
    normalizeButtons();
    ensureSettingsSection();
    injectAccountMenu();
    setupDelegatedActions();
    watchDynamicButtons();

    if (sessionStorage.getItem('mm-reopen-login') === '1') {
      sessionStorage.removeItem('mm-reopen-login');
      setTimeout(showLoginOverlay, 60);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
