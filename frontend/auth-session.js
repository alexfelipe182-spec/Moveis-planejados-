(() => {
  const originalApi = window.api;
  if (typeof originalApi !== 'function') return;

  let accessToken = '';

  window.api = async function(path, options = {}, retryAuth = true) {
    const nextOptions = { ...options, headers: { ...(options.headers || {}) } };
    if (accessToken && !nextOptions.headers.Authorization) {
      nextOptions.headers.Authorization = `Bearer ${accessToken}`;
    }

    const data = await originalApi(path, nextOptions, retryAuth);
    if ((path === '/auth/login' || path === '/auth/refresh') && typeof data?.access_token === 'string') {
      accessToken = data.access_token;
    }
    if (path === '/auth/logout') accessToken = '';
    return data;
  };
})();
