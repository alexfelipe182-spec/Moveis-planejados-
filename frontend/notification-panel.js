(() => {
  const BUTTON_SELECTOR = '.reference-public-notification';
  const PANEL_ID = 'reference-public-notification-panel';
  const STYLE_ID = 'reference-public-notification-styles';

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .reference-public-account-wrap{position:relative;isolation:isolate}
      .reference-public-notification{display:grid;place-items:center;flex:0 0 42px;width:42px;height:42px;border-radius:12px;touch-action:manipulation;-webkit-tap-highlight-color:transparent}
      .reference-public-notification:focus-visible{outline:3px solid rgba(8,122,79,.24);outline-offset:2px}
      .reference-public-notification .reference-public-notification-dot{display:none;position:absolute;top:6px;right:7px;width:8px;height:8px;border-radius:50%;background:var(--ref-gold,#c58c27);box-shadow:0 0 0 2px #fff}
      .reference-public-notification.has-unread .reference-public-notification-dot{display:block}
      .reference-public-notification-panel{position:absolute;top:calc(100% + 12px);right:0;z-index:50;width:min(360px,calc(100vw - 24px));max-height:min(430px,70vh);overflow:auto;padding:10px;border:1px solid #d8e8df;border-radius:16px;background:#fff;color:#111;box-shadow:0 20px 50px rgba(13,43,29,.18)}
      .reference-public-notification-panel[hidden]{display:none!important}
      .reference-public-notification-panel header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:8px 8px 12px;border-bottom:1px solid #edf1ee}
      .reference-public-notification-panel h2{margin:0;font:750 .95rem/1.2 Manrope,Inter,sans-serif;color:#16231e}
      .reference-public-notification-panel button{font:inherit}
      .reference-public-notification-empty{margin:0;padding:28px 12px;text-align:center;color:#66746d;font-size:.82rem;line-height:1.5}
      .reference-public-notification-list{display:grid;gap:6px;margin:8px 0 0;padding:0;list-style:none}
      .reference-public-notification-item{display:grid;gap:5px;padding:12px;border-radius:12px;background:#f7faf8}
      .reference-public-notification-item[data-unread="true"]{background:#eef8f2;box-shadow:inset 3px 0 0 var(--ref-gold,#c58c27)}
      .reference-public-notification-item strong{font-size:.8rem;color:#1d2d25}
      .reference-public-notification-item p{margin:0;color:#56665e;font-size:.75rem;line-height:1.45}
      .reference-public-notification-mark{justify-self:start;padding:6px 9px;border:1px solid #d7e6de;border-radius:999px;background:#fff;color:#087a4f;cursor:pointer;font-size:.68rem;font-weight:700}
      @media(max-width:720px){
        .reference-public-account-wrap{gap:8px}
        .reference-public-notification{flex-basis:44px;width:44px;height:44px}
        .reference-public-divider{margin:0 2px}
        .reference-public-notification-panel{position:fixed;top:76px;right:12px;left:12px;width:auto;max-height:calc(100dvh - 96px)}
      }
    `;
    document.head.appendChild(style);
  }

  function normalizeNotifications(value) {
    if (!Array.isArray(value)) return [];
    return value.filter(Boolean).map((item, index) => ({
      id: item.id ?? `notification-${index}`,
      title: String(item.title || 'Notificação'),
      message: String(item.message || ''),
      read: Boolean(item.read || item.read_at),
    }));
  }

  function initNotifications() {
    const button = document.querySelector(BUTTON_SELECTOR);
    if (!button || document.getElementById(PANEL_ID)) return;

    injectStyles();

    const legacyDot = button.querySelector('span');
    if (legacyDot) {
      legacyDot.className = 'reference-public-notification-dot';
      legacyDot.hidden = true;
    }

    button.setAttribute('aria-label', 'Notificações');
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-haspopup', 'dialog');
    button.setAttribute('aria-controls', PANEL_ID);

    const panel = document.createElement('section');
    panel.id = PANEL_ID;
    panel.className = 'reference-public-notification-panel';
    panel.hidden = true;
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Painel de notificações');
    panel.innerHTML = '<header><h2>Notificações</h2></header><div class="reference-public-notification-body"></div>';
    button.parentElement.appendChild(panel);

    let notifications = normalizeNotifications(window.MM_NOTIFICATIONS);

    function render() {
      const body = panel.querySelector('.reference-public-notification-body');
      const unreadCount = notifications.filter(item => !item.read).length;
      button.classList.toggle('has-unread', unreadCount > 0);
      if (legacyDot) legacyDot.hidden = unreadCount === 0;
      button.setAttribute('aria-label', unreadCount ? `Notificações, ${unreadCount} não ${unreadCount === 1 ? 'lida' : 'lidas'}` : 'Notificações');

      if (!notifications.length) {
        body.innerHTML = '<p class="reference-public-notification-empty">Nenhuma notificação</p>';
        return;
      }

      body.innerHTML = '<ul class="reference-public-notification-list"></ul>';
      const list = body.querySelector('ul');
      notifications.forEach(item => {
        const li = document.createElement('li');
        li.className = 'reference-public-notification-item';
        li.dataset.unread = String(!item.read);
        const strong = document.createElement('strong');
        strong.textContent = item.title;
        const message = document.createElement('p');
        message.textContent = item.message;
        li.append(strong, message);
        if (!item.read) {
          const mark = document.createElement('button');
          mark.type = 'button';
          mark.className = 'reference-public-notification-mark';
          mark.textContent = 'Marcar como lida';
          mark.addEventListener('click', () => {
            item.read = true;
            render();
          });
          li.appendChild(mark);
        }
        list.appendChild(li);
      });
    }

    function setOpen(open) {
      panel.hidden = !open;
      button.setAttribute('aria-expanded', String(open));
    }

    button.addEventListener('click', event => {
      event.stopPropagation();
      setOpen(panel.hidden);
    });

    panel.addEventListener('click', event => event.stopPropagation());
    document.addEventListener('click', () => setOpen(false));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !panel.hidden) {
        setOpen(false);
        button.focus();
      }
    });

    window.MultiMarcenariasNotifications = {
      set(items) {
        notifications = normalizeNotifications(items);
        render();
      },
      clear() {
        notifications = [];
        render();
      },
    };

    render();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNotifications, { once: true });
  } else {
    initNotifications();
  }
})();
