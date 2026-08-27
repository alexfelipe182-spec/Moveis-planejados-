const API = window.API_BASE_URL || (location.hostname === 'localhost' ? 'http://localhost:8000/api/v1' : 'https://ideal-marcenaria-api.onrender.com/api/v1');
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const state = { user:null, resource:null, listResource:null, id:null, rows:[], categories:[], customers:[], search:'', status:'', csrfToken:'', offset:0, limit:25, total:0, loading:false, listError:'' };
const labels = {dashboard:'Dashboard',customers:'Clientes',quotes:'Orçamentos',projects:'Projetos',products:'Produtos',categories:'Serviços',users:'Usuários',activities:'Histórico'};
const statusLabels = {pending:'Pendente',analysis:'Em análise',approved:'Aprovado',rejected:'Recusado',completed:'Concluído',planning:'Planejamento',in_progress:'Em andamento',cancelled:'Cancelado'};
const csrf = () => state.csrfToken || document.cookie.split('; ').find(x=>x.startsWith('csrf_token='))?.split('=')[1] || '';
const escapeHtml = (v='') => String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const money = v => Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
let refreshPromise = null;
let sessionVersion = 0;
let listRequestVersion = 0;
let searchTimer = null;
function toast(message,type='success'){const el=$('#toast');if(!el)return;el.textContent=message;el.className=`toast show ${type}`;clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.className='toast',3500)}
async function refreshSession() {
  if (!refreshPromise) {
    refreshPromise = api('/auth/refresh', { method: 'POST' }, false)
      .finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}
async function api(path, options = {}, retryAuth = true) {
  const requestVersion = sessionVersion;
  const opts = { credentials: 'include', ...options, headers: { ...(options.headers || {}) } };
  if (opts.body && !(opts.body instanceof URLSearchParams) && typeof opts.body !== 'string') {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(opts.body);
  }
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(opts.method) && csrf()) {
    opts.headers['X-CSRF-Token'] = csrf();
  }
  const res = await fetch(API + path, opts);
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && retryAuth && !path.startsWith('/auth/')) {
    // A delayed response may belong to the session another request already renewed.
    if (requestVersion === sessionVersion) await refreshSession();
    return api(path, options, false);
  }
  if (!res.ok) {
    throw new Error(data.detail || (res.status === 401 ? 'Sessão expirada. Faça login novamente.' : `Erro ${res.status}`));
  }
  if (typeof data?.csrf_token === 'string') state.csrfToken = data.csrf_token;
  if (path === '/auth/login' || path === '/auth/refresh') sessionVersion += 1;
  if (Array.isArray(data)) {
    const integerHeader = name => {
      const value = res.headers?.get(name);
      return value != null && /^\d+$/.test(value) && Number.isSafeInteger(Number(value)) ? Number(value) : null;
    };
    Object.defineProperty(data, 'pagination', { value: {
      total: integerHeader('X-Total-Count'), offset: integerHeader('X-Page-Offset'), limit: integerHeader('X-Page-Limit'),
    } });
  }
  return data;
}
function openAuth(view='login'){const o=$('#auth-overlay');o.classList.remove('hidden');o.setAttribute('aria-hidden','false');showAuth(view)}
function closeAuth(){const o=$('#auth-overlay');o.classList.add('hidden');o.setAttribute('aria-hidden','true')}
function showAuth(view){['login','register','recovery','reset'].forEach(v=>$(`#${v}-view`)?.classList.toggle('hidden',v!==view))}
function showWhatsApp(message='Olá! Quero solicitar um orçamento para móveis planejados.'){const number=window.WHATSAPP_NUMBER;if(number)window.open(`https://wa.me/${String(number).replace(/\D/g,'')}?text=${encodeURIComponent(message)}`,'_blank','noopener');else toast('Configure window.WHATSAPP_NUMBER para ativar o WhatsApp.','error')}
function setupPublic(){$$('#open-login').forEach(b=>b.addEventListener('click',()=>openAuth('login')));$('#close-auth').addEventListener('click',closeAuth);$('#auth-overlay').addEventListener('click',e=>{if(e.target.id==='auth-overlay')closeAuth()});$$('[data-quote]').forEach(b=>b.addEventListener('click',()=>showWhatsApp()));$('#show-register').addEventListener('click',()=>showAuth('register'));$('#show-recovery').addEventListener('click',()=>showAuth('recovery'));$$('[data-auth-back]').forEach(b=>b.addEventListener('click',()=>showAuth('login')));$('#login-form').addEventListener('submit',login);$('#register-form').addEventListener('submit',register);$('#recovery-form').addEventListener('submit',recovery);$('#reset-form').addEventListener('submit',resetPassword);const hashToken=new URLSearchParams(location.hash.slice(1)).get('reset_token');const queryToken=new URLSearchParams(location.search).get('reset_token');const token=hashToken||queryToken;if(token){sessionStorage.setItem('reset_token',token);history.replaceState({},'',location.pathname);openAuth('reset')}}
async function login(e){e.preventDefault();$('#login-error').textContent='';try{const body=new URLSearchParams({username:$('#login-email').value.trim().toLowerCase(),password:$('#login-password').value});await api('/auth/login',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});state.user=await api('/me');if(!state.user.is_admin)throw new Error('Sua conta ainda não possui permissão administrativa.');closeAuth();enterAdmin()}catch(err){$('#login-error').textContent=err.message;if(err.message.includes('permissão'))await api('/auth/logout',{method:'POST'}).catch(()=>{})}}
async function register(e){e.preventDefault();const msg=$('#register-message');msg.className='form-message';msg.textContent='';try{await api('/auth/register',{method:'POST',body:{name:$('#register-name').value.trim(),email:$('#register-email').value.trim().toLowerCase(),password:$('#register-password').value}});msg.classList.add('success');msg.textContent='Cadastro realizado. Aguarde a liberação de um administrador para acessar o painel.';e.target.reset()}catch(err){msg.classList.add('error');msg.textContent=err.message}}
async function recovery(e){e.preventDefault();const msg=$('#recovery-message');msg.className='form-message';try{const data=await api('/auth/password-reset/request',{method:'POST',body:{email:$('#recovery-email').value.trim().toLowerCase()}});msg.classList.add('success');msg.textContent=data.message+(data.debug_token?' Token de teste gerado.':'');if(data.debug_token){sessionStorage.setItem('reset_token',data.debug_token);setTimeout(()=>showAuth('reset'),500)}}catch(err){msg.classList.add('error');msg.textContent=err.message}}
async function resetPassword(e){e.preventDefault();const msg=$('#reset-message');msg.className='form-message';try{const token=sessionStorage.getItem('reset_token');if(!token)throw new Error('Token de recuperação não encontrado. Solicite novamente.');await api('/auth/password-reset/confirm',{method:'POST',body:{token,new_password:$('#reset-password').value}});sessionStorage.removeItem('reset_token');msg.classList.add('success');msg.textContent='Senha redefinida com sucesso. Faça login.';e.target.reset();setTimeout(()=>showAuth('login'),900)}catch(err){msg.classList.add('error');msg.textContent=err.message}}
function enterAdmin(){$('#public-site').classList.add('hidden');$('#admin-app').classList.remove('hidden');$('#user-badge').textContent=state.user?.name||'Administrador';loadDashboard()}
async function logout(){try{await api('/auth/logout',{method:'POST'})}finally{location.reload()}}
function setupAdmin(){$$('#admin-nav .nav').forEach(b=>b.addEventListener('click',()=>showSection(b.dataset.section)));$('#logout').addEventListener('click',logout);$('#modal-close').addEventListener('click',closeModal);$('#modal').addEventListener('click',e=>{if(e.target.id==='modal')closeModal()});document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal()});$('#item-form').addEventListener('submit',submitItem);$('#theme-toggle').addEventListener('click',()=>{document.body.classList.toggle('dark');localStorage.setItem('ideal-theme',document.body.classList.contains('dark')?'dark':'light')});if(localStorage.getItem('ideal-theme')==='dark')document.body.classList.add('dark')}
function showSection(name){clearTimeout(searchTimer);listRequestVersion++;state.listResource=null;$$('.admin-section').forEach(s=>s.classList.add('hidden'));$(`#${name}`).classList.remove('hidden');$$('#admin-nav .nav').forEach(b=>b.classList.toggle('active',b.dataset.section===name));$('#admin-title').textContent=labels[name]||'Dashboard';if(name==='dashboard')loadDashboard();else loadResource(name,{reset:true})}
async function loadDashboard(){const section=$('#dashboard');section.innerHTML='<div class="panel loading">Carregando visão geral...</div>';try{const [data,me]=await Promise.all([api('/admin/dashboard'),api('/me')]);state.user=me;$('#user-badge').textContent=me.name;const c=data.counts||{};const cards=[['Clientes',c.customers||0,'customers'],['Orçamentos',c.quotes||0,'quotes'],['Projetos',c.projects||0,'projects'],['Produtos',c.products||0,'products'],['Usuários',c.users||0,'users']];const recent=(data.recent_activities||[]).map(a=>`<li><strong>${escapeHtml(a.action)}</strong> · ${escapeHtml(a.description)}<small>${new Date(a.created_at).toLocaleString('pt-BR')}</small></li>`).join('')||'<li>Nenhuma atividade registrada ainda.</li>';section.innerHTML=`<div class="welcome"><div><span class="eyebrow">Visão geral</span><h2>Olá, ${escapeHtml(me.name.split(' ')[0])}. 👋</h2><p>Seu painel está conectado à API e ao PostgreSQL.</p></div><button class="btn light" onclick="createItem('quotes')">Novo orçamento</button></div><div class="stats">${cards.map(([n,v,s])=>`<button class="stat" onclick="showSection('${s}')"><span>${n}</span><strong>${v}</strong><small>Gerenciar ${n.toLowerCase()} →</small></button>`).join('')}</div><div class="panel"><div class="panel-title"><div><span class="eyebrow">Atividade</span><h3>Últimas ações</h3></div><button class="btn secondary" onclick="showSection('activities')">Ver histórico</button></div><ul class="activity-list">${recent}</ul></div>`}catch(err){section.innerHTML=`<div class="panel empty"><h2>Não foi possível carregar o painel</h2><p>${escapeHtml(err.message)}</p><button class="btn primary" onclick="loadDashboard()">Tentar novamente</button></div>`}}
const configs={customers:{title:'Clientes',endpoint:'/customers',columns:[['name','Cliente'],['email','E-mail'],['phone','Telefone'],['address','Endereço']],empty:'Nenhum cliente cadastrado.'},quotes:{title:'Orçamentos',endpoint:'/quotes',columns:[['customer_id','Cliente'],['description','Descrição'],['total','Valor'],['status','Status']],empty:'Nenhum orçamento cadastrado.'},projects:{title:'Projetos',endpoint:'/projects',columns:[['name','Projeto'],['customer_id','Cliente'],['status','Status'],['project_date','Data']],empty:'Nenhum projeto cadastrado.'},products:{title:'Produtos',endpoint:'/products',columns:[['name','Nome'],['category_id','Categoria'],['price','Valor'],['is_active','Status']],empty:'Nenhum produto cadastrado.'},categories:{title:'Serviços',endpoint:'/categories',columns:[['name','Nome'],['description','Descrição']],empty:'Nenhum serviço cadastrado.'},users:{title:'Usuários',endpoint:'/admin/users',columns:[['name','Nome'],['email','E-mail'],['is_admin','Permissão'],['is_active','Status']],empty:'Nenhum usuário cadastrado.'},activities:{title:'Histórico de atividades',endpoint:'/activities',columns:[['action','Ação'],['entity','Entidade'],['description','Descrição'],['created_at','Data']],empty:'Nenhuma atividade registrada.'}};
function mergeReferences(collection, rows) {
  const known = new Map(state[collection].map(row => [row.id, row]));
  rows.forEach(row => known.set(row.id, row));
  state[collection] = [...known.values()];
}
async function ensureReferences(collection, ids) {
  const missing = [...new Set(ids)].filter(id => id != null && !state[collection].some(row => row.id === id));
  if (!missing.length) return;
  const params = new URLSearchParams({ limit: '100' });
  missing.forEach(id => params.append('ids', String(id)));
  mergeReferences(collection, await api(`/${collection}?${params}`));
}
async function loadResource(resource, { reset = false } = {}) {
  const cfg = configs[resource];
  if (!cfg) return;
  clearTimeout(searchTimer);
  if (reset || state.listResource !== resource) {
    state.search = ''; state.status = ''; state.offset = 0; state.rows = []; state.total = 0;
  }
  state.listResource = resource;
  const version = ++listRequestVersion;
  state.loading = true; state.listError = '';
  renderResource(resource);
  const params = new URLSearchParams({ offset: String(state.offset), limit: String(state.limit) });
  if (state.search.trim()) params.set('q', state.search.trim());
  if (state.status) params.set('status', state.status);
  try {
    const rows = await api(`${cfg.endpoint}?${params}`);
    if (version !== listRequestVersion) return;
    if (!Array.isArray(rows)) throw new Error('A API retornou uma listagem inválida.');
    if (['customers', 'categories'].includes(resource)) mergeReferences(resource, rows);
    if (['quotes', 'projects'].includes(resource)) await ensureReferences('customers', rows.map(row => row.customer_id));
    if (resource === 'products') await ensureReferences('categories', rows.map(row => row.category_id));
    if (version !== listRequestVersion) return;
    state.rows = rows; state.total = rows.pagination?.total ?? null;
    if (!rows.length && state.offset > 0) {
      state.offset = state.total == null ? Math.max(0, state.offset - state.limit) : Math.max(0, Math.floor((state.total - 1) / state.limit) * state.limit);
      return loadResource(resource);
    }
    state.loading = false;
    renderResource(resource);
  } catch (error) {
    if (version !== listRequestVersion) return;
    state.loading = false; state.rows = []; state.total = null; state.listError = error.message;
    renderResource(resource);
  }
}
function renderResource(resource) {
  const cfg = configs[resource], section = $(`#${resource}`);
  if (!section || state.listResource !== resource) return;
  const rows = state.rows;
  const active = document.activeElement;
  const selection = active?.id === `search-${resource}` ? [active.selectionStart, active.selectionEnd] : null;
  const head = cfg.columns.map(column => `<th>${column[1]}</th>`).join('');
  const body = state.loading ? `<tr><td colspan="${cfg.columns.length + 1}" class="empty-row">Buscando registros...</td></tr>`
    : state.listError ? `<tr><td colspan="${cfg.columns.length + 1}" class="empty-row"><p>${escapeHtml(state.listError)}</p><button class="btn secondary" onclick="loadResource('${resource}')">Tentar novamente</button></td></tr>`
    : rows.length ? rows.map(row => `<tr data-row-id="${row.id}">${cfg.columns.map(([key]) => `<td>${formatCell(resource, key, row[key])}</td>`).join('')}<td class="actions">${resource === 'activities' ? '<span class="muted">Somente leitura</span>' : resource === 'users' ? `<button class="small-btn" onclick="editItem('users',${row.id})">Editar</button>` : `<button class="small-btn" onclick="editItem('${resource}',${row.id})">Editar</button>${resource === 'customers' ? `<button class="small-btn" onclick="viewCustomerHistory(${row.id})">Histórico</button>` : ''}<button class="small-btn danger" onclick="deleteItem('${resource}',${row.id})">Excluir</button>`}</td></tr>`).join('')
    : `<tr><td colspan="${cfg.columns.length + 1}" class="empty-row">${state.search || state.status ? 'Nenhum registro corresponde aos filtros.' : cfg.empty}</td></tr>`;
  const createButton = ['users', 'activities'].includes(resource) ? '' : `<button class="btn primary" onclick="createItem('${resource}')">+ Novo</button>`;
  const statusOptions = resource === 'quotes'
    ? { pending:'Pendente', analysis:'Em análise', approved:'Aprovado', rejected:'Recusado internamente', sent:'Enviado • aguardando cliente', accepted:'Aceito pelo cliente', declined:'Recusado pelo cliente', completed:'Concluído' }
    : { planning:'Planejamento', in_progress:'Em andamento', completed:'Concluído', cancelled:'Cancelado' };
  const statusFilter = ['quotes', 'projects'].includes(resource) ? `<select class="filter" aria-label="Filtrar por status" onchange="setStatus('${resource}',this.value)"><option value="">Todos os status</option>${Object.entries(statusOptions).map(([key, value]) => `<option value="${key}" ${state.status === key ? 'selected' : ''}>${value}</option>`).join('')}</select>` : '';
  const count = state.total == null ? `${rows.length} registro(s) nesta página` : `${state.total} registro(s) encontrados`;
  const last = state.total == null ? rows.length < state.limit : state.offset + rows.length >= state.total;
  const pages = state.total == null ? '' : ` de ${Math.max(1, Math.ceil(state.total / state.limit))}`;
  section.innerHTML = `<div class="panel" aria-busy="${state.loading}"><div class="toolbar"><div><span class="eyebrow">Gerenciamento</span><h2>${cfg.title}</h2><p aria-live="polite">${state.loading ? 'Consultando...' : count}</p></div><div class="toolbar-actions"><input type="search" id="search-${resource}" aria-label="Pesquisar em todos os registros" maxlength="200" placeholder="Pesquisar em todos os registros..." value="${escapeHtml(state.search)}" oninput="setSearch('${resource}',this.value)">${statusFilter}${createButton}</div></div><div class="table-wrap"><table class="table"><thead><tr>${head}<th>Ações</th></tr></thead><tbody>${body}</tbody></table></div><nav class="pagination" aria-label="Páginas de ${cfg.title}"><label>Por página<select aria-label="Registros por página" onchange="setPageSize('${resource}',this.value)" ${state.loading ? 'disabled' : ''}>${[10,25,50,100].map(size => `<option value="${size}" ${state.limit === size ? 'selected' : ''}>${size}</option>`).join('')}</select></label><span>Página ${Math.floor(state.offset / state.limit) + 1}${pages}</span><div><button class="btn secondary" onclick="changePage('${resource}',-1)" ${state.loading || state.offset === 0 ? 'disabled' : ''}>Anterior</button><button class="btn secondary" onclick="changePage('${resource}',1)" ${state.loading || last || state.listError ? 'disabled' : ''}>Próxima</button></div></nav></div>`;
  if (selection) {
    const input = $(`#search-${resource}`);
    input?.focus({ preventScroll: true });
    input?.setSelectionRange(...selection);
  }
}
function setSearch(resource, value) {
  clearTimeout(searchTimer); ++listRequestVersion;
  state.search = value; state.offset = 0; state.loading = true; state.listError = '';
  renderResource(resource);
  searchTimer = setTimeout(() => loadResource(resource), 300);
}
function setStatus(resource, value) {
  state.status = value; state.offset = 0;
  return loadResource(resource);
}
function changePage(resource, direction) {
  if (state.loading || ![-1, 1].includes(direction)) return;
  state.offset = Math.max(0, state.offset + direction * state.limit);
  return loadResource(resource);
}
function setPageSize(resource, value) {
  const limit = Number(value);
  if (![10, 25, 50, 100].includes(limit)) return;
  state.limit = limit; state.offset = 0;
  return loadResource(resource);
}
function quoteTechnicalForm(row) {
  const costs = [['Material', 'material_cost'], ['Ferragens', 'hardware_cost'], ['Mão de obra', 'labor_cost'], ['Acabamento', 'finishing_cost']];
  return recordLookupField('Cliente', 'customers', 'customer_id', row.customer_id)
    + field('Descrição', 'description', 'textarea', row.description || '', true, 'minlength="3" maxlength="3000"')
    + field('Medidas', 'measurements', 'textarea', row.measurements || '', false, 'maxlength="2000"')
    + field('Materiais', 'materials', 'textarea', row.materials || '', false, 'maxlength="2000"')
    + costs.map(([label, name]) => field(label, name, 'number', row[name] ?? 0, true, 'min="0" step="0.01"')).join('')
    + field('Margem de lucro (%)', 'profit_margin', 'number', row.profit_margin ?? 30, true, 'min="0" max="100" step="0.01"')
    + '<p class="muted">O preço e a análise serão recalculados. Aprovação e resposta do cliente são registradas pelos botões do orçamento.</p>';
}
function formatCell(resource,key,value){if(value===null||value===undefined||value==='')return'<span class="muted">—</span>';if(key==='price'||key==='total')return money(value);if(key==='is_admin')return value?'<span class="badge success">Administrador</span>':'<span class="badge">Usuário</span>';if(key==='is_active')return value?'<span class="badge success">Ativo</span>':'<span class="badge">Inativo</span>';if(key==='status')return`<span class="badge">${escapeHtml(statusLabels[value]||value)}</span>`;if(key==='category_id')return escapeHtml(state.categories.find(x=>x.id===value)?.name||`#${value}`);if(key==='customer_id')return escapeHtml(state.customers.find(x=>x.id===value)?.name||`#${value}`);if(key==='created_at'||key==='project_date')return new Date(value).toLocaleString('pt-BR');return escapeHtml(value)}
function field(label,name,type='text',value='',required=false,extra=''){return`<label>${label}${type==='textarea'?`<textarea name="${name}" ${required?'required':''} ${extra}>${escapeHtml(value)}</textarea>`:`<input name="${name}" type="${type}" value="${escapeHtml(value)}" ${required?'required':''} ${extra}>`}</label>`}
function selectField(label, name, options, value = '') {
  if (name === 'customer_id') return recordLookupField(label, 'customers', name, value);
  if (name === 'category_id') return recordLookupField(label, 'categories', name, value);
  return `<label>${label}<select name="${name}" required><option value="">Selecione...</option>${options.map(option => `<option value="${option.id}" ${String(option.id) === String(value) ? 'selected' : ''}>${escapeHtml(option.name)}</option>`).join('')}</select></label>`;
}
function recordLookupField(label, collection, name, value = '') {
  const selected = state[collection].find(row => String(row.id) === String(value));
  return `<div class="record-lookup" data-collection="${collection}"><div>${escapeHtml(label)}</div><input type="search" data-lookup-search maxlength="200" autocomplete="off" placeholder="Pesquisar em todos os registros..." aria-label="Pesquisar ${escapeHtml(label.toLowerCase())}"><select name="${name}" aria-label="${escapeHtml(label)}" required data-lookup-selected="${escapeHtml(value)}"><option value="">Selecione...</option>${selected ? `<option value="${selected.id}" selected>${escapeHtml(selected.name)}</option>` : ''}</select><div class="lookup-pagination"><button type="button" class="small-btn" data-lookup-prev disabled>Anterior</button><small data-lookup-info aria-live="polite">Carregando opções...</small><button type="button" class="small-btn" data-lookup-next disabled>Próxima</button></div></div>`;
}
async function setupRecordLookups(root) {
  await Promise.all($$('.record-lookup', root).map(async element => {
    const collection = element.dataset.collection;
    if (!['customers', 'categories'].includes(collection)) return;
    const input = $('[data-lookup-search]', element), select = $('select', element);
    const previous = $('[data-lookup-prev]', element), next = $('[data-lookup-next]', element), info = $('[data-lookup-info]', element);
    const pageSize = 25;
    let offset = 0, version = 0, timer = null, selectedId = select.dataset.lookupSelected || '', selected = null;
    if (selectedId) {
      await ensureReferences(collection, [Number(selectedId)]);
      selected = state[collection].find(row => String(row.id) === selectedId) || null;
    }
    async function load() {
      const requestVersion = ++version;
      previous.disabled = true; next.disabled = true;
      info.textContent = 'Buscando opções...';
      const params = new URLSearchParams({ offset: String(offset), limit: String(pageSize) });
      if (input.value.trim()) params.set('q', input.value.trim());
      try {
        const rows = await api(`/${collection}?${params}`);
        if (requestVersion !== version || element.isConnected === false) return;
        mergeReferences(collection, rows);
        const options = selected && !rows.some(row => row.id === selected.id) ? [selected, ...rows] : rows;
        select.innerHTML = `<option value="">Selecione...</option>${options.map(row => `<option value="${row.id}" ${String(row.id) === selectedId ? 'selected' : ''}>${escapeHtml(row.name)}${row.email ? ` — ${escapeHtml(row.email)}` : ''}</option>`).join('')}`;
        select.value = selectedId;
        const total = rows.pagination?.total;
        info.textContent = `${total == null ? rows.length + ' nesta página' : total + ' encontrado(s)'} · Página ${Math.floor(offset / pageSize) + 1}`;
        previous.disabled = offset === 0;
        next.disabled = total == null ? rows.length < pageSize : offset + rows.length >= total;
      } catch (error) {
        if (requestVersion !== version || element.isConnected === false) return;
        info.textContent = `Não foi possível buscar: ${error.message}. Digite novamente para tentar.`;
      }
    }
    select.addEventListener('change', () => {
      selectedId = select.value;
      selected = state[collection].find(row => String(row.id) === selectedId) || null;
    });
    input.addEventListener('input', () => {
      ++version; clearTimeout(timer); offset = 0;
      previous.disabled = true; next.disabled = true;
      timer = setTimeout(load, 300);
    });
    previous.addEventListener('click', () => { offset = Math.max(0, offset - pageSize); return load(); });
    next.addEventListener('click', () => { offset += pageSize; return load(); });
    await load();
  }));
}
function formHtml(resource,row={}){if(resource==='customers')return field('Nome','name','text',row.name||'',true,'maxlength="160"')+field('E-mail','email','email',row.email||'')+field('Telefone','phone','tel',row.phone||'')+field('Endereço','address','text',row.address||'',false,'maxlength="500"');if(resource==='categories')return field('Nome','name','text',row.name||'',true,'maxlength="120"')+field('Descrição','description','textarea',row.description||'',false,'maxlength="500"');if(resource==='products')return selectField('Categoria','category_id',state.categories,row.category_id)+field('Nome','name','text',row.name||'',true,'maxlength="160"')+field('Descrição','description','textarea',row.description||'')+field('Valor','price','number',row.price??0,true,'min="0" step="0.01"')+field('Imagem (URL)','image_url','url',row.image_url||'')+`<label class="check"><input name="is_active" type="checkbox" ${row.is_active!==false?'checked':''}> Ativo</label>`;if(resource==='quotes')return selectField('Cliente','customer_id',state.customers,row.customer_id)+field('Descrição','description','textarea',row.description||'',true,'maxlength="3000"')+field('Medidas','measurements','textarea',row.measurements||'',false,'maxlength="2000" placeholder="Ex.: 2,40m x 0,60m"')+field('Materiais','materials','textarea',row.materials||'',false,'maxlength="2000"')+field('Valor total','total','number',row.total??0,true,'min="0" step="0.01"')+`<label>Status<select name="status"><option value="pending" ${row.status==='pending'||!row.status?'selected':''}>Pendente</option><option value="analysis" ${row.status==='analysis'?'selected':''}>Em análise</option><option value="approved" ${row.status==='approved'?'selected':''}>Aprovado</option><option value="rejected" ${row.status==='rejected'?'selected':''}>Recusado</option><option value="completed" ${row.status==='completed'?'selected':''}>Concluído</option></select></label>`;if(resource==='projects')return selectField('Cliente','customer_id',state.customers,row.customer_id)+field('Nome do projeto','name','text',row.name||'',true,'maxlength="160"')+field('Descrição','description','textarea',row.description||'',false,'maxlength="5000"')+field('Medidas','measurements','textarea',row.measurements||'',false,'maxlength="2000"')+field('Materiais','materials','textarea',row.materials||'',false,'maxlength="2000"')+field('Data','project_date','date',row.project_date||'')+`<label>Status<select name="status"><option value="planning" ${row.status==='planning'||!row.status?'selected':''}>Planejamento</option><option value="in_progress" ${row.status==='in_progress'?'selected':''}>Em andamento</option><option value="completed" ${row.status==='completed'?'selected':''}>Concluído</option><option value="cancelled" ${row.status==='cancelled'?'selected':''}>Cancelado</option></select></label>`+field('Fotos (URLs, uma por linha)','photos','textarea',(row.photos||[]).join('\n'),false,'placeholder="https://..."');if(resource==='users')return field('Nome','name','text',row.name||'',true,'maxlength="120"')+field('E-mail','email','email',row.email||'',true)+`<label>Status<select name="is_active"><option value="true" ${row.is_active?'selected':''}>Ativo</option><option value="false" ${!row.is_active?'selected':''}>Inativo</option></select></label><label>Permissão<select name="is_admin"><option value="true" ${row.is_admin?'selected':''}>Administrador</option><option value="false" ${!row.is_admin?'selected':''}>Usuário</option></select></label>`}
async function openForm(resource, id = null) {
  state.resource = resource; state.id = id;
  const row = id ? (state.listResource === resource ? state.rows.find(item => item.id === id) : null) || await api(`${configs[resource].endpoint}/${id}`) : {};
  if (resource === 'quotes' && id && !['pending', 'analysis'].includes(row.status)) throw new Error('Este orçamento já tem uma decisão registrada. Consulte a proposta ou crie uma nova revisão.');
  if (row.customer_id) await ensureReferences('customers', [row.customer_id]);
  if (row.category_id) await ensureReferences('categories', [row.category_id]);
  $('#modal-title').textContent = `${id ? 'Editar' : 'Novo'} ${resource === 'quotes' ? 'orçamento' : resource === 'customers' ? 'cliente' : resource === 'projects' ? 'projeto' : resource === 'products' ? 'produto' : resource === 'categories' ? 'serviço' : 'usuário'}`;
  const form = $('#item-form');
  form.innerHTML = `<div class="form-grid">${resource === 'quotes' ? quoteTechnicalForm(row) : formHtml(resource, row)}</div><div class="modal-actions"><button type="button" class="btn secondary" onclick="closeModal()">Cancelar</button><button type="submit" class="btn primary">${id ? 'Salvar alterações' : 'Cadastrar'}</button></div>`;
  // Production stages now use the dedicated /projects/{id}/status workflow.
  if (resource === 'projects') form.querySelector('select[name="status"]')?.closest('label')?.remove();
  $('#modal').classList.remove('hidden'); $('#modal').setAttribute('aria-hidden', 'false');
  await setupRecordLookups(form);
}
function createItem(resource){return openForm(resource).catch(error=>toast(error.message,'error'))}function editItem(resource,id){return openForm(resource,id).catch(error=>toast(error.message,'error'))}function closeModal(){$('#modal').classList.add('hidden');$('#modal').setAttribute('aria-hidden','true');$('#item-form').innerHTML=''}
async function submitItem(e) {
  e.preventDefault();
  if ($('.smart-quote-create', e.target) || $('.history-modal', e.target)) return;
  const fd = new FormData(e.target), resource = state.resource, payload = {};
  for (const [key, value] of fd.entries()) payload[key] = value;
  if (resource === 'products') { payload.category_id = Number(payload.category_id); payload.price = Number(payload.price); payload.is_active = fd.has('is_active'); }
  if (resource === 'quotes') {
    payload.customer_id = Number(payload.customer_id);
    delete payload.status; delete payload.total;
    ['material_cost', 'hardware_cost', 'labor_cost', 'finishing_cost', 'profit_margin'].forEach(key => { if (key in payload) payload[key] = Number(payload[key]); });
  }
  if (resource === 'projects') { payload.customer_id = Number(payload.customer_id); payload.project_date = payload.project_date || null; payload.photos = String(payload.photos || '').split(/\n|,/).map(value => value.trim()).filter(Boolean); }
  if (resource === 'users') { payload.is_active = payload.is_active === 'true'; payload.is_admin = payload.is_admin === 'true'; }
  if (resource === 'projects') delete payload.status;
  const button = $('button[type="submit"]', e.target);
  if (button) button.disabled = true;
  try {
    const endpoint = resource === 'users' ? `/admin/users/${state.id}` : state.id ? `${configs[resource].endpoint}/${state.id}` : configs[resource].endpoint;
    const method = resource === 'users' ? 'PATCH' : state.id ? 'PUT' : 'POST';
    const saved = await api(endpoint, { method, body: payload });
    if (['customers', 'categories'].includes(resource)) mergeReferences(resource, [saved]);
    closeModal(); toast(state.id ? 'Alterações salvas com sucesso.' : 'Cadastro realizado com sucesso.');
    await loadResource(resource);
  } catch (error) { toast(error.message, 'error'); }
  finally { if (button) button.disabled = false; }
}
async function deleteItem(resource,id){if(!confirm('Excluir este registro? Esta ação não pode ser desfeita.'))return;try{await api(`${configs[resource].endpoint}/${id}`,{method:'DELETE'});toast('Registro excluído.');await loadResource(resource)}catch(err){toast(err.message,'error')}}
async function viewCustomerHistory(id) {
  const customer = state.rows.find(row => row.id === id), form = $('#item-form');
  $('#modal-title').textContent = `Histórico — ${customer?.name || `Cliente #${id}`}`;
  form.innerHTML = '<div class="history-modal"><label>Pesquisar histórico<input type="search" id="history-search" maxlength="200" placeholder="Pesquisar em todo o histórico..."></label><div id="history-rows" aria-live="polite"></div><nav class="pagination" aria-label="Páginas do histórico"><button type="button" class="btn secondary" id="history-prev" disabled>Anterior</button><span id="history-count"></span><button type="button" class="btn secondary" id="history-next" disabled>Próxima</button><button type="button" class="btn secondary hidden" id="history-retry">Tentar novamente</button></nav></div><div class="modal-actions"><button type="button" class="btn secondary" onclick="closeModal()">Fechar</button></div>';
  const input = $('#history-search'), list = $('#history-rows'), count = $('#history-count');
  const previous = $('#history-prev'), next = $('#history-next'), retry = $('#history-retry');
  let offset = 0, version = 0, timer = null;
  async function load() {
    const requestVersion = ++version;
    previous.disabled = true; next.disabled = true; retry.classList.add('hidden'); list.textContent = 'Carregando histórico...';
    const params = new URLSearchParams({ offset: String(offset), limit: '25' });
    if (input.value.trim()) params.set('q', input.value.trim());
    try {
      const rows = await api(`/customers/${id}/history?${params}`);
      if (requestVersion !== version || list.isConnected === false) return;
      list.innerHTML = rows.length ? rows.map(item => `<div class="history-item"><strong>${escapeHtml(item.description)}</strong><span>${new Date(item.created_at).toLocaleString('pt-BR')}</span></div>`).join('') : '<p class="muted">Nenhuma atividade corresponde à pesquisa.</p>';
      const total = rows.pagination?.total;
      count.textContent = `${total == null ? rows.length + ' nesta página' : total + ' registro(s)'} · Página ${Math.floor(offset / 25) + 1}`;
      previous.disabled = offset === 0;
      next.disabled = total == null ? rows.length < 25 : offset + rows.length >= total;
    } catch (error) {
      if (requestVersion !== version || list.isConnected === false) return;
      list.textContent = error.message; count.textContent = ''; retry.classList.remove('hidden');
    }
  }
  previous.addEventListener('click', () => { offset = Math.max(0, offset - 25); return load(); });
  next.addEventListener('click', () => { offset += 25; return load(); });
  retry.addEventListener('click', load);
  input.addEventListener('input', () => { ++version; clearTimeout(timer); offset = 0; previous.disabled = true; next.disabled = true; timer = setTimeout(load, 300); });
  $('#modal').classList.remove('hidden'); $('#modal').setAttribute('aria-hidden', 'false');
  await load();
}
async function boot(){setupPublic();setupAdmin();try{await api('/auth/csrf');const me=await api('/me');if(me?.is_admin){state.user=me;enterAdmin()}}catch(_){} }
boot();
