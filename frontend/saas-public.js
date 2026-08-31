(() => {
  const apiBase = window.API_BASE_URL || (location.hostname === 'localhost' ? 'http://localhost:8000/api/v1' : 'https://ideal-marcenaria-api.onrender.com/api/v1');
  const $ = (s, root = document) => root.querySelector(s);
  let selectedPlan = 'starter';

  function showRegister(plan = 'starter') {
    selectedPlan = plan;
    const overlay = $('#auth-overlay');
    overlay?.classList.remove('hidden');
    overlay?.setAttribute('aria-hidden', 'false');
    ['login', 'register', 'recovery', 'reset'].forEach((view) => {
      $(`#${view}-view`)?.classList.toggle('hidden', view !== 'register');
    });
    const planInput = $('#register-plan');
    if (planInput) planInput.value = plan;
    $('#register-business-name')?.focus();
  }

  async function registerBusiness(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
    const form = event.currentTarget;
    const message = $('#register-message');
    if (!form || !message) return;

    message.className = 'form-message';
    message.textContent = 'Criando sua marcenaria...';

    const payload = {
      business_name: $('#register-business-name')?.value.trim(),
      owner_name: $('#register-name')?.value.trim(),
      email: $('#register-email')?.value.trim().toLowerCase(),
      password: $('#register-password')?.value,
      plan_code: $('#register-plan')?.value || selectedPlan || 'starter',
    };

    try {
      const response = await fetch(`${apiBase}/auth/register-business`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Erro ${response.status}`);
      message.classList.add('success');
      message.textContent = 'Marcenaria criada com sucesso. Entre com seu e-mail para acessar o painel.';
      form.reset();
      setTimeout(() => {
        $('#login-email').value = payload.email;
        ['login', 'register', 'recovery', 'reset'].forEach((view) => {
          $(`#${view}-view`)?.classList.toggle('hidden', view !== 'login');
        });
        $('#login-password')?.focus();
      }, 900);
    } catch (error) {
      message.classList.add('error');
      message.textContent = error.message;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const form = $('#register-form');
    form?.addEventListener('submit', registerBusiness, true);

    document.querySelectorAll('[data-plan]').forEach((button) => {
      button.addEventListener('click', () => showRegister(button.dataset.plan || 'starter'));
    });

    const showRegisterButton = $('#show-register');
    showRegisterButton?.addEventListener('click', () => {
      selectedPlan = 'starter';
      const planInput = $('#register-plan');
      if (planInput) planInput.value = 'starter';
    });
  });
})();
