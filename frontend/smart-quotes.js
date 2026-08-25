(() => {
  const apiBase = window.API_BASE_URL || (location.hostname === 'localhost' ? 'http://localhost:8000/api/v1' : 'https://ideal-marcenaria-api.onrender.com/api/v1');
  const money = value => Number(value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

  function renderPanel(result) {
    let panel = document.querySelector('#smart-quote-panel');
    if (!panel) {
      panel = document.createElement('section');
      panel.id = 'smart-quote-panel';
      panel.className = 'smart-quote-panel';
      document.querySelector('.admin-main')?.prepend(panel);
    }
    const warnings = (result.warnings || []).map(x => `<li>${escapeHtml(x)}</li>`).join('') || '<li>Nenhum alerta financeiro.</li>';
    const recommendations = (result.recommendations || []).map(x => `<li>${escapeHtml(x)}</li>`).join('') || '<li>Nenhuma recomendação adicional.</li>';
    panel.innerHTML = `<div class="panel"><div class="panel-title"><div><span class="eyebrow">Inteligência de orçamento</span><h3>Análise automática</h3></div><span class="badge">Requer aprovação</span></div><div class="smart-quote-grid"><div><small>Custo base</small><strong>${money(result.base_cost)}</strong></div><div><small>Preço sugerido</small><strong>${money(result.suggested_total)}</strong></div><div><small>Margem</small><strong>${Number(result.profit_margin || 0).toFixed(2)}%</strong></div></div><div class="smart-quote-columns"><div><h4>Alertas</h4><ul>${warnings}</ul></div><div><h4>Recomendações</h4><ul>${recommendations}</ul></div></div></div>`;
  }

  function escapeHtml(value = '') { return String(value).replace(/[&<>'"]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c])); }

  window.analyzeSmartQuote = async function(payload) {
    const response = await fetch(`${apiBase}/quotes/estimate`, {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Erro ${response.status}`);
    renderPanel(data);
    return data;
  };
})();
