const API = window.API_BASE_URL || (window.location.origin.includes('localhost') ? 'http://localhost:8000/api/v1' : `${window.location.origin}/api/v1`);
const $ = (selector) => document.querySelector(selector);
const csrf = () => document.cookie.split('; ').find(x => x.trim().startsWith('csrf_token='))?.split('=')[1] || '';
const labels = { products:'Produtos', categories:'Categorias', customers:'Clientes', quotes:'Orçamentos' };
const state = { resource:null, id:null, rows:[], categories:[], customers:[] };

function escapeHtml(value='') { return String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function money(value) { return Number(value || 0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'}); }
function showToast(message, type='success') { const el=$('#toast'); el.textContent=message; el.className=`toast show ${type}`; clearTimeout(showToast.timer); showToast.timer=setTimeout(()=>el.className='toast',3200); }

async function api(path, options={}) {
  const opts={credentials:'include',...options,headers:{...(options.headers||{})}};
  if (opts.body && !(opts.body instanceof URLSearchParams) && typeof opts.body !== 'string') { opts.headers['Content-Type']='application/json'; opts.body=JSON.stringify(opts.body); }
  if (['POST','PUT','PATCH','DELETE'].includes(opts.method) && csrf()) opts.headers['X-CSRF-Token']=csrf();
  const res=await fetch(API+path,opts);
  if (res.status===204) return null;
  const data=await res.json().catch(()=>({}));
  if (!res.ok) throw new Error(data.detail || (res.status===401?'Sessão expirada. Entre novamente.':'Não foi possível concluir a operação.'));
  return data;
}

$('#login-form').addEventListener('submit',async e=>{
  e.preventDefault(); $('#login-error').textContent='';
  try {
    const body=new URLSearchParams({username:$('#email').value.trim().toLowerCase(),password:$('#password').value});
    await api('/auth/login',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});
    $('#login').classList.add('hidden'); $('#app').classList.remove('hidden');
    await loadDashboard();
  } catch(err) { $('#login-error').textContent=err.message; }
});
$('#logout').addEventListener('click',async()=>{try{await api('/auth/logout',{method:'POST'});}finally{location.reload();}});
document.querySelectorAll('.nav').forEach(btn=>btn.addEventListener('click',()=>showSection(btn.dataset.section)));
$('#modal-close').addEventListener('click',closeModal);
$('#modal').addEventListener('click',e=>{if(e.target.id==='modal')closeModal();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});

function showSection(name) {
  document.querySelectorAll('.section').forEach(x=>x.classList.add('hidden'));
  $('#'+name).classList.remove('hidden');
  document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('active',x.dataset.section===name));
  $('#title').textContent=labels[name]||'Dashboard';
  if(name==='dashboard') loadDashboard(); else loadResource(name);
}

async function loadDashboard() {
  try {
    const data=await api('/admin/dashboard');
    $('#user-badge').textContent='Administrador';
    const counts=data.counts||{};
    const cards=[['Usuários',counts.users||0,'users'],['Categorias',counts.categories||0,'categories'],['Produtos',counts.products||0,'products'],['Clientes',counts.customers||0,'customers'],['Orçamentos',counts.quotes||0,'quotes']];
    $('#dashboard').innerHTML=`<div class="welcome"><div><span class="eyebrow">Visão geral</span><h2>Bem-vindo ao painel 👋</h2><p>Gerencie produtos, clientes e orçamentos em um só lugar.</p></div><button class="primary" onclick="showSection('products')">Ver produtos</button></div><div class="stats">${cards.map(c=>`<button class="stat" onclick="showSection('${c[2]}')"><span>${c[0]}</span><strong>${c[1]}</strong><small>Ver ${c[0].toLowerCase()} →</small></button>`).join('')}</div><div class="panel"><div class="panel-title"><div><span class="eyebrow">Sistema</span><h3>Base operacional</h3></div><span class="badge success">Online</span></div><p>API, PostgreSQL, autenticação e permissões administrativas estão conectados.</p></div>`;
  } catch(err) { $('#dashboard').innerHTML=`<div class="empty"><h2>Acesso administrativo necessário</h2><p>${escapeHtml(err.message)}</p></div>`; }
}

const config={
  products:{title:'Produtos',columns:[['name','Produto'],['category_id','Categoria'],['price','Preço'],['is_active','Status']],empty:'Nenhum produto cadastrado.'},
  categories:{title:'Categorias',columns:[['name','Categoria'],['description','Descrição']],empty:'Nenhuma categoria cadastrada.'},
  customers:{title:'Clientes',columns:[['name','Cliente'],['email','E-mail'],['phone','Telefone']],empty:'Nenhum cliente cadastrado.'},
  quotes:{title:'Orçamentos',columns:[['customer_id','Cliente'],['status','Status'],['total','Total']],empty:'Nenhum orçamento cadastrado.'}
};

async function loadResource(resource) {
  const section=$('#'+resource); const cfg=config[resource];
  section.innerHTML='<div class="loading panel">Carregando...</div>';
  try {
    if(resource==='products') state.categories=await api('/categories?limit=100');
    if(resource==='quotes') state.customers=await api('/customers?limit=100');
    const rows=await api('/'+resource+'?limit=100'); state.rows=rows;
    const headers=cfg.columns.map(c=>`<th>${c[1]}</th>`).join('');
    const body=rows.length?rows.map(row=>`<tr>${cfg.columns.map(([key])=>`<td>${formatCell(resource,key,row[key])}</td>`).join('')}<td class="actions"><button class="btn" onclick="editItem('${resource}',${row.id})">Editar</button><button class="btn danger" onclick="deleteItem('${resource}',${row.id})">Excluir</button></td></tr>`).join(''):`<tr><td colspan="${cfg.columns.length+1}" class="empty-row">${cfg.empty}</td></tr>`;
    section.innerHTML=`<div class="panel"><div class="toolbar"><div><span class="eyebrow">Gerenciamento</span><h2>${cfg.title}</h2><p>${rows.length} registro(s)</p></div><button class="primary" onclick="createItem('${resource}')">+ Novo</button></div><div class="table-wrap"><table><thead><tr>${headers}<th>Ações</th></tr></thead><tbody>${body}</tbody></table></div></div>`;
  } catch(err) { section.innerHTML=`<div class="empty"><h2>Não foi possível carregar</h2><p>${escapeHtml(err.message)}</p><button class="primary" onclick="loadResource('${resource}')">Tentar novamente</button></div>`; }
}
function formatCell(resource,key,value) {
  if(value===null||value===undefined) return '<span class="muted">—</span>';
  if(key==='price'||key==='total') return money(value);
  if(key==='is_active') return value?'<span class="badge success">Ativo</span>':'<span class="badge">Inativo</span>';
  if(key==='status') return `<span class="badge status-${escapeHtml(value)}">${statusLabel(value)}</span>`;
  if(key==='category_id'&&resource==='products') return escapeHtml(state.categories.find(x=>x.id===value)?.name||`#${value}`);
  if(key==='customer_id'&&resource==='quotes') return escapeHtml(state.customers.find(x=>x.id===value)?.name||`#${value}`);
  return escapeHtml(value);
}
function statusLabel(v){return ({pending:'Pendente',approved:'Aprovado',rejected:'Recusado',completed:'Concluído'})[v]||v;}

function field(label,name,type='text',value='',required=false,extra='') { return `<label>${label}${type==='textarea'?`<textarea name="${name}" ${required?'required':''} ${extra}>${escapeHtml(value)}</textarea>`:`<input name="${name}" type="${type}" value="${escapeHtml(value)}" ${required?'required':''} ${extra}>`}</label>`; }
function selectField(label,name,options,value='') { return `<label>${label}<select name="${name}" required><option value="">Selecione...</option>${options.map(o=>`<option value="${o.id}" ${String(o.id)===String(value)?'selected':''}>${escapeHtml(o.name)}</option>`).join('')}</select></label>`; }

function formHtml(resource,row={}) {
  if(resource==='categories') return field('Nome','name','text',row.name||'',true,'maxlength="120"')+field('Descrição','description','textarea',row.description||'','false','maxlength="500"');
  if(resource==='products') return field('Nome','name','text',row.name||'',true,'maxlength="160"')+selectField('Categoria','category_id',state.categories,row.category_id)+field('Descrição','description','textarea',row.description||'','false','maxlength="2000"')+field('Preço','price','number',row.price??0,true,'min="0" step="0.01"')+field('Imagem (URL)','image_url','url',row.image_url||'','false')+`<label class="check"><input name="is_active" type="checkbox" ${row.is_active!==false?'checked':''}> Produto ativo</label>`;
  if(resource==='customers') return field('Nome','name','text',row.name||'',true,'maxlength="160"')+field('E-mail','email','email',row.email||'',false)+field('Telefone','phone','tel',row.phone||'',false)+field('Endereço','address','text',row.address||'',false,'maxlength="300"');
  if(resource==='quotes') return selectField('Cliente','customer_id',state.customers,row.customer_id)+field('Descrição','description','textarea',row.description||'','false','maxlength="2000"')+field('Valor total','total','number',row.total??0,true,'min="0" step="0.01"')+`<label>Status<select name="status"><option value="pending" ${row.status==='pending'?'selected':''}>Pendente</option><option value="approved" ${row.status==='approved'?'selected':''}>Aprovado</option><option value="rejected" ${row.status==='rejected'?'selected':''}>Recusado</option><option value="completed" ${row.status==='completed'?'selected':''}>Concluído</option></select></label>`;
}

async function openForm(resource,id=null){
  state.resource=resource; state.id=id; let row={};
  if(resource==='products'&&!state.categories.length) state.categories=await api('/categories?limit=100');
  if(resource==='quotes'&&!state.customers.length) state.customers=await api('/customers?limit=100');
  if(id) row=state.rows.find(x=>x.id===id)||await api(`/${resource}/${id}`);
  $('#modal-title').textContent=`${id?'Editar':'Novo'} ${config[resource].title.slice(0,-1)}`;
  $('#item-form').innerHTML=`<div class="form-grid">${formHtml(resource,row)}</div><div class="modal-actions"><button type="button" class="btn" onclick="closeModal()">Cancelar</button><button type="submit" class="primary">${id?'Salvar alterações':'Cadastrar'}</button></div>`;
  $('#modal').classList.remove('hidden'); $('#modal').setAttribute('aria-hidden','false');
}
function createItem(resource){openForm(resource);}
function editItem(resource,id){openForm(resource,id);}
function closeModal(){ $('#modal').classList.add('hidden'); $('#modal').setAttribute('aria-hidden','true'); $('#item-form').reset?.(); }

$('#item-form').addEventListener('submit',async e=>{
  e.preventDefault(); const fd=new FormData(e.target); const resource=state.resource; const payload=Object.fromEntries(fd.entries());
  if(resource==='products'){payload.category_id=Number(payload.category_id);payload.price=Number(payload.price);payload.is_active=fd.has('is_active');}
  if(resource==='quotes'){payload.customer_id=Number(payload.customer_id);payload.total=Number(payload.total);}
  try { await api(state.id?`/${resource}/${state.id}`:`/${resource}`,{method:state.id?'PUT':'POST',body:payload}); closeModal(); showToast(state.id?'Alterações salvas.':'Cadastro realizado.'); await loadResource(resource); } catch(err){showToast(err.message,'error');}
});

async function deleteItem(resource,id){
  if(!confirm('Tem certeza que deseja excluir este registro? Esta ação não pode ser desfeita.')) return;
  try { await api(`/${resource}/${id}`,{method:'DELETE'}); showToast('Registro excluído.'); await loadResource(resource); } catch(err){showToast(err.message,'error');}
}

loadDashboard();
