(() => {
  const $ = (selector, root = document) => root.querySelector(selector);

  function applyAuthenticatedReference() {
    const admin = $('#admin-app');
    if (!admin) return;

    if (!admin.classList.contains('reference-authenticated-dashboard')) {
      admin.classList.add('reference-public-dashboard', 'reference-authenticated-dashboard');
    }

    const sidebar = $('.sidebar', admin);
    sidebar?.classList.add('reference-public-sidebar');

    const brand = $('.side-brand', admin);
    brand?.classList.add('reference-public-brand');
    $('.logo-mark', brand)?.classList.add('reference-public-logo');

    const nav = $('#admin-nav', admin);
    nav?.classList.add('reference-public-nav');

    $('.side-plan-card', admin)?.classList.add('reference-public-plan');

    const main = $('.admin-main', admin);
    main?.classList.add('reference-public-main');

    const topbar = $('.topbar', admin);
    topbar?.classList.add('reference-public-topbar');

    $('.reference-search', topbar)?.classList.add('reference-public-search');

    const actions = $('.top-actions', topbar);
    actions?.classList.add('reference-public-account-wrap');
    $('.notification-button', actions)?.classList.add('reference-public-notification');
    $('.topbar-divider', actions)?.classList.add('reference-public-divider');

    const account = $('.user-pill', actions);
    account?.classList.add('reference-public-account');
    $('.user-meta', account)?.classList.add('reference-public-account-copy');
    $('.user-avatar', account)?.classList.add('reference-public-avatar');
    $('.user-chevron', account)?.classList.add('reference-public-chevron');

    $('#dashboard', admin)?.classList.add('reference-authenticated-content');
  }

  function init() {
    applyAuthenticatedReference();
    document.addEventListener('mm:auth-changed', applyAuthenticatedReference);

    const admin = $('#admin-app');
    if (admin) {
      new MutationObserver(applyAuthenticatedReference).observe(admin, {
        attributes: true,
        attributeFilter: ['class'],
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();