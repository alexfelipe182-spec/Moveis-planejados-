(() => {
  const pathname = window.location.pathname.replace(/\/+$/, '') || '/';
  const isDashboardRoute = pathname === '/dashboard' || pathname.startsWith('/dashboard/');
  if (!isDashboardRoute) return;

  const admin = document.querySelector('#admin-app');
  const overlay = document.querySelector('#auth-overlay');
  if (!admin || !overlay || typeof openAuth !== 'function' || typeof closeAuth !== 'function') return;

  document.addEventListener('mm:auth-changed', () => closeAuth(), { once: true });

  if (admin.classList.contains('hidden')) {
    openAuth('login');
    document.querySelector('#login-email')?.focus({ preventScroll: true });
  } else {
    closeAuth();
  }
})();
