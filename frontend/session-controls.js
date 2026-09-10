(() => {
  const API_BASE = window.API_BASE_URL || (
    location.hostname === 'localhost'
      ? 'http://localhost:8000/api/v1'
      : 'https://ideal-marcenaria-api.onrender.com/api/v1'
  );
  const SIGNED_OUT_KEY = 'mm-explicit-signout';
  const RELOGIN_KEY = 'mm-relogin';
  const LOGOUT_SELECTOR = '#logout, #mm-menu-logout, #settings-logout, [data-account-action="logout"]';
  const RELOGIN_SELECTOR = '#mm-menu-relogin, #settings-relogin, #direct-relogin, [data-account-action="relogin"]';
  const ACTION_BUTTON_SELECTOR = [
    'button[onclick]:not([type])',
    'button.nav:not([type])',
    'button.stat:not([type])',
    'button.dashboard-kpi:not([type])',
    'button.small-btn:not([type])',
    'button.icon-button:not([type])',
    'button.notification-button:not([type])',
    'button[data-dashboard-search-resource]:not([type])',
  ].join(',');

  const nativeFetch = window.fetch.bind(window);
  const refreshControllers = new Set();
  let logoutPromise = null;

  function requestUrl(input) {
    try {
      if (typeof input === 'string') return new URL(input, location.href);
      if (input instanceof URL) return input;
      if (input && typeof input.url === 'string') return new URL(input.url, location.href);
    } catch (_) {
      return null;
    }
    return null;
  }

  function isApiPath(input, suffix) {
    const url = requestUrl(input);
    if (!url) return false;
    return url.href.startsWith(API_BASE) && url.pathname.endsWith(suffix);
  }

  function signedOut() {
    try {
      return sessionStorage.getItem(SIGNED_OUT_KEY) === '1';
    } catch (_) {
      return false;
    }
  }

  function syntheticUnauthorized() {
    return new Response(JSON.stringify({ detail: 'Sessão encerrada' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
    });
  }

  window.fetch = function guardedFetch(input, init = {}) {
    const refreshRequest = isApiPath(input, '/auth/refresh');
    const sessionRestoreRequest = isApiPath(input, '/me');

    if (signedOut() && (refreshRequest || sessionRestoreRequest)) {
      return Promise.resolve(syntheticUnauthorized());
    }

    if (!refreshRequest) return nativeFetch(input, init);

    const controller = new AbortController();
    const upstreamSignal = init?.signal;
    if (upstreamSignal) {
      if (upstreamSignal.aborted) controller.abort();
      else upstreamSignal.addEventListener('abort', () => controller.abort(), { once: true });
    }
    refreshControllers.add(controller);

    return nativeFetch(input, { ...init, signal: controller.signal })
      .finally(() => refreshControllers.delete(controller));
  };

  function abortRefreshRequests() {
    refreshControllers.forEach((controller) => controller.abort());
    refreshControllers.clear();
  }

  function readCsrfCookie() {
    const entry = document.cookie
      .split('; ')
      .find((value) => value.startsWith('csrf_token='));
    return entry ? decodeURIComponent(entry.split('=').slice(1).join('=')) : '';
  }

  async function fallbackLogoutRequest() {
    const csrf = readCsrfCookie();
    const headers = csrf ? { 'X-CSRF-Token': csrf } : {};
    const response = await nativeFetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
      headers,
      cache: 'no-store',
    });
    if (!response.ok && response.status !== 204) {
      throw new Error(`Falha ao encerrar sessão (${response.status})`);
    }
  }

  async function requestLogout() {
    if (typeof window.api === 'function') {
      try {
        await window.api('/auth/logout', { method: 'POST', cache: 'no-store' }, false);
        return;
      } catch (_) {
        // Retry with the CSRF cookie itself. This avoids a stale in-memory CSRF token
        // preventing logout after a refresh rotation.
      }
    }
    await fallbackLogoutRequest();
  }

  function setLogoutButtonsBusy(busy) {
    document.querySelectorAll(`${LOGOUT_SELECTOR}, ${RELOGIN_SELECTOR}`).forEach((button) => {
      if (!(button instanceof HTMLButtonElement)) return;
      button.disabled = busy;
      if (busy) button.setAttribute('aria-busy', 'true');
      else button.removeAttribute('aria-busy');
    });
  }

  function rememberExplicitLogout(relogin) {
    try {
      sessionStorage.setItem(SIGNED_OUT_KEY, '1');
      if (relogin) sessionStorage.setItem(RELOGIN_KEY, '1');
      else sessionStorage.removeItem(RELOGIN_KEY);
    } catch (_) {}
  }

  function allowFreshLogin() {
    try {
      sessionStorage.removeItem(SIGNED_OUT_KEY);
    } catch (_) {}
  }

  async function leaveSession(relogin = false) {
    if (logoutPromise) return logoutPromise;

    rememberExplicitLogout(relogin);
    abortRefreshRequests();
    setLogoutButtonsBusy(true);

    logoutPromise = (async () => {
      try {
        await requestLogout();
      } catch (error) {
        console.error('Não foi possível confirmar o logout no servidor.', error);
      } finally {
        window.location.replace('/');
      }
    })();

    return logoutPromise;
  }

  function normalizeActionButtons(root = document) {
    const buttons = [];
    if (root instanceof Element && root.matches(ACTION_BUTTON_SELECTOR)) buttons.push(root);
    if (root.querySelectorAll) buttons.push(...root.querySelectorAll(ACTION_BUTTON_SELECTOR));
    buttons.forEach((button) => button.setAttribute('type', 'button'));
  }

  document.addEventListener('click', (event) => {
    const target = event.target instanceof Element
      ? event.target.closest(`${LOGOUT_SELECTOR}, ${RELOGIN_SELECTOR}`)
      : null;
    if (!target) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    leaveSession(target.matches(RELOGIN_SELECTOR));
  }, true);

  document.addEventListener('submit', (event) => {
    if (event.target?.id === 'login-form') allowFreshLogin();
  }, true);

  function init() {
    normalizeActionButtons();
    const body = document.body;
    if (body) {
      new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          mutation.addedNodes.forEach((node) => {
            if (node instanceof Element) normalizeActionButtons(node);
          });
        });
      }).observe(body, { childList: true, subtree: true });
    }
  }

  window.MM_SESSION_CONTROLS = Object.freeze({
    logout: () => leaveSession(false),
    relogin: () => leaveSession(true),
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
