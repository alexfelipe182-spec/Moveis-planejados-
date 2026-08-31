(() => {
  const proposalStatusLabels = {
    analysis: 'Em análise',
    approved: 'Aprovado',
    sent: 'Enviado • aguardando cliente',
    accepted: 'Aceito pelo cliente',
    declined: 'Recusado pelo cliente',
    rejected: 'Rejeitado internamente',
    pending: 'Pendente',
    completed: 'Concluído',
  };

  const safe = value => escapeHtml(value ?? '—');
  const customerFor = quote => state.customers.find(item => item.id === quote.customer_id) || {};
  const customerName = quote => customerFor(quote).name || `Cliente #${quote.customer_id}`;
  const tenantName = () => state.tenant?.name || 'Sua Marcenaria';

  async function ensureTenant() {
    if (!state.tenant) state.tenant = await api('/tenant');
    return state.tenant;
  }

  function proposalHtml(quote) {
    const customer = customerFor(quote);
    const status = proposalStatusLabels[quote.status] || quote.status || '—';
    const date = quote.created_at ? new Date(quote.created_at).toLocaleDateString('pt-BR') : new Date().toLocaleDateString('pt-BR');
    const business = tenantName();
    return `<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Orçamento #${safe(quote.id)} | ${safe(business)}</title>
<style>
  *{box-sizing:border-box} body{font-family:Arial,sans-serif;margin:0;background:#f4f4f1;color:#20251f} .page{max-width:900px;margin:32px auto;background:#fff;padding:48px;border-radius:18px;box-shadow:0 12px 36px #0001} header{display:flex;justify-content:space-between;gap:24px;border-bottom:2px solid #2e4a35;padding-bottom:24px;margin-bottom:30px}.brand{font-size:26px;font-weight:700;color:#243d2b}.muted{color:#6c746c}.badge{display:inline-block;padding:7px 12px;border-radius:999px;background:#e6eee7;font-weight:700}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:24px 0}.card{border:1px solid #e1e5df;border-radius:12px;padding:18px}.card h3{margin:0 0 10px;font-size:14px;text-transform:uppercase;color:#687168}.description{white-space:pre-wrap}.total{margin-top:28px;padding:24px;border-radius:14px;background:#243d2b;color:white;display:flex;justify-content:space-between;align-items:center}.total strong{font-size:28px}.actions{margin:24px 0;text-align:right}.actions button{border:0;border-radius:10px;padding:12px 18px;font-weight:700;cursor:pointer}.print{background:#243d2b;color:white} footer{margin-top:32px;padding-top:20px;border-top:1px solid #ddd;font-size:13px;color:#697169}@media print{body{background:#fff}.page{box-shadow:none;margin:0;max-width:none;padding:24px}.actions{display:none}}@media(max-width:650px){.page{margin:0;padding:24px;border-radius:0}.grid{grid-template-columns:1fr}header{flex-direction:column}}
</style>
</head>
<body>
<main class="page">
<header><div><div class="brand">${safe(business)}</div><div class="muted">Móveis planejados • Projeto sob medida</div></div><div><strong>Orçamento #${safe(quote.id)}</strong><br><span class="muted">${safe(date)}</span><br><span class="badge">${safe(status)}</span></div></header>
<section class="grid"><div class="card"><h3>Cliente</h3><strong>${safe(customer.name || customerName(quote))}</strong><p class="muted">${safe(customer.email || '')}<br>${safe(customer.phone || '')}<br>${safe(customer.address || '')}</p></div><div class="card"><h3>Projeto</h3><div class="description">${safe(quote.description)}</div><p><strong>Medidas:</strong> ${safe(quote.measurements)}</p><p><strong>Materiais:</strong> ${safe(quote.materials)}</p></div></section>
<section class="card"><h3>Condições comerciais</h3><p>Status: <strong>${safe(status)}</strong></p><p class="muted">O valor considera o escopo descrito nesta proposta e pode ser ajustado após conferência final de medidas, materiais, ferragens, acabamento, prazo e condições de instalação.</p></section>
<div class="total"><span>Valor total da proposta</span><strong>${money(quote.total ?? quote.suggested_total)}</strong></div>
<div class="actions"><button class="print" onclick="window.print()">Imprimir / Salvar em PDF</button></div>
<footer>${safe(business)} • Proposta comercial gerada pela Multi-Marcenarias.</footer>
</main>
</body>
</html>`;
  }

  async function openQuoteProposal(quoteId) {
    const quote = state.rows.find(item => item.id === quoteId);
    if (!quote) return toast('Orçamento não encontrado.', 'error');
    try {
      await ensureTenant();
    } catch (error) {
      return toast(error.message, 'error');
    }
    const popup = window.open('', '_blank');
    if (!popup) return toast('Permita pop-ups para visualizar a proposta.', 'error');
    popup.opener = null;
    popup.document.open();
    popup.document.write(proposalHtml(quote));
    popup.document.close();
  }

  async function shareQuote(quoteId) {
    const quote = state.rows.find(item => item.id === quoteId);
    if (!quote) return toast('Orçamento não encontrado.', 'error');
    if (quote.status !== 'approved') return toast('A proposta precisa estar aprovada antes do envio.', 'error');
    const customer = customerFor(quote);
    const phone = String(customer.phone || '').replace(/\D/g, '');
    if (!phone) return toast('Cadastre o telefone do cliente antes de enviar.', 'error');

    try {
      await ensureTenant();
    } catch (error) {
      return toast(error.message, 'error');
    }

    const whatsapp = window.open('', '_blank');
    if (!whatsapp) return toast('Permita pop-ups para abrir o WhatsApp.', 'error');
    whatsapp.opener = null;

    try {
      await api(`/quotes/${quote.id}/shared`, { method: 'POST' });
      const message = `Olá, ${customer.name || 'cliente'}! Sua proposta da ${tenantName()} está pronta. Orçamento #${quote.id} no valor de ${money(quote.total ?? quote.suggested_total)}. Vou enviar o PDF da proposta nesta conversa.`;
      whatsapp.location.href = `https://wa.me/${phone}?text=${encodeURIComponent(message)}`;
      toast(`Proposta #${quote.id} marcada como enviada e registrada no histórico.`);
      await loadResource('quotes');
    } catch (error) {
      whatsapp.close();
      toast(error.message, 'error');
    }
  }

  function addProposalButtons() {
    const section = document.querySelector('#quotes');
    if (!section || section.classList.contains('hidden')) return;
    const rows = [...section.querySelectorAll('tbody tr')];
    let visibleRows = state.rows.filter(row => !state.search || Object.values(row).some(value => String(value ?? '').toLowerCase().includes(state.search.toLowerCase())));
    if (state.status) visibleRows = visibleRows.filter(row => row.status === state.status);
    rows.forEach((tr, index) => {
      const quote = visibleRows[index];
      const actions = tr.querySelector('.actions');
      if (!quote || !actions || actions.querySelector('[data-quote-proposal]')) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'small-btn';
      button.dataset.quoteProposal = String(quote.id);
      button.textContent = ['approved', 'sent', 'accepted', 'declined'].includes(quote.status) ? 'Proposta' : 'Visualizar';
      button.addEventListener('click', () => openQuoteProposal(quote.id));
      actions.prepend(button);
      if (quote.status === 'approved') {
        const share = document.createElement('button');
        share.type = 'button';
        share.className = 'small-btn';
        share.dataset.quoteShare = String(quote.id);
        share.textContent = 'WhatsApp';
        share.addEventListener('click', () => shareQuote(quote.id));
        actions.prepend(share);
      }
    });
  }

  const previousRenderResource = window.renderResource;
  window.renderResource = function(resource) {
    const result = previousRenderResource(resource);
    if (resource === 'quotes') addProposalButtons();
    return result;
  };

  window.openQuoteProposal = openQuoteProposal;
  window.shareQuote = shareQuote;
})();

(() => {
  const form = document.getElementById('register-form');
  if (!form || document.getElementById('register-business')) return;

  const nameInput = document.getElementById('register-name');
  const ownerLabel = nameInput?.closest('label');
  if (ownerLabel) {
    const businessLabel = document.createElement('label');
    businessLabel.setAttribute('for', 'register-business');
    businessLabel.innerHTML = 'Nome da marcenaria<input id="register-business" type="text" minlength="2" maxlength="160" required autocomplete="organization">';
    ownerLabel.parentNode.insertBefore(businessLabel, ownerLabel);
  }

  document.addEventListener('submit', async event => {
    if (event.target !== form) return;
    event.preventDefault();
    event.stopImmediatePropagation();

    const message = document.getElementById('register-message');
    const submit = form.querySelector('button[type="submit"]');
    const email = document.getElementById('register-email').value.trim().toLowerCase();
    message.className = 'form-message';
    message.textContent = '';
    submit.disabled = true;

    try {
      const response = await fetch(`${API}/auth/register-business`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          business_name: document.getElementById('register-business').value.trim(),
          owner_name: document.getElementById('register-name').value.trim(),
          email,
          password: document.getElementById('register-password').value,
          plan_code: 'starter',
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Erro ${response.status}`);
      message.classList.add('success');
      message.textContent = 'Marcenaria criada! Sua conta já possui acesso administrativo.';
      form.reset();
      const loginEmail = document.getElementById('login-email');
      if (loginEmail) loginEmail.value = email;
      setTimeout(() => window.showAuth?.('login'), 900);
    } catch (error) {
      message.classList.add('error');
      message.textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  }, true);
})();
