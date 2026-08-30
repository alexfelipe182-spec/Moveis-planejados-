(() => {
  'use strict';
  const API = window.API_BASE_URL || (location.hostname === 'localhost'
    ? 'http://localhost:8000/api/v1'
    : 'https://ideal-marcenaria-api.onrender.com/api/v1');
  const $ = (selector) => document.querySelector(selector);
  const selected = $('#plan');

  function money(value) {
    return Number(value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
  }

  function choose(code) {
    selected.value = code;
    document.querySelectorAll('.plan').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.code === code ? 'true' : 'false');
    });
  }

  async function loadPlans() {
    const response = await fetch(`${API}/plans`, { headers: { Accept: 'application/json' } });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Não foi possível carregar os planos.');
    const plans = data.plans || [];
    $('#plans').innerHTML = plans.map((plan) => `
      <button type="button" class="plan" data-code="${plan.code}" aria-pressed="${plan.code === 'starter'}">
        <strong>${plan.name}</strong>
        <div class="price">${money(plan.monthly_price_brl)}<small>/mês</small></div>
        <small>Até ${plan.max_users} usuários · ${plan.max_active_projects} projetos ativos</small>
      </button>`).join('');
    document.querySelectorAll('.plan').forEach((button) => button.addEventListener('click', () => choose(button.dataset.code)));
  }

  $('#form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const message = $('#message');
    const submit = event.submitter;
    submit.disabled = true;
    message.className = 'message';
    message.textContent = 'Criando ambiente isolado...';
    try {
      const response = await fetch(`${API}/auth/register-business`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({
          business_name: $('#business').value.trim(),
          owner_name: $('#owner').value.trim(),
          email: $('#email').value.trim().toLowerCase(),
          password: $('#password').value,
          plan_code: selected.value,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Erro ${response.status}`);
      message.className = 'message success';
      message.textContent = `${data.tenant.name} criada. Você já é o administrador desta empresa.`;
      setTimeout(() => { location.href = '/'; }, 1400);
    } catch (error) {
      message.textContent = error.message || 'Não foi possível criar a empresa.';
    } finally {
      submit.disabled = false;
    }
  });

  loadPlans().catch((error) => { $('#plans').innerHTML = `<p>${error.message}</p>`; });
})();
