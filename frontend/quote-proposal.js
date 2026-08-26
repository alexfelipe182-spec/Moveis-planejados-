(() => {
  const proposalStatusLabels = {
    analysis: 'Em análise',
    approved: 'Aprovado',
    rejected: 'Recusado',
    pending: 'Pendente',
    completed: 'Concluído',
  };

  const safe = value => escapeHtml(value ?? '—');
  const customerName = quote => state.customers.find(item => item.id === quote.customer_id)?.name || `Cliente #${quote.customer_id}`;

  function proposalHtml(quote) {
    const customer = state.customers.find(item => item.id === quote.customer_id) || {};
    const status = proposalStatusLabels[quote.status] || quote.status || '—';
    const date = quote.created_at ? new Date(quote.created_at).toLocaleDateString('pt-BR') : new Date().toLocaleDateString('pt-BR');
    return `<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Orçamento #${safe(quote.id)} | Marcenaria Ideal</title>
<style>
  *{box-sizing:border-box} body{font-family:Arial,sans-serif;margin:0;background:#f4f4f1;color:#20251f} .page{max-width:900px;margin:32px auto;background:#fff;padding:48px;border-radius:18px;box-shadow:0 12px 36px #0001} header{display:flex;justify-content:space-between;gap:24px;border-bottom:2px solid #2e4a35;padding-bottom:24px;margin-bottom:30px}.brand{font-size:26px;font-weight:700;color:#243d2b}.muted{color:#6c746c}.badge{display:inline-block;padding:7px 12px;border-radius:999px;background:#e6eee7;font-weight:700}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:24px 0}.card{border:1px solid #e1e5df;border-radius:12px;padding:18px}.card h3{margin:0 0 10px;font-size:14px;text-transform:uppercase;color:#687168}.description{white-space:pre-wrap}.total{margin-top:28px;padding:24px;border-radius:14px;background:#243d2b;color:white;display:flex;justify-content:space-between;align-items:center}.total strong{font-size:28px}.actions{margin:24px 0;text-align:right}.actions button{border:0;border-radius:10px;padding:12px 18px;font-weight:700;cursor:pointer}.print{background:#243d2b;color:white} footer{margin-top:32px;padding-top:20px;border-top:1px solid #ddd;font-size:13px;color:#697169}@media print{body{background:#fff}.page{box-shadow:none;margin:0;max-width:none;padding:24px}.actions{display:none}}@media(max-width:650px){.page{margin:0;padding:24px;border-radius:0}.grid{grid-template-columns:1fr}header{flex-direction:column}}
</style>
</head>
<body>
<main class="page">
<header><div><div class="brand">Marcenaria Ideal</div><div class="muted">Móveis planejados • Projeto sob medida</div></div><div><strong>Orçamento #${safe(quote.id)}</strong><br><span class="muted">${safe(date)}</span><br><span class="badge">${safe(status)}</span></div></header>
<section class="grid"><div class="card"><h3>Cliente</h3><strong>${safe(customer.name || customerName(quote))}</strong><p class="muted">${safe(customer.email || '')}<br>${safe(customer.phone || '')}<br>${safe(customer.address || '')}</p></div><div class="card"><h3>Projeto</h3><div class="description">${safe(quote.description)}</div><p><strong>Medidas:</strong> ${safe(quote.measurements)}</p><p><strong>Materiais:</strong> ${safe(quote.materials)}</p></div></section>
<section class="grid"><div class="card"><h3>Custos do projeto</h3><p>Material: <strong>${money(quote.material_cost)}</strong></p><p>Ferragens: <strong>${money(quote.hardware_cost)}</strong></p><p>Mão de obra: <strong>${money(quote.labor_cost)}</strong></p><p>Acabamento: <strong>${money(quote.finishing_cost)}</strong></p></div><div class="card"><h3>Condições</h3><p>Margem aplicada: <strong>${safe(quote.profit_margin ?? 0)}%</strong></p><p>Status: <strong>${safe(status)}</strong></p><p class="muted">Valores calculados pelo sistema e sujeitos à validação final de medidas, materiais e condições comerciais.</p></div></section>
<div class="total"><span>Valor total do orçamento</span><strong>${money(quote.total ?? quote.suggested_total)}</strong></div>
<div class="actions"><button class="print" onclick="window.print()">Imprimir / Salvar em PDF</button></div>
<footer>Marcenaria Ideal • Proposta comercial gerada pelo painel administrativo.</footer>
</main>
</body>
</html>`;
  }

  function openQuoteProposal(quoteId) {
    const quote = state.rows.find(item => item.id === quoteId);
    if (!quote) return toast('Orçamento não encontrado.', 'error');
    const popup = window.open('', '_blank', 'noopener');
    if (!popup) return toast('Permita pop-ups para visualizar a proposta.', 'error');
    popup.document.open();
    popup.document.write(proposalHtml(quote));
    popup.document.close();
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
      button.textContent = quote.status === 'approved' ? 'Proposta' : 'Visualizar';
      button.addEventListener('click', () => openQuoteProposal(quote.id));
      actions.prepend(button);
    });
  }

  const previousRenderResource = window.renderResource;
  window.renderResource = function(resource) {
    const result = previousRenderResource(resource);
    if (resource === 'quotes') addProposalButtons();
    return result;
  };

  window.openQuoteProposal = openQuoteProposal;
})();
