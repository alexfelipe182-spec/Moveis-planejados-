(() => {
  const moneyBRL = value => Number(value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const esc = value => String(value ?? '').replace(/[&<>'\"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','\"':'&quot;'}[c]));

  window.openSmartQuote = async () => {
    const customers = await api('/customers?limit=100');
    const modal = document.querySelector('#modal');
    const content = document.querySelector('#modal-content');
    if (!modal || !content) return toast('Modal de orçamento não encontrado.', 'error');
    content.innerHTML = `<div class="smart-quote-panel"><div class="panel-title"><div><span class="eyebrow">IA + Automação</span><h3>Novo orçamento inteligente</h3></div></div><form id="smart-quote-form" class="form-grid"><label>Cliente<select name="customer_id" required><option value="">Selecione...</option>${customers.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('')}</select></label><label>Descrição<textarea name="description" required minlength="3" maxlength="3000"></textarea></label><label>Medidas<textarea name="measurements" maxlength="2000"></textarea></label><label>Materiais<textarea name="materials" maxlength="2000"></textarea></label><label>Material (R$)<input name="material_cost" type="number" min="0" step="0.01" value="0" required></label><label>Ferragens (R$)<input name="hardware_cost" type="number" min="0" step="0.01" value="0" required></label><label>Mão de obra (R$)<input name="labor_cost" type="number" min="0" step="0.01" value="0" required></label><label>Acabamento (R$)<input name="finishing_cost" type="number" min="0" step="0.01" value="0" required></label><label>Margem de lucro (%)<input name="profit_margin" type="number" min="0" max="100" step="0.01" value="30" required></label><div class="form-actions"><button class="btn secondary" type="button" id="smart-quote-cancel">Cancelar</button><button class="btn primary" type="submit">Calcular e analisar com IA</button></div></form><div id="smart-quote-result" class="hidden"></div></div>`;
    modal.classList.remove('hidden');
    document.querySelector('#smart-quote-cancel').onclick = closeModal;
    document.querySelector('#smart-quote-form').onsubmit = async event => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(event.currentTarget));
      data.customer_id = Number(data.customer_id);
      ['material_cost','hardware_cost','labor_cost','finishing_cost','profit_margin'].forEach(k => data[k] = Number(data[k]));
      const button = event.currentTarget.querySelector('button[type="submit"]');
      button.disabled = true; button.textContent = 'Analisando...';
      try {
        const quote = await api('/quotes', { method: 'POST', body: data });
        const result = document.querySelector('#smart-quote-result');
        result.classList.remove('hidden');
        result.innerHTML = `<div class="ai-result"><h3>🤖 Análise do orçamento</h3><div class="stats"><div class="stat"><span>Custo base</span><strong>${moneyBRL(Number(quote.material_cost)+Number(quote.hardware_cost)+Number(quote.labor_cost)+Number(quote.finishing_cost))}</strong></div><div class="stat"><span>Preço sugerido</span><strong>${moneyBRL(quote.suggested_total)}</strong></div><div class="stat"><span>Margem</span><strong>${esc(quote.profit_margin)}%</strong></div></div><div class="panel"><p><strong>Status:</strong> ${esc(quote.status)}</p><p><strong>Análise IA:</strong></p><pre class="ai-text">${esc(quote.ai_analysis || 'Análise automática indisponível. O cálculo financeiro foi preservado.')}</pre><p class="approval-note">🔐 O orçamento precisa de aprovação da marcenaria.</p></div><div class="form-actions"><button class="btn primary" id="smart-quote-done">Concluir</button></div></div>`;
        document.querySelector('#smart-quote-done').onclick = () => { closeModal(); loadResource('quotes'); };
        event.currentTarget.classList.add('hidden');
      } catch (error) { toast(error.message, 'error'); button.disabled = false; button.textContent = 'Calcular e analisar com IA'; }
    };
  };

  const originalCreateItem = window.createItem;
  window.createItem = resource => resource === 'quotes'
    ? window.openSmartQuote()
    : originalCreateItem(resource);
})();
