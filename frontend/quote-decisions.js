(() => {
  const decisionLabels = { approved: 'Aprovar', rejected: 'Rejeitar' };
  const commercialLabels = { accepted: 'Cliente aceitou', declined: 'Cliente recusou' };

  async function decideQuote(quoteId, decision) {
    if (!decisionLabels[decision]) throw new Error('Decisão de orçamento inválida.');
    const action = decisionLabels[decision].toLowerCase();
    if (!confirm(`${decisionLabels[decision]} o orçamento #${quoteId}?`)) return;
    try {
      await api(`/quotes/${quoteId}/decision`, { method: 'PATCH', body: { status: decision } });
      toast(`Orçamento #${quoteId} ${action === 'aprovar' ? 'aprovado' : 'rejeitado'} com sucesso.`);
      await loadResource('quotes');
    } catch (error) {
      toast(error.message, 'error');
    }
  }

  async function setCommercialStatus(quoteId, status) {
    if (!commercialLabels[status]) throw new Error('Status comercial inválido.');
    if (!confirm(`${commercialLabels[status]} na proposta #${quoteId}?`)) return;
    try {
      await api(`/quotes/${quoteId}/commercial-status`, { method: 'PATCH', body: { status } });
      toast(`Resposta do cliente registrada na proposta #${quoteId}.`);
      await loadResource('quotes');
    } catch (error) {
      toast(error.message, 'error');
    }
  }

  function button(text, className, dataset, onClick) {
    const element = document.createElement('button');
    element.type = 'button';
    element.className = className;
    Object.entries(dataset).forEach(([key, value]) => { element.dataset[key] = value; });
    element.textContent = text;
    element.addEventListener('click', onClick);
    return element;
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
      if (!quote || !actions || actions.querySelector('[data-quote-decision], [data-commercial-status]')) return;

      if (quote.status === 'analysis') {
        actions.prepend(button('Rejeitar', 'small-btn danger', { quoteDecision: 'rejected' }, () => decideQuote(quote.id, 'rejected')));
        actions.prepend(button('Aprovar', 'small-btn', { quoteDecision: 'approved' }, () => decideQuote(quote.id, 'approved')));
      }

      if (quote.status === 'sent') {
        actions.prepend(button('Cliente recusou', 'small-btn danger', { commercialStatus: 'declined' }, () => setCommercialStatus(quote.id, 'declined')));
        actions.prepend(button('Cliente aceitou', 'small-btn', { commercialStatus: 'accepted' }, () => setCommercialStatus(quote.id, 'accepted')));
      }
    });
  }

  const originalRenderResource = window.renderResource;
  window.renderResource = function(resource) {
    const result = originalRenderResource(resource);
    if (resource === 'quotes') addDecisionButtons();
    return result;
  };

  window.decideQuote = decideQuote;
  window.setQuoteCommercialStatus = setCommercialStatus;
})();
