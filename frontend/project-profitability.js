(() => {
  const healthLabels = {
    healthy: ['Saudável', 'success'],
    attention: ['Atenção', 'warning'],
    critical: ['Crítica', 'warning'],
    loss: ['Prejuízo', 'danger'],
  };

  const formatMoney = value => Number(value || 0).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  });
  const formatPercent = value => `${Number(value || 0).toLocaleString('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`;
  const escapeValue = value => String(value ?? '').replace(/[&<>'\"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '\"': '&quot;',
  })[character]);

  function installStyles() {
    if (document.querySelector('#mm-profitability-style')) return;
    const style = document.createElement('style');
    style.id = 'mm-profitability-style';
    style.textContent = `
      .mm-profitability-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:18px}
      .mm-profitability-head p{margin:5px 0 0;color:#59665f}
      .mm-profitability-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
      .mm-profitability-card{padding:16px;border:1px solid rgba(15,92,62,.13);border-radius:14px;background:#fbfdfb}
      .mm-profitability-card span{display:block;color:#59665f;font-size:.78rem;font-weight:800;text-transform:uppercase;letter-spacing:.04em}
      .mm-profitability-card strong{display:block;margin-top:7px;color:#111827;font-size:1.32rem;font-weight:850}
      .mm-profitability-card small{display:block;margin-top:4px;color:#6b7280}
      .mm-profitability-note{margin-top:16px;padding:14px 16px;border-radius:12px;background:#f2f8f4;color:#32463a;line-height:1.5}
      .mm-profitability-note strong{color:#163c29}
      body.dark .mm-profitability-card{background:#101815;border-color:rgba(137,210,169,.18)}
      body.dark .mm-profitability-card span,body.dark .mm-profitability-card small{color:#cbd5ce}
      body.dark .mm-profitability-card strong{color:#f8fafc}
      body.dark .mm-profitability-note{background:#13251b;color:#d7e7dc}
      body.dark .mm-profitability-note strong{color:#f1fff6}
      @media(max-width:760px){.mm-profitability-grid{grid-template-columns:1fr 1fr}.mm-profitability-head{flex-direction:column}}
      @media(max-width:430px){.mm-profitability-grid{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
  }

  function metric(label, value, detail = '') {
    return `<article class="mm-profitability-card"><span>${escapeValue(label)}</span><strong>${escapeValue(value)}</strong>${detail ? `<small>${escapeValue(detail)}</small>` : ''}</article>`;
  }

  async function openProjectProfitability(projectId) {
    if (typeof api !== 'function') return;
    installStyles();
    const button = document.querySelector(`[data-project-profitability="${projectId}"]`);
    const previousLabel = button?.textContent;
    if (button) {
      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
      button.textContent = 'Calculando...';
    }

    try {
      const data = await api(`/projects/${projectId}/profitability`);
      const [healthLabel, healthTone] = healthLabels[data.health] || ['Em análise', 'warning'];
      const variation = `${formatMoney(data.cost_variance)} · ${formatPercent(data.cost_variance_percent)}`;
      const title = document.querySelector('#modal-title');
      const form = document.querySelector('#item-form');
      const modal = document.querySelector('#modal');
      if (!title || !form || !modal) throw new Error('Janela de rentabilidade indisponível.');

      title.textContent = `Rentabilidade — Projeto #${projectId}`;
      form.innerHTML = `
        <div class="mm-profitability-head">
          <div><span class="eyebrow">Resultado do projeto</span><h3>Orçamento #${escapeValue(data.quote_id)}</h3><p>Comparação entre o valor vendido e os custos lançados.</p></div>
          <span class="badge ${escapeValue(healthTone)}">${escapeValue(healthLabel)}</span>
        </div>
        <div class="mm-profitability-grid">
          ${metric('Valor vendido', formatMoney(data.sold_total), 'Receita do orçamento aceito')}
          ${metric('Custo previsto', formatMoney(data.expected_cost), 'Base usada na formação do preço')}
          ${metric('Custo real lançado', formatMoney(data.real_cost), 'Somente custos registrados no projeto')}
          ${metric('Lucro apurado', formatMoney(data.real_profit), 'Venda menos custos lançados')}
          ${metric('Margem apurada', formatPercent(data.real_margin_percent), 'Com os custos registrados até agora')}
          ${metric('Variação do custo', variation, 'Custo real menos custo previsto')}
        </div>
        <div class="mm-profitability-note"><strong>Importante:</strong> a rentabilidade só é definitiva quando todos os custos reais do projeto estiverem lançados. Custos faltantes podem deixar o lucro e a margem artificialmente altos.</div>
        <div class="modal-actions"><button type="button" class="btn secondary" onclick="closeModal()">Fechar</button></div>`;
      modal.classList.remove('hidden');
      modal.setAttribute('aria-hidden', 'false');
    } catch (error) {
      toast(error.message, 'error');
    } finally {
      if (button?.isConnected) {
        button.disabled = false;
        button.removeAttribute('aria-busy');
        button.textContent = previousLabel || 'Rentabilidade';
      }
    }
  }

  if (typeof rowActions === 'function') {
    const previousRowActions = rowActions;
    rowActions = function(resource, row) {
      let html = previousRowActions(resource, row);
      if (resource === 'projects' && row?.quote_id != null && !html.includes('data-project-profitability')) {
        html += `<button class="small-btn" type="button" data-project-profitability="${Number(row.id)}" onclick="openProjectProfitability(${Number(row.id)})">Rentabilidade</button>`;
      }
      return html;
    };
  }

  window.openProjectProfitability = openProjectProfitability;
})();
