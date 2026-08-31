(() => {
  const money = value => Number(value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const escapeHtml = (value = '') => String(value).replace(/[&<>'\"]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c]));
  function analysisOrigin(result){if(result.analysis_source==='openai-assisted')return 'IA conectada + regras de segurança';if(result.analysis_source==='local-fallback')return 'IA externa indisponível • análise local aplicada';return 'Análise segura local'}
  function renderPanel(result) { let panel=document.querySelector('#smart-quote-result'); if(!panel){panel=document.createElement('section');panel.id='smart-quote-result';panel.className='smart-quote-panel';document.querySelector('.admin-main')?.prepend(panel)} const warnings=(result.warnings||[]).map(x=>`<li>${escapeHtml(x)}</li>`).join('')||'<li>Nenhum alerta financeiro.</li>'; const recommendations=(result.recommendations||[]).map(x=>`<li>${escapeHtml(x)}</li>`).join('')||'<li>Nenhuma recomendação adicional.</li>'; panel.innerHTML=`<div class="panel"><div class="panel-title"><div><span class="eyebrow">Inteligência de orçamento</span><h3>Análise automática</h3><small>${escapeHtml(analysisOrigin(result))}</small></div><span class="badge">Requer aprovação</span></div>${result.summary?`<p>${escapeHtml(result.summary)}</p>`:''}<div class="smart-quote-grid"><div><small>Custo base</small><strong>${money(result.base_cost)}</strong></div><div><small>Preço sugerido</small><strong>${money(result.suggested_total)}</strong></div><div><small>Margem</small><strong>${Number(result.profit_margin||0).toFixed(2)}%</strong></div></div><div class="smart-quote-columns"><div><h4>Alertas</h4><ul>${warnings}</ul></div><div><h4>Recomendações</h4><ul>${recommendations}</ul></div></div></div>`; }
  async function analyze(payload,render=true){const data=await api('/quotes/estimate',{method:'POST',body:payload});if(render)renderPanel(data);return data} window.analyzeSmartQuote=analyze;
  function numberValue(form,name){return Number(new FormData(form).get(name)||0)}
  const analysisFields=Object.freeze(['material_cost','hardware_cost','labor_cost','finishing_cost','profit_margin','description','measurements','materials']);
  function analysisPayload(form){const data=new FormData(form);return{material_cost:numberValue(form,'material_cost'),hardware_cost:numberValue(form,'hardware_cost'),labor_cost:numberValue(form,'labor_cost'),finishing_cost:numberValue(form,'finishing_cost'),profit_margin:numberValue(form,'profit_margin'),description:String(data.get('description')||'').trim(),measurements:String(data.get('measurements')||'').trim()||null,materials:String(data.get('materials')||'').trim()||null}}
  function measurementValue(value) {
    const match = String(value || '').trim().match(/^(\d+(?:[.,]\d+)?)\s*m?$/i);
    if (!match) return null;
    const number = Number(match[1].replace(',','.'));
    return Number.isFinite(number) && number > 0 ? number : null;
  }
  function itemPayload({name,quantity,unit_price,measurements=''}) {
    const raw = String(measurements).trim();
    if (!raw) return { name, quantity, unit_price, width:null, height:null, depth:null };
    const parts = raw.split(/[x×]/i);
    const values = parts.map(measurementValue);
    if (![2,3].includes(parts.length) || values.some(value => value === null)) {
      throw new Error('Revise as medidas. Use largura × altura ou largura × altura × profundidade, por exemplo: 2,40 × 2,10 × 0,60m.');
    }
    return { name, quantity, unit_price, width:values[0], height:values[1], depth:values[2] ?? null };
  }
  async function createQuoteAndOpenItems(data, openItems = openQuoteItems) {
    const quote = await api('/quotes',{method:'POST',body:data});
    try {
      if (await openItems(quote.id,quote.description) === false) throw new Error('Os itens não foram carregados.');
    } catch (error) {
      error.quotePersisted = true; error.quote = quote;
      throw error;
    }
    return quote;
  }
  window.smartQuoteTools=Object.freeze({itemPayload,createQuoteAndOpenItems,analysisPayload,analysisFields,analysisOrigin});
  async function openQuoteItems(quoteId,quoteDescription=''){
    const loading=openManagedModal(`Itens do orçamento #${quoteId}`,'<div class="history-modal" aria-live="polite">Carregando itens do orçamento...</div>','#modal-close');
    let quote,loadedItems;
    try {[quote,loadedItems]=await Promise.all([api(`/quotes/${quoteId}`),api(`/quotes/${quoteId}/items`)]);}
    catch(error){
      if (!loading.content?.isConnected || loading.form.firstElementChild !== loading.content) return false;
      openManagedModal(`Itens do orçamento #${quoteId}`,`<div class="history-modal"><p role="alert">${escapeHtml(error.message)}</p><button type="button" class="btn secondary" data-items-retry>Tentar novamente</button></div>`,'[data-items-retry]');
      document.querySelector('[data-items-retry]')?.addEventListener('click',()=>openQuoteItems(quoteId,quoteDescription));
      return false;
    }
    if (!loading.content?.isConnected || loading.form.firstElementChild !== loading.content) return false;
    let items=loadedItems; const form=document.querySelector('#item-form');
    if(!['pending','analysis'].includes(quote.status)){
      openManagedModal(`Itens do orçamento #${quoteId}`,`<div class="history-modal"><p>Orçamento com decisão registrada. Os itens estão protegidos contra alterações.</p>${items.map(item=>`<div class="history-item"><strong>${escapeHtml(item.name)} — ${Number(item.quantity)} × ${money(item.unit_price)}</strong><span>${money(item.subtotal)}</span></div>`).join('')||'<p>Nenhum item cadastrado.</p>'}<strong>Total: ${money(items.reduce((sum,item)=>sum+Number(item.subtotal||0),0))}</strong></div><div class="modal-actions"><button type="button" class="btn secondary" onclick="closeModal()">Fechar</button></div>`,'button');
      return true;
    }
    openManagedModal(`Itens do orçamento #${quoteId}`,`<div class="smart-quote-create"><div class="smart-quote-intro"><span class="eyebrow">Composição do orçamento</span><h3>${escapeHtml(quoteDescription||'Móveis planejados')}</h3><p>Adicione ou edite cada móvel. Subtotais e o total geral são recalculados automaticamente.</p></div><div id="quote-items-list"></div><div class="cost-grid"><label>Nome do móvel<input id="qi-name" type="text" maxlength="200" placeholder="Ex.: Armário de cozinha" required></label><label>Quantidade<input id="qi-quantity" type="number" min="0.01" step="0.01" value="1" inputmode="decimal"></label><label>Medidas (L × A × P)<input id="qi-measurements" type="text" maxlength="100" placeholder="Ex.: 2,40 × 2,10 × 0,60m"></label><label>Preço unitário<input id="qi-price" type="number" min="0" step="0.01" value="0" inputmode="decimal"></label></div><div class="smart-result-card"><div><small>Total dos itens</small><strong id="quote-items-total">R$ 0,00</strong></div><div><small>Orçamento</small><strong>#${quoteId}</strong></div></div><div class="modal-actions"><button type="button" class="btn secondary" id="quote-items-close">Fechar</button><button type="button" class="btn primary" id="quote-item-add">+ Adicionar móvel</button></div></div>`,'#qi-name');
    const list=form.querySelector('#quote-items-list'),totalEl=form.querySelector('#quote-items-total');
    const measurementText=item=>[item.width,item.height,item.depth].filter(v=>v!==null&&v!==undefined).map(v=>String(v).replace('.',',')).join(' × ');
    const renderItems=rows=>{const total=rows.reduce((sum,item)=>sum+Number(item.subtotal||0),0);totalEl.textContent=money(total);list.innerHTML=rows.length?rows.map(item=>`<div class="panel" data-item-id="${item.id}" style="margin-bottom:10px"><div class="panel-title"><div><strong>${escapeHtml(item.name)}</strong><small>${Number(item.quantity)} × ${money(item.unit_price)}${measurementText(item)?` • ${escapeHtml(measurementText(item))}`:''}${item.description?` • ${escapeHtml(item.description)}`:''}</small></div><strong>${money(item.subtotal)}</strong><div><button type="button" class="btn secondary quote-item-edit" data-id="${item.id}">Editar</button><button type="button" class="btn secondary quote-item-delete" data-id="${item.id}">Excluir</button></div></div></div>`).join(''):'<p class="muted">Nenhum móvel adicionado ainda.</p>'}; renderItems(items);
    const clearForm=()=>{form.querySelector('#qi-name').value='';form.querySelector('#qi-quantity').value='1';form.querySelector('#qi-measurements').value='';form.querySelector('#qi-price').value='0';};
    form.querySelector('#quote-item-add').addEventListener('click',async()=>{const name=form.querySelector('#qi-name').value.trim();const quantity=Number(form.querySelector('#qi-quantity').value||0);const unit_price=Number(form.querySelector('#qi-price').value||0);const raw=form.querySelector('#qi-measurements').value.trim();if(!name||quantity<=0||unit_price<0){toast('Informe nome, quantidade e preço unitário.','error');return}const button=form.querySelector('#quote-item-add');button.disabled=true;button.textContent='Adicionando...';try{const item=await api(`/quotes/${quoteId}/items`,{method:'POST',body:itemPayload({name,quantity,unit_price,measurements:raw})});items.push(item);renderItems(items);clearForm();toast('Móvel adicionado. Total atualizado automaticamente.')}catch(err){toast(err.message,'error')}finally{button.disabled=false;button.textContent='+ Adicionar móvel'}});
    list.addEventListener('click',async event=>{
      const editButton=event.target.closest('.quote-item-edit');
      if(editButton){
        const item=items.find(x=>String(x.id)===String(editButton.dataset.id)); if(!item)return;
        const row=editButton.closest('[data-item-id]');
        row.innerHTML=`<div class="form-grid"><label>Nome<input class="edit-name" value="${escapeHtml(item.name)}" maxlength="200"></label><label>Quantidade<input class="edit-quantity" type="number" min="0.01" step="0.01" value="${Number(item.quantity)}"></label><label>Medidas L × A × P<input class="edit-measurements" value="${escapeHtml(measurementText(item))}" maxlength="100"></label><label>Preço unitário<input class="edit-price" type="number" min="0" step="0.01" value="${Number(item.unit_price)}"></label></div><div class="modal-actions"><button type="button" class="btn secondary quote-item-cancel">Cancelar</button><button type="button" class="btn primary quote-item-save">Salvar alterações</button></div>`;
        row.querySelector('.quote-item-cancel').addEventListener('click',()=>renderItems(items));
        row.querySelector('.quote-item-save').addEventListener('click',async()=>{const name=row.querySelector('.edit-name').value.trim();const quantity=Number(row.querySelector('.edit-quantity').value||0);const unit_price=Number(row.querySelector('.edit-price').value||0);const raw=row.querySelector('.edit-measurements').value.trim();if(!name||quantity<=0||unit_price<0){toast('Informe nome, quantidade e preço unitário.','error');return}const save=row.querySelector('.quote-item-save');save.disabled=true;save.textContent='Salvando...';try{const updated=await api(`/quotes/${quoteId}/items/${item.id}`,{method:'PUT',body:itemPayload({name,quantity,unit_price,measurements:raw})});const index=items.findIndex(x=>x.id===item.id);if(index>=0)items[index]=updated;renderItems(items);toast('Móvel atualizado. Total recalculado automaticamente.')}catch(err){toast(err.message,'error');save.disabled=false;save.textContent='Salvar alterações'}});
        return;
      }
      const deleteButton=event.target.closest('.quote-item-delete');if(!deleteButton)return;if(!confirm('Excluir este móvel do orçamento?'))return;try{await api(`/quotes/${quoteId}/items/${deleteButton.dataset.id}`,{method:'DELETE'});const index=items.findIndex(x=>String(x.id)===String(deleteButton.dataset.id));if(index>=0)items.splice(index,1);renderItems(items);toast('Móvel removido. Total atualizado.')}catch(err){toast(err.message,'error')}});
    form.querySelector('#quote-items-close').addEventListener('click',async()=>{closeModal();try{await loadResource('quotes')}catch(_){}});
  }
  window.openQuoteItems=openQuoteItems;
  async function openSmartQuoteCreate(){
    const loading=openManagedModal('Novo orçamento inteligente','<div class="history-modal" aria-live="polite">Carregando clientes...</div>','#modal-close');
    let customers;try{customers=await api('/customers?limit=1')}catch(error){if(!loading.content?.isConnected||loading.form.firstElementChild!==loading.content)return false;openManagedModal('Novo orçamento inteligente',`<div class="history-modal"><p role="alert">${escapeHtml(error.message)}</p><button type="button" class="btn secondary" data-smart-retry>Tentar novamente</button></div>`,'[data-smart-retry]');document.querySelector('[data-smart-retry]')?.addEventListener('click',openSmartQuoteCreate);return false}if(!loading.content?.isConnected||loading.form.firstElementChild!==loading.content)return false;if(!customers.length){closeModal();toast('Cadastre pelo menos um cliente antes de criar um orçamento.','error');showSection('customers');return false}const form=document.querySelector('#item-form');
    openManagedModal('Novo orçamento inteligente',`<div class="smart-quote-create"><div class="smart-quote-intro"><span class="eyebrow">Assistente de orçamento</span><h3>Monte o orçamento e deixe a IA analisar</h3><p>Informe os custos reais. O sistema calcula custo base, preço sugerido, margem e alertas automaticamente.</p></div><div class="form-grid">${recordLookupField('Cliente','customers','customer_id')}<label>Margem de lucro (%)<input name="profit_margin" type="number" value="30" min="0" max="100" step="0.01" required></label><label class="span-2">Descrição<textarea name="description" minlength="3" maxlength="3000" required placeholder="Ex.: Cozinha planejada em MDF, portas basculantes..."></textarea></label><label>Medidas<textarea name="measurements" maxlength="2000" placeholder="Ex.: 3,20m x 2,40m"></textarea></label><label>Materiais<textarea name="materials" maxlength="2000" placeholder="Ex.: MDF amadeirado 18mm, MDF branco..."></textarea></label></div><div class="cost-grid"><label>Material<input name="material_cost" type="number" value="0" min="0" step="0.01" inputmode="decimal" required></label><label>Ferragens<input name="hardware_cost" type="number" value="0" min="0" step="0.01" inputmode="decimal" required></label><label>Mão de obra<input name="labor_cost" type="number" value="0" min="0" step="0.01" inputmode="decimal" required></label><label>Acabamento<input name="finishing_cost" type="number" value="0" min="0" step="0.01" inputmode="decimal" required></label></div><div id="smart-quote-result" class="smart-quote-result" aria-live="polite"></div><div class="modal-actions"><button type="button" class="btn secondary" data-smart-cancel>Cancelar</button><button type="button" class="btn secondary" data-smart-analyze>✨ Calcular com IA</button><button type="button" class="btn primary" data-smart-save disabled>Salvar orçamento</button></div></div>`,'[data-lookup-search]');
    const smartForm=form.querySelector('.smart-quote-create'),saveButton=smartForm.querySelector('[data-smart-save]');let lastEstimate=null;const payloadFromForm=()=>analysisPayload(form);
    smartForm.querySelector('[data-smart-analyze]').addEventListener('click',async()=>{
      const button=smartForm.querySelector('[data-smart-analyze]'),submitted=payloadFromForm();
      button.disabled=true;button.textContent='Calculando...';saveButton.disabled=true;lastEstimate=null;
      try{
        const estimate=await analyze(submitted,false);
        if(smartForm.isConnected===false)return;
        const result=smartForm.querySelector('#smart-quote-result');
        if(JSON.stringify(submitted)!==JSON.stringify(payloadFromForm())){
          result.textContent='Custos alterados durante o cálculo. Calcule novamente antes de salvar.';return;
        }
        lastEstimate=estimate;
        result.innerHTML=`<p><strong>${escapeHtml(analysisOrigin(lastEstimate))}</strong>${lastEstimate.summary?` — ${escapeHtml(lastEstimate.summary)}`:''}</p><div class="smart-result-card"><div><small>Custo base</small><strong>${money(lastEstimate.base_cost)}</strong></div><div><small>Preço sugerido</small><strong>${money(lastEstimate.suggested_total)}</strong></div><div><small>Margem</small><strong>${Number(lastEstimate.profit_margin||0).toFixed(2)}%</strong></div></div><div class="smart-result-lists"><div><strong>Alertas</strong><ul>${(lastEstimate.warnings||[]).map(x=>`<li>${escapeHtml(x)}</li>`).join('')||'<li>Nenhum alerta.</li>'}</ul></div><div><strong>Recomendações</strong><ul>${(lastEstimate.recommendations||[]).map(x=>`<li>${escapeHtml(x)}</li>`).join('')||'<li>Nenhuma recomendação.</li>'}</ul></div></div>`;
        saveButton.disabled=false;toast('Análise concluída. Revise o preço antes de salvar.');
      }catch(err){toast(err.message,'error')}finally{button.disabled=false;button.textContent='✨ Calcular com IA'}
    });
    smartForm.querySelector('[data-smart-cancel]').addEventListener('click',closeModal);
    saveButton.addEventListener('click',async()=>{if(!lastEstimate){toast('Calcule o orçamento com a IA antes de salvar.','error');return}if(!form.reportValidity())return;const fd=new FormData(form),data=payloadFromForm();data.customer_id=Number(fd.get('customer_id'));data.total=Number(lastEstimate.suggested_total||0);data.status='analysis';saveButton.disabled=true;saveButton.textContent='Salvando...';try{await createQuoteAndOpenItems(data);toast('Orçamento criado. Agora adicione os móveis.')}catch(err){if(err.quotePersisted){toast(`Orçamento #${err.quote.id} criado, mas os itens não foram carregados. Use “Tentar novamente” ou reabra o orçamento; não salve outra vez.`,'error');loadResource('quotes').catch(()=>{});return}toast(err.message,'error');saveButton.disabled=false;saveButton.textContent='Salvar orçamento'}});
    smartForm.addEventListener('input',event=>{if(analysisFields.includes(event.target.name)){lastEstimate=null;saveButton.disabled=true;smartForm.querySelector('#smart-quote-result').textContent='Dados da análise alterados. Calcule novamente antes de salvar.'}});
    await setupRecordLookups(form);
  }
  const originalCreateItem=window.createItem;window.createItem=function(resource){if(resource==='quotes')return openSmartQuoteCreate().catch(err=>toast(err.message,'error'));return originalCreateItem(resource)};
})();
