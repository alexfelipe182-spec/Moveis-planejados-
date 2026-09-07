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
      #mm-account-menu{position:absolute;right:0;top:calc(100% + 10px);width:min(290px,calc(100vw - 24px));padding:10px;background:#fff;border:1px solid rgba(13,89,61,.16);border-radius:16px;box-shadow:0 18px 50px rgba(9,54,38,.18);display:none;z-index:1000}
      #mm-account-menu.open{display:grid;gap:6px}
      #mm-account-menu .mm-account-head{padding:8px 10px 10px;border-bottom:1px solid rgba(13,89,61,.10);margin-bottom:2px}
      #mm-account-menu .mm-account-head strong{display:block;color:#102119;font-size:14px}
      #mm-account-menu .mm-account-head small{display:block;color:#617168;margin-top:2px}
      #mm-account-menu button{width:100%;border:0;background:transparent;border-radius:10px;padding:10px 12px;text-align:left;color:#102119;font:inherit;font-weight:700;cursor:pointer}
      #mm-account-menu button:hover,#mm-account-menu button:focus-visible{background:#eef8f2;outline:none}
      #mm-account-menu button[data-danger="true"]{color:#9b2c2c}
      @media(max-width:760px){#mm-account-menu{position:fixed;right:12px;top:72px;width:min(320px,calc(100vw - 24px))}}
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
        <div class="panel" style="margin-top:16px"><strong>${accountName().replace(/[&<>'\"]/g, '')}</strong><p class="muted">Administrador da marcenaria</p></div>
        <div class="toolbar-actions" style="margin-top:18px;display:flex;gap:10px;flex-wrap:wrap">
          <button id="settings-relogin" class="btn primary" type="button">↻ Sair e entrar novamente</button>
          <button id="settings-logout" class="btn secondary" type="button">↪ Sair da conta</button>
          <button id="settings-dashboard" class="btn secondary" type="button">⌂ Voltar ao Dashboard</button>
        </div>
      </div>`;
    $('#settings-relogin')?.addEventListener('click', () => performLogout(true));
    $('#settings-logout')?.addEventListener('click', () => performLogout(false));
    $('#settings-dashboard')?.addEventListener('click', () => window.showSection?.('dashboard'));
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
