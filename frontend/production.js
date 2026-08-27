/* Production UI uses the authenticated API; never place credentials here. */
(() => {
  const stages = { planning:'Planejamento', in_progress:'Em andamento', measurement:'Medição', technical_design:'Projeto técnico', purchasing:'Compras', production:'Produção', installation:'Instalação', delivered:'Entregue', completed:'Concluído', cancelled:'Cancelado' };
  const nextStage = { planning:'measurement', in_progress:'production', measurement:'technical_design', technical_design:'purchasing', purchasing:'production', production:'installation', installation:'delivered', delivered:'completed' };
  const kinds = { mdf:'MDF', hardware:'Ferragens', profile:'Perfis', accessory:'Acessórios', finish:'Acabamento', service:'Serviço', other:'Outro' };
  const categories = { material:'Material', labor:'Mão de obra', freight:'Frete', installation:'Instalação', outsourcing:'Terceirização', tax:'Impostos', other:'Outro' };
  const options = (label, name, values, current) => '<label>' + label + '<select name="' + name + '" required>' + Object.entries(values).map(([key, value]) => '<option value="' + key + '"' + (key === current ? ' selected' : '') + '>' + value + '</option>').join('') + '</select></label>';
  const activeField = row => '<label class="check"><input type="checkbox" name="is_active"' + (row.is_active !== false ? ' checked' : '') + '> Ativo</label>';
  Object.assign(statusLabels, stages);
  Object.assign(labels, { suppliers:'Fornecedores', materials:'Insumos' });
  state.suppliers = []; state.materials = [];
  configs.suppliers = { title:'Fornecedores', endpoint:'/suppliers', columns:[['name','Fornecedor'],['contact_name','Contato'],['email','E-mail'],['phone','Telefone'],['is_active','Situação']], empty:'Nenhum fornecedor cadastrado.' };
  configs.materials = { title:'Insumos', endpoint:'/materials', columns:[['name','Insumo'],['kind','Tipo'],['supplier_id','Fornecedor'],['unit','Unidade'],['unit_cost','Custo unitário'],['waste_percent','Perda (%)'],['is_active','Situação']], empty:'Nenhum insumo cadastrado.' };
  function supplierForm(row = {}) {
    return field('Nome do fornecedor','name','text',row.name || '',true,'minlength="2" maxlength="160"')
      + field('Pessoa de contato','contact_name','text',row.contact_name || '',false,'maxlength="160"')
      + field('E-mail','email','email',row.email || '') + field('Telefone','phone','tel',row.phone || '',false,'maxlength="40"')
      + field('Observações','notes','textarea',row.notes || '',false,'maxlength="5000"') + activeField(row);
  }
  function materialForm(row = {}) {
    return field('Nome do insumo','name','text',row.name || '',true,'minlength="2" maxlength="180"')
      + options('Tipo','kind',kinds,row.kind || 'mdf') + recordLookupField('Fornecedor','suppliers','supplier_id',row.supplier_id || '',false)
      + field('Unidade','unit','text',row.unit || 'un',true,'maxlength="30"')
      + field('Custo unitário','unit_cost','number',row.unit_cost ?? 0,true,'min="0" step="0.01"')
      + field('Perda (%)','waste_percent','number',row.waste_percent ?? 0,true,'min="0" max="100" step="0.01"') + activeField(row);
  }
  const originalForm = window.formHtml;
  window.formHtml = (resource, row = {}) => resource === 'suppliers' ? supplierForm(row) : resource === 'materials' ? materialForm(row) : originalForm(resource, row);
  const originalOpen = window.openForm;
  window.openForm = async function(resource, id = null) {
    await originalOpen(resource, id);
    if (['suppliers','materials'].includes(resource)) $('#modal-title').textContent = (id ? 'Editar ' : 'Novo ') + (resource === 'suppliers' ? 'fornecedor' : 'insumo');
  };
  const originalFormat = window.formatCell;
  window.formatCell = function(resource, key, value) {
    if (key === 'unit_cost') return money(value);
    if (key === 'kind') return escapeHtml(kinds[value] || value);
    if (key === 'supplier_id' && value) return escapeHtml(state.suppliers.find(row => row.id === value)?.name || '#' + value);
    return originalFormat(resource, key, value);
  };
  const originalRender = window.renderResource;
  window.renderResource = function(resource) {
    originalRender(resource);
    if (resource !== 'projects' || state.listResource !== 'projects' || state.loading || state.listError) return;
    const filter = $('#projects select[aria-label="Filtrar por status"]');
    if (filter) {
      filter.innerHTML = '<option value="">Todos os status</option>' + Object.entries(stages).map(([key, value]) => '<option value="' + key + '">' + value + '</option>').join('');
      filter.value = state.status;
    }
    $$('#projects tbody tr[data-row-id]').forEach(row => {
      const actions = $('.actions', row);
      if (!actions || $('[data-production]', actions)) return;
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'small-btn'; button.dataset.production = row.dataset.rowId;
      button.textContent = 'Produção e custos';
      button.addEventListener('click', () => openProduction(Number(row.dataset.rowId))); actions.prepend(button);
    });
  };
  function modal(title) {
    $('#modal-title').textContent = title;
    $('#item-form').innerHTML = '<div class="production-modal" aria-live="polite">Carregando...</div>';
    $('#modal').classList.remove('hidden'); $('#modal').setAttribute('aria-hidden','false');
    return $('.production-modal', $('#item-form'));
  }
  function costPayload(form, projectId) {
    const fd = new FormData(form);
    return { project_id:projectId, material_id:fd.get('material_id') ? Number(fd.get('material_id')) : null,
      category:fd.get('category'), description:String(fd.get('description') || '').trim(),
      quantity:Number(fd.get('quantity')), unit_cost:Number(fd.get('unit_cost')) };
  }
  async function openProduction(projectId) {
    const view = modal('Produção e custos — projeto #' + projectId);
    let offset = 0, request = 0;
    async function load() {
      const version = ++request;
      view.textContent = 'Carregando produção e custos...';
      try {
        const [project, rows, total] = await Promise.all([
          api('/projects/' + projectId), api('/project-costs/project/' + projectId + '?offset=' + offset + '&limit=25'),
          api('/project-costs/project/' + projectId + '/total')
        ]);
        if (!view.isConnected || version !== request) return;
        const next = nextStage[project.status], count = rows.pagination?.total;
        view.innerHTML = '<h3>' + escapeHtml(project.name) + '</h3><p>Etapa atual: <strong>' + escapeHtml(stages[project.status] || project.status) + '</strong>'
          + (project.quote_id ? ' · Orçamento #' + project.quote_id : '') + '</p>'
          + (next ? '<p>Avance somente depois de concluir o trabalho desta etapa.</p><button type="button" class="btn primary" data-advance>Confirmar avanço para ' + stages[next] + '</button>' : '<p>Etapa encerrada. Não é possível avançar.</p>')
          + '<section class="production-summary"><h3>Custos registrados</h3><strong>' + money(total.total_cost) + '</strong><p>Valores efetivos lançados; não representam lucro nem orçamento previsto.</p></section>'
          + '<div class="table-wrap"><table class="table"><thead><tr><th>Descrição</th><th>Categoria</th><th>Quantidade</th><th>Unitário</th><th>Total</th></tr></thead><tbody>'
          + (rows.length ? rows.map(row => '<tr><td>' + escapeHtml(row.description) + '</td><td>' + escapeHtml(categories[row.category] || row.category) + '</td><td>' + Number(row.quantity) + '</td><td>' + money(row.unit_cost) + '</td><td>' + money(row.total_cost) + '</td></tr>').join('') : '<tr><td colspan="5">Nenhum custo nesta página.</td></tr>')
          + '</tbody></table></div><nav class="pagination" aria-label="Páginas de custos"><button type="button" class="btn secondary" data-cost-prev' + (offset === 0 ? ' disabled' : '') + '>Anterior</button><span>Página ' + (Math.floor(offset / 25) + 1) + (count == null ? '' : ' · ' + count + ' lançamento(s)') + '</span><button type="button" class="btn secondary" data-cost-next' + ((count == null ? rows.length < 25 : offset + rows.length >= count) ? ' disabled' : '') + '>Próxima</button></nav>'
          + '<h3>Novo lançamento</h3><div class="form-grid">' + options('Categoria','category',categories,'material') + recordLookupField('Insumo','materials','material_id','',false)
          + field('Descrição do custo','description','text','',true,'minlength="2" maxlength="500"')
          + field('Quantidade','quantity','number',1,true,'min="0.001" step="0.001"') + field('Custo unitário','unit_cost','number',0,true,'min="0" step="0.01"')
          + '</div><p>Insumo é opcional. Com insumo selecionado e custo zero, será usado o custo do cadastro. A perda cadastrada será aplicada pelo servidor. Confira antes de registrar: esta tela não edita nem exclui lançamentos.</p>'
          + '<p data-production-message role="status"></p><div class="modal-actions"><button type="button" class="btn secondary" data-production-close>Fechar</button><button type="button" class="btn primary" data-cost-save>Registrar custo</button></div>';
        $('[data-production-close]',view).addEventListener('click', closeModal);
        $('[data-cost-prev]',view).addEventListener('click', () => { offset = Math.max(0, offset - 25); load(); });
        $('[data-cost-next]',view).addEventListener('click', () => { offset += 25; load(); });
        $('[data-advance]',view)?.addEventListener('click', async event => {
          const button = event.currentTarget; button.disabled = true;
          try {
            await api('/projects/' + projectId + '/status',{method:'PATCH',body:{status:next}});
            if (state.listResource === 'projects') await loadResource('projects');
            if (view.isConnected) await load();
          } catch (error) {
            if (view.isConnected) $('[data-production-message]',view).textContent = error.message + ' Feche e reabra para atualizar a etapa.';
            button.disabled = false;
          }
        });
        $('[data-cost-save]',view).addEventListener('click', async event => {
          const form = $('#item-form');
          if (!form.reportValidity()) return;
          const button = event.currentTarget; button.disabled = true;
          try {
            await api('/project-costs',{method:'POST',body:costPayload(form,projectId)});
            if (view.isConnected) { offset = 0; await load(); toast('Custo registrado. Total atualizado.'); }
          } catch (error) {
            if (view.isConnected) $('[data-production-message]',view).textContent = error.message + ' Confira a lista antes de repetir um envio com falha de conexão.';
            button.disabled = false;
          }
        });
        await setupRecordLookups(view);
      } catch (error) {
        if (!view.isConnected || version !== request) return;
        view.innerHTML = '<p role="alert">' + escapeHtml(error.message) + '</p><button type="button" class="btn secondary" data-retry>Tentar novamente</button>';
        $('[data-retry]',view).addEventListener('click', load);
      }
    }
    await load();
  }
  window.productionTools = Object.freeze({ stages, nextStage, supplierForm, materialForm, costPayload });
  window.openProduction = openProduction;
  const nav = $('#admin-nav'), main = $('.admin-main');
  if (nav && main) {
    for (const [resource, icon] of [['suppliers','▣'],['materials','▥']]) {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'nav'; button.dataset.section = resource;
      button.setAttribute('aria-label', labels[resource]); button.innerHTML = icon + ' <span>' + labels[resource] + '</span>';
      button.addEventListener('click', () => showSection(resource)); nav.appendChild(button);
      const section = document.createElement('section'); section.id = resource; section.className = 'admin-section hidden'; main.appendChild(section);
    }
  }
})();
