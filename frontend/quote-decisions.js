(() => {
  const decisionLabels = { approved: 'Aprovar', rejected: 'Rejeitar' };

  async function decideQuote(quoteId, decision) {
    if (!decisionLabels[decision]) throw new Error('Decisão de orçamento inválida.');
    const action = decisionLabels[decision].toLowerCase();
    if (!confirm(`${decisionLabels[decision]} o orçamento #${quoteId}?`)) return;
    try {
      await api(`/quotes/${quoteId}/decision`, { method: 'PATCH', body: { decision } });
      toast(`Orçamento #${quoteId} ${action === 'aprovar' ? 'aprovado' : 'rejeitado'} com sucesso.`);
      await loadResource('quotes');
    } catch (error) {
      toast(error.message, 'error');
    }
  }

  function addDecisionButtons() {
    const section = document.querySelector('#quotes');
    if (!section || section.classList.contains('hidden')) return;
    const rows = [...section.querySelectorAll('tbody tr')];
    let visibleRows = state.rows.filter(row => !state.search || Object.values(row).some(value => String(value ?? '').toLowerCase().includes(state.search.toLowerCase())));
    if (state.status) visibleRows = visibleRows.filter(row => row.status === state.status);
    rows.forEach((tr, index) => {
      const quote = visibleRows[index];
      const actions = tr.querySelector('.actions');
      if (!quote || !actions || actions.querySelector('[data-quote-decision]')) return;
      if (!['analysis', 'pending'].includes(quote.status)) return;
      const approve = document.createElement('button');
      approve.type = 'button';
      approve.className = 'small-btn';
      approve.dataset.quoteDecision = 'approved';
      approve.textContent = 'Aprovar';
      approve.addEventListener('click', () => decideQuote(quote.id, 'approved'));
      const reject = document.createElement('button');
      reject.type = 'button';
      reject.className = 'small-btn danger';
      reject.dataset.quoteDecision = 'rejected';
      reject.textContent = 'Rejeitar';
      reject.addEventListener('click', () => decideQuote(quote.id, 'rejected'));
      actions.prepend(reject);
      actions.prepend(approve);
    });
  }

  const originalRenderResource = window.renderResource;
  window.renderResource = function(resource) {
    const result = originalRenderResource(resource);
    if (resource === 'quotes') addDecisionButtons();
    return result;
  };

  window.decideQuote = decideQuote;
})();
