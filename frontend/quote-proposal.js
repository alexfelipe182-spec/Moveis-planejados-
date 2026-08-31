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
  const pendingShares = new Set();
  function whatsappNumber(value) {
    const digits = String(value || '').replace(/\D/g, '');
    if (/^\d{10,11}$/.test(digits)) return '55' + digits;
    return /^55\d{10,11}$/.test(digits) ? digits : '';
  }

  function proposalHtml(quote, items, customer) {
    const status = proposalStatusLabels[quote.status] || quote.status || '—';
    const date = quote.created_at ? new Date(quote.created_at).toLocaleDateString('pt-BR') : new Date().toLocaleDateString('pt-BR');
    const demonstration = String(quote.description || '').startsWith('[DEMONSTRAÇÃO]');
    const draft = !['approved', 'sent', 'accepted', 'completed'].includes(quote.status);
    const notices = [
      demonstration ? 'DEMONSTRAÇÃO — dados fictícios e valores ilustrativos. Não utilizar como proposta real.' : '',
      draft ? 'NÃO APROVADA — versão para conferência interna; não enviar como proposta aprovada.' : '',
    ].filter(Boolean).map(text => '<p class="notice">' + safe(text) + '</p>').join('');
    const itemRows = items.map(item => {
      const dimensions = [item.width, item.height, item.depth].every(value => value != null)
        ? '<br><small>Medidas (L × A × P): ' + [item.width, item.height, item.depth].map(safe).join(' × ') + '</small>' : '';
      return '<tr><td><strong>' + safe(item.name) + '</strong><div class="description">' + safe(item.description || '') + '</div>' + dimensions
        + '</td><td>' + safe(item.quantity) + '</td><td>' + money(item.unit_price) + '</td><td>' + money(item.subtotal) + '</td></tr>';
    }).join('');
    return `<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Orçamento #${safe(quote.id)} | Multi-Marcenarias</title>
<style>
  *{box-sizing:border-box} body{font-family:Arial,sans-serif;margin:0;background:#f4f4f1;color:#20251f} .page{max-width:900px;margin:32px auto;background:#fff;padding:48px;border-radius:18px;box-shadow:0 12px 36px #0001} header{display:flex;justify-content:space-between;gap:24px;border-bottom:2px solid #2e4a35;padding-bottom:24px;margin-bottom:30px}.brand{font-size:26px;font-weight:700;color:#243d2b}.muted{color:#6c746c}.badge{display:inline-block;padding:7px 12px;border-radius:999px;background:#e6eee7;font-weight:700}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:24px 0}.card{border:1px solid #e1e5df;border-radius:12px;padding:18px}.card h3{margin:0 0 10px;font-size:14px;text-transform:uppercase;color:#687168}.description{white-space:pre-wrap}.total{margin-top:28px;padding:24px;border-radius:14px;background:#243d2b;color:white;display:flex;justify-content:space-between;align-items:center}.total strong{font-size:28px}.actions{margin:24px 0;text-align:right}.actions button{border:0;border-radius:10px;padding:12px 18px;font-weight:700;cursor:pointer}.print{background:#243d2b;color:white} footer{margin-top:32px;padding-top:20px;border-top:1px solid #ddd;font-size:13px;color:#697169}@media print{body{background:#fff}.page{box-shadow:none;margin:0;max-width:none;padding:24px}.actions{display:none}}@media(max-width:650px){.page{margin:0;padding:24px;border-radius:0}.grid{grid-template-columns:1fr}header{flex-direction:column}}
</style>
<style>
  .brand{color:#075c72}header{border-color:#075c72}.badge{background:#e0edf3;color:#122637}
  .total,.print{background:#075c72}.notice{border:1px solid #94732a;border-left:4px solid #94732a;background:#fff9e8;color:#46360e;padding:14px;line-height:1.5}
  .items-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;margin-top:16px;font-size:14px}
  caption{text-align:left;font-weight:700;font-size:16px;padding:12px 0}th,td{text-align:left;vertical-align:top;padding:12px 8px;border-bottom:1px solid #d1dce2}
  th{background:#edf4f8}td:not(:first-child){white-space:nowrap}td:first-child{min-width:180px}
  .description,.brand,.card{overflow-wrap:anywhere}.total{flex-wrap:wrap;gap:12px}tr{break-inside:avoid}
  @media print{.items-wrap{overflow:visible}thead{display:table-header-group}.notice,.total{break-inside:avoid}td:first-child{min-width:0}}
</style>
</head>
<body>
<main class="page">
${notices}
<header><div><div class="brand">Multi-Marcenarias</div><div class="muted">Móveis planejados • Projeto sob medida</div></div><div><strong>Orçamento #${safe(quote.id)}</strong><br><span class="muted">${safe(date)}</span><br><span class="badge">${safe(status)}</span></div></header>
<section class="grid"><div class="card"><h3>Cliente</h3><strong>${safe(customer.name || customerName(quote))}</strong><p class="muted">${safe(customer.email || '')}<br>${safe(customer.phone || '')}<br>${safe(customer.address || '')}</p></div><div class="card"><h3>Projeto</h3><div class="description">${safe(quote.description)}</div><p><strong>Medidas:</strong> ${safe(quote.measurements)}</p><p><strong>Materiais:</strong> ${safe(quote.materials)}</p></div></section>
<section class="items-wrap">${items.length ? '<table><caption>Composição do orçamento</caption><thead><tr><th scope="col">Móvel / serviço</th><th scope="col">Quantidade</th><th scope="col">Unitário</th><th scope="col">Subtotal</th></tr></thead><tbody>' + itemRows + '</tbody></table>' : '<p class="muted">Sem itens detalhados. Consulte o escopo descrito acima.</p>'}</section>
<section class="card"><h3>Condições comerciais</h3><p>Status: <strong>${safe(status)}</strong></p><p class="muted">O valor considera o escopo descrito nesta proposta e pode ser ajustado após conferência final de medidas, materiais, ferragens, acabamento, prazo e condições de instalação.</p><p class="muted">Prazo, pagamento e validade devem ser acordados antes do envio ao cliente.</p></section>
<div class="total"><span>Valor total da proposta</span><strong>${money(quote.total ?? quote.suggested_total)}</strong></div>
<div class="actions"><button class="print" onclick="window.print()">Imprimir / Salvar em PDF</button></div>
<footer>Multi-Marcenarias • Proposta comercial gerada pelo painel administrativo.</footer>
</main>
</body>
</html>`;
  }

  async function openQuoteProposal(quoteId) {
    if (!state.rows.some(item => item.id === quoteId)) return toast('Orçamento não encontrado.', 'error');
    const popup = window.open('', '_blank');
    if (!popup) return toast('Permita pop-ups para visualizar a proposta.', 'error');
    popup.opener = null;
    popup.document.title = 'Carregando proposta | Multi-Marcenarias';
    popup.document.body.textContent = 'Carregando proposta e itens...';
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), 20000);
    try {
      const [quote, items] = await Promise.all([
        api('/quotes/' + quoteId, { signal: controller.signal }),
        api('/quotes/' + quoteId + '/items', { signal: controller.signal }),
      ]);
      if (!Array.isArray(items)) throw new Error('Não foi possível conferir os itens da proposta.');
      const totalCents = Math.round(Number(quote.total ?? quote.suggested_total) * 100);
      const itemCents = items.map(item => Math.round(Number(item.subtotal) * 100));
      if (!Number.isSafeInteger(totalCents) || itemCents.some(value => !Number.isSafeInteger(value))
          || (items.length && itemCents.reduce((sum, value) => sum + value, 0) !== totalCents)) {
        throw new Error('Os itens e o total precisam ser conferidos novamente.');
      }
      // A quote can have been edited since the list was loaded. Never print stale client details.
      const customer = await api('/customers/' + quote.customer_id, { signal: controller.signal });
      if (popup.closed) return;
      popup.document.open();
      popup.document.write(proposalHtml(quote, items, customer));
      popup.document.close();
    } catch (error) {
      const message = error.name === 'AbortError' ? 'O carregamento demorou demais. Feche esta janela e tente novamente.'
        : 'Não foi possível carregar a proposta completa. Feche esta janela e tente novamente.';
      if (!popup.closed) popup.document.body.textContent = message;
      toast(message, 'error');
    } finally {
      clearTimeout(deadline);
    }
  }

  async function shareQuote(quoteId) {
    const listedQuote = state.rows.find(item => item.id === quoteId);
    if (!listedQuote) return toast('Orçamento não encontrado.', 'error');
    if (listedQuote.status !== 'approved') return toast('A proposta precisa estar aprovada antes do envio.', 'error');
    if (pendingShares.has(quoteId)) return toast('O compartilhamento deste orçamento já está em andamento.', 'error');
    pendingShares.add(quoteId);

    const whatsapp = window.open('', '_blank');
    if (!whatsapp) { pendingShares.delete(quoteId); return toast('Permita pop-ups para abrir o WhatsApp.', 'error'); }
    whatsapp.opener = null;
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), 20000);
    try {
      const quote = await api(`/quotes/${quoteId}`, { signal:controller.signal });
      if (quote.status !== 'approved') throw new Error('A proposta não está mais aprovada. Atualize a lista antes de enviar.');
      const customer = await api(`/customers/${quote.customer_id}`, { signal:controller.signal });
      const phone = whatsappNumber(customer.phone);
      if (!phone) throw new Error('Cadastre um telefone brasileiro válido para o cliente antes de enviar.');
      if (whatsapp.closed) throw new Error('A janela do WhatsApp foi fechada. O envio não foi registrado.');
      const message = `Olá, ${customer.name || 'cliente'}! Sua proposta da Multi-Marcenarias está pronta. Orçamento #${quote.id} no valor de ${money(quote.total ?? quote.suggested_total)}. Vou enviar o PDF da proposta nesta conversa.`;
      whatsapp.location.href = `https://wa.me/${phone}?text=${encodeURIComponent(message)}`;
      await api(`/quotes/${quote.id}/shared`, { method: 'POST', signal:controller.signal });
      toast(`Proposta #${quote.id} marcada como enviada e registrada no histórico.`);
      await loadResource('quotes');
    } catch (error) {
      whatsapp.close();
      toast(error.name === 'AbortError' ? 'O carregamento demorou demais. Tente compartilhar novamente.' : error.message, 'error');
    } finally {
      clearTimeout(deadline); pendingShares.delete(quoteId);
    }
  }

  function addProposalButtons() {
    const section = document.querySelector('#quotes');
    if (!section || section.classList.contains('hidden')) return;
    const rows = [...section.querySelectorAll('tbody tr')];
    const visibleRows = state.rows;
    rows.forEach(tr => {
      const quote = visibleRows.find(item => String(item.id) === tr.dataset.rowId);
      const actions = tr.querySelector('.actions');
      if (!quote || !actions || actions.querySelector('[data-quote-proposal]')) return;
      const editable = ['pending', 'analysis'].includes(quote.status);
      if (!editable) actions.querySelector(`button[onclick="editItem('quotes',${quote.id})"]`)?.remove();
      const items = document.createElement('button');
      items.type = 'button'; items.className = 'small-btn'; items.dataset.quoteItems = String(quote.id);
      items.textContent = editable ? 'Itens' : 'Ver itens';
      items.addEventListener('click', () => window.openQuoteItems(quote.id, quote.description).catch(error => toast(error.message, 'error')));
      actions.prepend(items);
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
