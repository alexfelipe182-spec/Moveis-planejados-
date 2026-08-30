(() => {
  'use strict';
  const API = window.API_BASE_URL || (location.hostname === 'localhost'
    ? 'http://localhost:8000/api/v1'
    : 'https://ideal-marcenaria-api.onrender.com/api/v1');
  const $ = (selector) => document.querySelector(selector);
  let accessToken = '';
  let csrfToken = '';

  function escapeHtml(value = '') {
    return String(value).replace(/[&<>'"]/g, (char) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;',
    })[char]);
  }

  async function api(path, options = {}) {
    const headers = { Accept: 'application/json', ...(options.headers || {}) };
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
    if (csrfToken && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(options.method)) {
      headers['X-CSRF-Token'] = csrfToken;
    }
    if (options.body && typeof options.body !== 'string') {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }
    const response = await fetch(`${API}${path}`, {
      credentials: 'include',
      ...options,
      headers,
    });
    const data = response.status === 204 ? null : await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data?.detail || `Erro ${response.status}`);
    return data;
  }

  function renderMetrics(data) {
    const items = [
      ['Empresas', data.tenants],
      ['Empresas ativas', data.active_tenants],
      ['Usuários', data.users],
      ['Projetos', data.projects],
    ];
    $('#metrics').innerHTML = items.map(([label, value]) => (
      `<div class="metric"><span>${escapeHtml(label)}</span><strong>${Number(value || 0)}</strong></div>`
    )).join('');
  }

  function options(values, selected) {
    return values.map((value) => (
      `<option value="${escapeHtml(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(value)}</option>`
    )).join('');
  }

  async function load() {
    const [dashboard, tenants] = await Promise.all([
      api('/superadmin/dashboard'),
      api('/superadmin/tenants?limit=100'),
    ]);
    renderMetrics(dashboard);
    $('#tenants').innerHTML = tenants.map((tenant) => {
      const tenantId = Number(tenant.id);
      const trial = tenant.trial_ends_at
        ? new Date(tenant.trial_ends_at).toLocaleDateString('pt-BR')
        : '—';
      return `<tr>
        <td><strong>${escapeHtml(tenant.name)}</strong><br><small>${escapeHtml(tenant.slug)}</small></td>
        <td><select id="status-${tenantId}">${options(['trialing', 'active', 'past_due', 'suspended', 'cancelled'], tenant.status)}</select></td>
        <td><select id="plan-${tenantId}">${options(['starter', 'professional', 'business'], tenant.plan_code)}</select></td>
        <td>${escapeHtml(trial)}</td>
        <td class="actions"><button type="button" data-save-tenant="${tenantId}">Salvar</button></td>
      </tr>`;
    }).join('');

    document.querySelectorAll('[data-save-tenant]').forEach((button) => {
      button.addEventListener('click', () => saveTenant(Number(button.dataset.saveTenant)));
    });
  }

  async function saveTenant(tenantId) {
    const message = $('#message');
    try {
      await api(`/superadmin/tenants/${tenantId}`, {
        method: 'PATCH',
        body: {
          status: $(`#status-${tenantId}`).value,
          plan_code: $(`#plan-${tenantId}`).value,
        },
      });
      message.style.color = '#86efac';
      message.textContent = 'Empresa atualizada.';
      await load();
    } catch (error) {
      message.style.color = '#fca5a5';
      message.textContent = error.message;
    }
  }

  $('#login-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const message = $('#login-message');
    message.textContent = '';
    try {
      const body = new URLSearchParams({
        username: $('#email').value.trim().toLowerCase(),
        password: $('#password').value,
      });
      const response = await fetch(`${API}/auth/login`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Falha no login');
      accessToken = data.access_token || '';
      csrfToken = data.csrf_token || '';
      const me = await api('/me');
      if (!me.is_superadmin) {
        accessToken = '';
        csrfToken = '';
        throw new Error('Esta conta não possui permissão de superadministrador.');
      }
      $('#login').classList.add('hidden');
      $('#app').classList.remove('hidden');
      await load();
    } catch (error) {
      message.textContent = error.message;
    }
  });
})();
