(() => {
  const triggerSelector = '.notification-button, .reference-public-notification';
  const bellIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></svg><span class="notification-dot" aria-hidden="true" hidden></span>`;
  const fallbackReadMarkers = new Map();
  let activities = [];
  let activeTrigger = null;
  let panel = null;
  let requestSequence = 0;

  const identity = () => state.user ? `${state.user.tenant_id}:${state.user.id}` : '';
  const storageKey = () => `mm-notifications-read:${identity()}`;

  function readMarker() {
    if (!identity()) return 0;
    try {
      return Number(localStorage.getItem(storageKey())) || 0;
    } catch (_) {
      return fallbackReadMarkers.get(storageKey()) || 0;
    }
  }

  function saveReadMarker(value) {
    try {
      localStorage.setItem(storageKey(), String(value));
    } catch (_) {
      fallbackReadMarkers.set(storageKey(), value);
    }
  }

  function unreadCount() {
    const marker = readMarker();
    return activities.filter((activity) => Number(activity.id) > marker).length;
  }

  function updateIndicators() {
    const count = state.user ? unreadCount() : 0;
    document.querySelectorAll(triggerSelector).forEach((button) => {
      const dot = button.querySelector('.notification-dot');
      if (dot) dot.hidden = count === 0;
      button.setAttribute('aria-label', count
        ? `Notificações: ${count} ${count === 1 ? 'não lida' : 'não lidas'}`
        : 'Notificações');
    });
  }

  function renderActivities() {
    if (!panel) return;
    const content = panel.querySelector('[data-notification-content]');
    const marker = readMarker();
    content.innerHTML = activities.length
      ? `<ul>${activities.map((activity) => `<li class="${Number(activity.id) > marker ? 'unread' : ''}"><strong>${escapeHtml(activity.description)}</strong><time datetime="${escapeHtml(activity.created_at)}">${escapeHtml(new Date(activity.created_at).toLocaleString('pt-BR'))}</time></li>`).join('')}</ul>`
      : '<p class="notifications-empty">Nenhuma notificação por enquanto.</p>';
    panel.querySelector('[data-notification-read]').disabled = unreadCount() === 0;
    updateIndicators();
  }

  function closePanel(restoreFocus = false) {
    requestSequence += 1;
    if (panel) panel.hidden = true;
    document.querySelectorAll(triggerSelector).forEach((button) => {
      button.setAttribute('aria-expanded', 'false');
    });
    if (restoreFocus) activeTrigger?.focus();
    activeTrigger = null;
  }

  function positionPanel(button) {
    const rect = button.getBoundingClientRect();
    const right = Math.max(12, window.innerWidth - rect.right);
    panel.style.top = `${Math.min(rect.bottom + 8, window.innerHeight - 90)}px`;
    panel.style.right = `${right}px`;
  }

  async function loadActivities(showLoading = true) {
    if (!state.user) {
      activities = [];
      updateIndicators();
      return;
    }
    const sequence = ++requestSequence;
    const owner = identity();
    if (showLoading && panel) {
      panel.querySelector('[data-notification-content]').textContent = 'Carregando notificações...';
    }
    try {
      const result = await api('/activities?limit=20');
      if (sequence !== requestSequence || owner !== identity()) return;
      activities = Array.isArray(result) ? result : [];
      if (panel && !panel.hidden) renderActivities();
      else updateIndicators();
    } catch (_) {
      if (sequence !== requestSequence || owner !== identity()) return;
      activities = [];
      updateIndicators();
      if (panel && !panel.hidden) {
        panel.querySelector('[data-notification-content]').textContent = 'Não foi possível carregar as notificações. Tente atualizar.';
        panel.querySelector('[data-notification-read]').disabled = true;
      }
    }
  }

  function ensurePanel() {
    if (panel) return panel;
    panel = document.createElement('section');
    panel.id = 'notifications-panel';
    panel.className = 'notifications-panel';
    panel.hidden = true;
    panel.setAttribute('role', 'region');
    panel.setAttribute('aria-labelledby', 'notifications-title');
    panel.innerHTML = `<div class="notifications-heading"><h2 id="notifications-title">Notificações</h2><button type="button" data-notification-close aria-label="Fechar notificações">×</button></div><div data-notification-content role="status" aria-live="polite"></div><div class="notifications-actions"><button type="button" data-notification-refresh>Atualizar</button><button type="button" data-notification-read>Marcar como lidas</button></div>`;
    document.body.appendChild(panel);
    panel.querySelector('[data-notification-close]').addEventListener('click', () => closePanel(true));
    panel.querySelector('[data-notification-refresh]').addEventListener('click', () => loadActivities());
    panel.querySelector('[data-notification-read]').addEventListener('click', () => {
      const newest = Math.max(0, ...activities.map((activity) => Number(activity.id) || 0));
      saveReadMarker(newest);
      renderActivities();
    });
    return panel;
  }

  function bindTriggers() {
    document.querySelectorAll(triggerSelector).forEach((button) => {
      if (button.dataset.notificationsBound) return;
      button.dataset.notificationsBound = 'true';
      button.innerHTML = bellIcon;
      button.setAttribute('aria-controls', 'notifications-panel');
      button.setAttribute('aria-expanded', 'false');
      button.addEventListener('click', () => {
        if (!state.user) {
          closePanel();
          openAuth('login');
          return;
        }
        ensurePanel();
        if (!panel.hidden && activeTrigger === button) {
          closePanel();
          return;
        }
        closePanel();
        activeTrigger = button;
        panel.hidden = false;
        positionPanel(button);
        button.setAttribute('aria-expanded', 'true');
        panel.querySelector('[data-notification-close]').focus();
        loadActivities();
      });
    });
    updateIndicators();
  }

  function init() {
    bindTriggers();
    new MutationObserver(bindTriggers).observe(document.body, { childList: true, subtree: true });
    document.addEventListener('click', (event) => {
      if (!event.target.closest(triggerSelector) && !panel?.contains(event.target)) closePanel();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && panel && !panel.hidden) closePanel(true);
    });
    document.addEventListener('mm:auth-changed', () => loadActivities(false));
    window.addEventListener('resize', () => {
      if (panel && !panel.hidden && activeTrigger) positionPanel(activeTrigger);
    });
    if (state.user) loadActivities(false);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
