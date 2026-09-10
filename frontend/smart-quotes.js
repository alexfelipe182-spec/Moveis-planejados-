(() => {
  if (window.multiSmartQuotesReady) return;
  window.multiSmartQuotesReady = true;
  const money = value => Number(value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const escapeHtml = (value = '') => String(value).replace(/[&<>'\"]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c]));

  function field(root, name) {
    return root?.querySelector?.(`[name="${name}"]`) || null;
  }

  function fieldValue(root, name) {
    return field(root, name)?.value ?? '';
  }

  function numberValue(root, name) {
    return Number(fieldValue(root, name) || 0);
  }

  function setButtonBusy(button, busy, busyLabel, idleLabel) {
    if (!button) return;
    button.disabled = busy;
    button.setAttribute?.('aria-busy', busy ? 'true' : 'false');
    button.textContent = busy ? busyLabel : idleLabel;
  }

  function interpretationLabel(source) {
    if (source === 'openai') return 'IA OpenAI ativa';
    if (source === 'assisted_local') return 'Modo assistido · fallback local';
    return 'Cálculo protegido';
  }

  function renderPanel(result, target = null) {
    let panel = target || document.querySelector('#smart-quote-result');
    if (!panel) {
      panel = document.createElement('section');
      panel.id = 'smart-quote-result';
      panel.className = 'smart-quote-panel';
      document.querySelector('.admin-main')?.prepend(panel);
    }
    const warnings = (result.warnings || []).map(x => `<li>${escapeHtml(x)}</li>`).join('') || '<li>Nenhum alerta financeiro.</li>';
    const recommendations = (result.recommendations || []).map(x => `<li>${escapeHtml(x)}</li>`).join('') || '<li>Nenhuma recomendação adicional.</li>';
    const source = interpretationLabel(result.interpretation_source);
    panel.innerHTML = `<div class="panel"><div class="panel-title"><div><span class="eyebrow">Inteligência de orçamento</span><h3>Análise automática</h3></div><div class="smart-result-badges"><span class="badge">${escapeHtml(source)}</span><span class="badge">Requer aprovação</span></div></div><div class="smart-quote-grid"><div><small>Custo base</small><strong>${money(result.base_cost)}</strong></div><div><small>Preço sugerido</small><strong>${money(result.suggested_total)}</strong></div><div><small>Margem</small><strong>${Number(result.profit_margin || 0).toFixed(2)}%</strong></div></div><div class="smart-quote-columns"><div><h4>Alertas</h4><ul>${warnings}</ul></div><div><h4>Recomendações</h4><ul>${recommendations}</ul></div></div></div>`;
  }

  async function analyze(payload) {
    const data = await api('/quotes/estimate', { method: 'POST', body: payload });
    renderPanel(data);
    return data;
  }
  window.analyzeSmartQuote = analyze;

  async function createDraft(payload) {
    return api('/quotes/draft', { method: 'POST', body: payload });
  }
  window.createSmartQuoteDraft = createDraft;

  async function openQuoteItems(quoteId, quoteDescription = '') {
    let items = await api(`/quotes/${quoteId}/items`);
    const form = document.querySelector('#item-form');
    document.querySelector('#modal-title').textContent = `Itens do orçamento #${quoteId}`;
    form.innerHTML = `<div class="smart-quote-create"><div class="smart-quote-intro"><span class="eyebrow">Composição do orçamento</span><h3>${escapeHtml(quoteDescription || 'Móveis planejados')}</h3><p>Adicione ou edite cada móvel. Subtotais e o total geral são recalculados automaticamente.</p></div><div id="quote-items-list"></div><div class="cost-grid"><label>Nome do móvel<input id="qi-name" type="text" maxlength="200" placeholder="Ex.: Armário de cozinha" required></label><label>Quantidade<input id="qi-quantity" type="number" min="0.01" step="0.01" value="1" inputmode="decimal"></label><label>Medidas (L × A × P)<input id="qi-measurements" type="text" maxlength="100" placeholder="Ex.: 2,40 × 2,10 × 0,60m"></label><label>Preço unitário<input id="qi-price" type="number" min="0" step="0.01" value="0" inputmode="decimal"></label></div><div class="smart-result-card"><div><small>Total dos itens</small><strong id="quote-items-total">R$ 0,00</strong></div><div><small>Orçamento</small><strong>#${quoteId}</strong></div></div><div class="modal-actions"><button type="button" class="btn secondary" id="quote-items-close">Fechar</button><button type="button" class="btn primary" id="quote-item-add">+ Adicionar móvel</button></div></div>`;

    const list = form.querySelector('#quote-items-list');
    const totalEl = form.querySelector('#quote-items-total');
    const measurementText = item => [item.width, item.height, item.depth]
      .filter(v => v !== null && v !== undefined)
      .map(v => String(v).replace('.', ','))
      .join(' × ');

    const renderItems = rows => {
      const total = rows.reduce((sum, item) => sum + Number(item.subtotal || 0), 0);
      totalEl.textContent = money(total);
      list.innerHTML = rows.length
        ? rows.map(item => `<div class="panel" data-item-id="${item.id}" style="margin-bottom:10px"><div class="panel-title"><div><strong>${escapeHtml(item.name)}</strong><small>${Number(item.quantity)} × ${money(item.unit_price)}${measurementText(item) ? ` • ${escapeHtml(measurementText(item))}` : ''}${item.description ? ` • ${escapeHtml(item.description)}` : ''}</small></div><strong>${money(item.subtotal)}</strong><div><button type="button" class="btn secondary quote-item-edit" data-id="${item.id}">Editar</button><button type="button" class="btn secondary quote-item-delete" data-id="${item.id}">Excluir</button></div></div></div>`).join('')
        : '<p class="muted">Nenhum móvel adicionado ainda.</p>';
    };
    renderItems(items);

    const clearForm = () => {
      form.querySelector('#qi-name').value = '';
      form.querySelector('#qi-quantity').value = '1';
      form.querySelector('#qi-measurements').value = '';
      form.querySelector('#qi-price').value = '0';
    };

    form.querySelector('#quote-item-add').addEventListener('click', async () => {
      if (form.querySelector('#quote-item-add').disabled) return;
      const name = form.querySelector('#qi-name').value.trim();
      const quantity = Number(form.querySelector('#qi-quantity').value || 0);
      const unit_price = Number(form.querySelector('#qi-price').value || 0);
      const raw = form.querySelector('#qi-measurements').value.trim();
      if (!name || quantity <= 0 || unit_price < 0) {
        toast('Informe nome, quantidade e preço unitário.', 'error');
        return;
      }
      const button = form.querySelector('#quote-item-add');
      setButtonBusy(button, true, 'Adicionando...', '+ Adicionar móvel');
      try {
        const parts = raw.replace(/,/g, '.').split(/[x×]/).map(x => Number(x.trim())).filter(Number.isFinite);
        const item = await api(`/quotes/${quoteId}/items`, { method: 'POST', body: { name, quantity, unit_price, width: parts[0] || null, height: parts[1] || null, depth: parts[2] || null } });
        items.push(item);
        renderItems(items);
        clearForm();
        toast('Móvel adicionado. Total atualizado automaticamente.');
      } catch (err) {
        toast(err.message, 'error');
      } finally {
        setButtonBusy(button, false, 'Adicionando...', '+ Adicionar móvel');
      }
    });

    list.addEventListener('click', async event => {
      const editButton = event.target.closest('.quote-item-edit');
      if (editButton) {
        const item = items.find(x => String(x.id) === String(editButton.dataset.id));
        if (!item) return;
        const row = editButton.closest('[data-item-id]');
        row.innerHTML = `<div class="form-grid"><label>Nome<input class="edit-name" value="${escapeHtml(item.name)}" maxlength="200"></label><label>Quantidade<input class="edit-quantity" type="number" min="0.01" step="0.01" value="${Number(item.quantity)}"></label><label>Medidas L × A × P<input class="edit-measurements" value="${escapeHtml(measurementText(item))}" maxlength="100"></label><label>Preço unitário<input class="edit-price" type="number" min="0" step="0.01" value="${Number(item.unit_price)}"></label></div><div class="modal-actions"><button type="button" class="btn secondary quote-item-cancel">Cancelar</button><button type="button" class="btn primary quote-item-save">Salvar alterações</button></div>`;
        row.querySelector('.quote-item-cancel').addEventListener('click', () => renderItems(items));
        row.querySelector('.quote-item-save').addEventListener('click', async () => {
          if (row.querySelector('.quote-item-save').disabled) return;
          const name = row.querySelector('.edit-name').value.trim();
          const quantity = Number(row.querySelector('.edit-quantity').value || 0);
          const unit_price = Number(row.querySelector('.edit-price').value || 0);
          const raw = row.querySelector('.edit-measurements').value.trim();
          if (!name || quantity <= 0 || unit_price < 0) {
            toast('Informe nome, quantidade e preço unitário.', 'error');
            return;
          }
          const parts = raw.replace(/,/g, '.').split(/[x×]/).map(x => Number(x.trim())).filter(Number.isFinite);
          const save = row.querySelector('.quote-item-save');
          setButtonBusy(save, true, 'Salvando...', 'Salvar alterações');
          try {
            const updated = await api(`/quotes/${quoteId}/items/${item.id}`, { method: 'PUT', body: { name, quantity, unit_price, width: parts[0] || null, height: parts[1] || null, depth: parts[2] || null } });
            const index = items.findIndex(x => x.id === item.id);
            if (index >= 0) items[index] = updated;
            renderItems(items);
            toast('Móvel atualizado. Total recalculado automaticamente.');
          } catch (err) {
            toast(err.message, 'error');
            setButtonBusy(save, false, 'Salvando...', 'Salvar alterações');
          }
        });
        return;
      }

      const deleteButton = event.target.closest('.quote-item-delete');
      if (!deleteButton || deleteButton.disabled) return;
      if (!confirm('Excluir este móvel do orçamento?')) return;
      deleteButton.disabled = true;
      try {
        await api(`/quotes/${quoteId}/items/${deleteButton.dataset.id}`, { method: 'DELETE' });
        const index = items.findIndex(x => String(x.id) === String(deleteButton.dataset.id));
        if (index >= 0) items.splice(index, 1);
        renderItems(items);
        toast('Móvel removido. Total atualizado.');
      } catch (err) {
        deleteButton.disabled = false;
        toast(err.message, 'error');
      }
    });

    form.querySelector('#quote-items-close').addEventListener('click', async () => {
      closeModal();
      try { await loadResource('quotes'); } catch (_) {}
    });
    $('#modal')?.classList.remove('hidden');
    $('#modal')?.setAttribute('aria-hidden', 'false');
  }
  window.openQuoteItems = openQuoteItems;

  async function openSmartQuoteCreate() {
    const customers = await api('/customers?limit=100');
    if (!customers.length) {
      toast('Cadastre pelo menos um cliente antes de criar um orçamento.', 'error');
      showSection('customers');
      return;
    }

    const options = customers.map(c => `<option value="${c.id}">${escapeHtml(c.name)}${c.email ? ` — ${escapeHtml(c.email)}` : ''}</option>`).join('');
    const form = document.querySelector('#item-form');
    document.querySelector('#modal-title').textContent = 'Novo orçamento inteligente';
    form.innerHTML = `<div class="smart-quote-create"><div class="smart-quote-intro"><span class="eyebrow">Assistente de orçamento</span><h3>Transforme o pedido do cliente em uma prévia técnica</h3><p>A IA organiza o pedido; os preços vêm somente do catálogo da sua marcenaria e continuam sujeitos à sua aprovação.</p></div><div class="form-grid"><label class="span-2">Pedido do cliente<textarea name="request_text" minlength="10" maxlength="5000" placeholder="Ex.: Quero um armário de 3 metros, MDF branco, seis portas e três gavetas."></textarea></label><label>Cliente<select name="customer_id" required><option value="">Selecione o cliente...</option>${options}</select></label><label>Margem de lucro (%)<input name="profit_margin" type="number" value="30" min="0" max="100" step="0.01" required></label><label class="span-2">Descrição<textarea name="description" minlength="3" maxlength="3000" required placeholder="Ex.: Cozinha planejada em MDF, portas basculantes..."></textarea></label><label>Medidas<textarea name="measurements" maxlength="2000" placeholder="Ex.: 3,20m x 2,40m"></textarea></label><label>Materiais<textarea name="materials" maxlength="2000" placeholder="Ex.: MDF amadeirado 18mm, MDF branco..."></textarea></label></div><div class="cost-grid"><label>Material<input name="material_cost" type="number" value="0" min="0" step="0.01" inputmode="decimal" required></label><label>Ferragens<input name="hardware_cost" type="number" value="0" min="0" step="0.01" inputmode="decimal" required></label><label>Mão de obra<input name="labor_cost" type="number" value="0" min="0" step="0.01" inputmode="decimal" required></label><label>Acabamento<input name="finishing_cost" type="number" value="0" min="0" step="0.01" inputmode="decimal" required></label></div><div id="smart-quote-state" role="status" aria-live="polite">Descreva o pedido para iniciar a análise.</div><div id="smart-quote-brief"></div><label class="smart-review"><input type="checkbox" name="human_reviewed">Revisei medidas, materiais, quantidades, dados faltantes e custos desta prévia.</label><div id="smart-quote-result" class="smart-quote-result" aria-live="polite"></div><div class="modal-actions"><button type="button" class="btn secondary" data-smart-cancel>Cancelar</button><button type="button" class="btn secondary" data-smart-interpret>✨ Interpretar pedido</button><button type="button" class="btn secondary" data-smart-analyze>Calcular preço</button><button type="button" class="btn primary" data-smart-save disabled>Salvar orçamento</button></div></div>`;

    const smartForm = form.querySelector('.smart-quote-create');
    const saveButton = smartForm.querySelector('[data-smart-save]');
    const resultPanel = smartForm.querySelector('#smart-quote-result');
    let lastEstimate = null;
    let interpretationSource = null;
    let technicalBrief = null;
    let busy = false;
    let revision = 0;
    let calculatedRevision = -1;
    let saveIdentity = null;
    const statePanel = smartForm.querySelector('#smart-quote-state');
    const briefPanel = smartForm.querySelector('#smart-quote-brief');
    const reviewed = field(smartForm, 'human_reviewed');
    const actionButtons = ['interpret', 'analyze', 'save'].map(action => smartForm.querySelector(`[data-smart-${action}]`));
    const setState = text => { statePanel.textContent = text; };
    const canSave = () => !busy && reviewed.checked && lastEstimate && calculatedRevision === revision && Number(lastEstimate.suggested_total || 0) > 0;
    const syncSave = () => { saveButton.disabled = !canSave(); };
    const begin = label => {
      if (busy) return false;
      busy = true;
      actionButtons.forEach(button => { button.disabled = true; button.setAttribute?.('aria-busy', 'true'); });
      setState(label);
      return true;
    };
    const finish = () => {
      busy = false;
      actionButtons.forEach(button => { button.disabled = false; button.setAttribute?.('aria-busy', 'false'); });
      syncSave();
    };
    const stillCurrent = version => version === revision && smartForm.isConnected !== false;
    reviewed.addEventListener('change', () => {
      syncSave();
      setState(canSave() ? 'Pronto para salvar. O orçamento seguirá para aprovação interna.' : 'Revise os dados e calcule o preço.');
    });

    const payloadFromForm = () => ({
      material_cost: numberValue(smartForm, 'material_cost'),
      hardware_cost: numberValue(smartForm, 'hardware_cost'),
      labor_cost: numberValue(smartForm, 'labor_cost'),
      finishing_cost: numberValue(smartForm, 'finishing_cost'),
      profit_margin: numberValue(smartForm, 'profit_margin'),
    });

    const setValue = (name, value) => {
      const control = field(smartForm, name);
      if (control) control.value = value ?? '';
    };

    const invalidateEstimate = () => {
      revision += 1;
      saveIdentity = null;
      reviewed.checked = false;
      lastEstimate = null;
      saveButton.disabled = true;
      setState('Dados alterados. Revise e calcule novamente antes de salvar.');
    };
    ['request_text', 'customer_id', 'description', 'measurements', 'materials', 'material_cost', 'hardware_cost', 'labor_cost', 'finishing_cost', 'profit_margin'].forEach(name => {
      field(smartForm, name)?.addEventListener('input', invalidateEstimate);
      field(smartForm, name)?.addEventListener('change', invalidateEstimate);
    });

    smartForm.querySelector('[data-smart-interpret]').addEventListener('click', async () => {
      if (busy) return;
      const customerId = numberValue(smartForm, 'customer_id');
      const requestText = fieldValue(smartForm, 'request_text').trim();
      if (!customerId) {
        toast('Selecione o cliente antes de interpretar o pedido.', 'error');
        return;
      }
      if (requestText.length < 10) {
        toast('Descreva o pedido do cliente com um pouco mais de detalhe.', 'error');
        return;
      }

      const button = smartForm.querySelector('[data-smart-interpret]');
      if (!begin('Analisando o pedido…')) return;
      const version = revision;
      reviewed.checked = false;
      lastEstimate = null;
      setButtonBusy(button, true, 'Interpretando...', '✨ Interpretar pedido');
      try {
        const draft = await createDraft({
          customer_id: customerId,
          request_text: requestText,
          profit_margin: numberValue(smartForm, 'profit_margin'),
        });
        if (!stillCurrent(version)) return;
        technicalBrief = draft.brief;
        interpretationSource = draft.interpretation_source || 'assisted_local';
        const list = values => (values || []).map(value => `<li>${escapeHtml(value)}</li>`).join('') || '<li>Nenhum dado adicional indicado. Confirme na revisão.</li>';
        briefPanel.innerHTML = `<div class="panel"><h4>Dados faltantes</h4><ul>${list(draft.brief?.missing_data)}</ul><h4>Perguntas sugeridas</h4><ul>${list(draft.brief?.questions)}</ul><h4>Riscos</h4><ul>${list(draft.brief?.risks)}</ul><p>Confiança da interpretação: ${Number(draft.brief?.confidence_score || 0)}%</p></div>`;
        setValue('description', draft.brief?.normalized_description || '');
        setValue('measurements', draft.brief?.measurements_summary || '');
        setValue('materials', draft.brief?.materials_summary || '');
        ['material_cost', 'hardware_cost', 'labor_cost', 'finishing_cost'].forEach(name => setValue(name, draft[name]));
        const missing = (draft.unpriced_items || []).map(item => `${item.requirement.name}: ${item.reason}`);
        lastEstimate = { ...draft, warnings: missing, recommendations: draft.brief?.questions || [] };
        renderPanel(lastEstimate, resultPanel);

        const hasMissing = missing.length > 0;
        const hasPositiveTotal = Number(draft.suggested_total || 0) > 0;
        const assisted = interpretationSource === 'assisted_local';
        saveButton.disabled = true;
        calculatedRevision = -1;
        setState(`${assisted ? 'Fallback local' : 'IA ativa'} · análise pronta. Revise os dados antes de calcular.${hasMissing || !hasPositiveTotal ? ' Complete os custos pendentes.' : ''}`);

        if (assisted) {
          toast('Pedido organizado em modo assistido. Revise os custos e clique em Calcular preço antes de salvar.');
        } else if (hasMissing) {
          toast('IA concluída. Complete os itens sem preço e recalcule antes de salvar.', 'error');
        } else if (!hasPositiveTotal) {
          toast('IA concluída, mas ainda faltam custos para formar um preço válido.', 'error');
        } else {
          toast('IA concluída com catálogo e preço calculado. Revise antes de salvar.');
        }
      } catch (err) {
        setState(`Erro recuperável: ${err.message}. Você pode revisar os dados e tentar novamente.`);
        toast(err.message, 'error');
      } finally {
        setButtonBusy(button, false, 'Interpretando...', '✨ Interpretar pedido');
        finish();
      }
    });

    smartForm.querySelector('[data-smart-analyze]').addEventListener('click', async () => {
      if (busy) return;
      if (!reviewed.checked) { setState('Confirme a revisão humana dos dados e custos.'); return; }
      if (!Object.values(payloadFromForm()).every(Number.isFinite)) { setState('Informe valores numéricos válidos.'); return; }
      if (!begin('Pronto para calcular · calculando com os custos revisados…')) return;
      const version = revision;
      lastEstimate = null;
      const button = smartForm.querySelector('[data-smart-analyze]');
      setButtonBusy(button, true, 'Calculando...', 'Calcular preço');
      try {
        const estimate = await api('/quotes/estimate', { method: 'POST', body: payloadFromForm() });
        if (!stillCurrent(version)) return;
        calculatedRevision = version;
        lastEstimate = { ...estimate, interpretation_source: interpretationSource || estimate.interpretation_source };
        renderPanel(lastEstimate, resultPanel);
        const validTotal = Number(lastEstimate.suggested_total || 0) > 0;
        saveButton.disabled = !validTotal;
        setState(validTotal ? 'Pronto para salvar. Revise o valor calculado.' : 'Complete os custos antes de salvar.');
        toast(
          validTotal
            ? 'Análise concluída. Revise o preço antes de salvar.'
            : 'Informe pelo menos um custo maior que zero e calcule novamente.',
          validTotal ? 'success' : 'error',
        );
      } catch (err) {
        lastEstimate = null;
        saveButton.disabled = true;
        setState(`Erro recuperável: ${err.message}. Tente calcular novamente.`);
        toast(err.message, 'error');
      } finally {
        setButtonBusy(button, false, 'Calculando...', 'Calcular preço');
        finish();
      }
    });

    smartForm.querySelector('[data-smart-cancel]').addEventListener('click', closeModal);

    saveButton.addEventListener('click', async () => {
      if (busy) return;
      if (!lastEstimate) {
        toast('Calcule o orçamento antes de salvar.', 'error');
        return;
      }
      if (Number(lastEstimate.suggested_total || 0) <= 0) {
        saveButton.disabled = true;
        toast('O preço sugerido precisa ser maior que zero antes de salvar.', 'error');
        return;
      }

      const customerId = numberValue(smartForm, 'customer_id');
      const description = fieldValue(smartForm, 'description').trim();
      if (!customerId) {
        toast('Selecione o cliente antes de salvar.', 'error');
        return;
      }
      if (description.length < 3) {
        toast('Informe a descrição do orçamento.', 'error');
        return;
      }

      if (!canSave()) { syncSave(); setState('Revise e calcule novamente antes de salvar.'); return; }
      const data = payloadFromForm();
      data.technical_brief = technicalBrief;
      data.human_reviewed = reviewed.checked;
      data.customer_id = customerId;
      data.description = description;
      data.measurements = fieldValue(smartForm, 'measurements').trim() || null;
      data.materials = fieldValue(smartForm, 'materials').trim() || null;
      data.total = Number(lastEstimate.suggested_total || 0);
      data.status = 'analysis';

      if (!begin('Salvando orçamento…')) return;
      saveIdentity ||= window.crypto?.randomUUID?.() || `quote-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      setButtonBusy(saveButton, true, 'Salvando...', 'Salvar orçamento');
      try {
        const quote = await api('/quotes', { method: 'POST', body: data, headers: { 'Idempotency-Key': saveIdentity } });
        toast('Orçamento criado. Agora adicione os móveis.');
        await openQuoteItems(quote.id, quote.description);
      } catch (err) {
        toast(err.message, 'error');
        setState(`Erro recuperável: ${err.message}. Tente salvar novamente.`);
        setButtonBusy(saveButton, false, 'Salvando...', 'Salvar orçamento');
        finish();
      }
    });

    $('#modal')?.classList.remove('hidden');
    $('#modal')?.setAttribute('aria-hidden', 'false');
  }

  window.openSmartQuote = openSmartQuoteCreate;
  // Capture Enter before the generic CRUD submit listener, without adding a second save handler.
  document.addEventListener('submit', event => {
    if (event.target?.querySelector?.('.smart-quote-create')) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);
  const originalCreateItem = window.createItem;
  window.createItem = function(resource) {
    if (resource === 'quotes') return openSmartQuoteCreate().catch(err => toast(err.message, 'error'));
    return originalCreateItem(resource);
  };
})();
