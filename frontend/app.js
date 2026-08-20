const API = window.API_BASE_URL || 'http://localhost:8000/api/v1';
const $ = (s) => document.querySelector(s);
const csrf = () => document.cookie.split('; ').find(x => x.startsWith('csrf_token='))?.split('=')[1] || '';

async function api(path, options = {}) {
  const opts = { credentials: 'include', ...options, headers: { ...(options.headers || {}) } };
  if (opts.body && typeof opts.body !== 'string') {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(opts.body);
  }
  if (['POST','PUT','PATCH','DELETE'].includes(opts.method) && csrf()) opts.headers['X-CSRF-Token'] = csrf();
  const res = await fetch(API + path, opts);
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || 'Erro na API');
  return data;
}

$('#login-form').addEventListener('submit', async (e) => {
  e.preventDefault(); $('#login-error').textContent = '';
  const body = new URLSearchParams({ username: $('#email').value, password: $('#password').value });
  try {
    await api('/auth/login', { method: 'POST', headers: {'Content-Type':'application/x-www-form-urlencoded'}, body });
    await loadDashboard();
    $('#login').classList.add('hidden'); $('#app').classList.remove('hidden');
  } catch (err) { $('#login-error').textContent = err.message; }
});

$('#logout').addEventListener('click', async () => { try { await api('/auth/logout',{method:'POST'}); } finally { location.reload(); } });

document.querySelectorAll('.nav').forEach(btn => btn.addEventListener('click', () => showSection(btn.dataset.section)));
function showSection(name) {
  document.querySelectorAll('.section').forEach(x => x.classList.add('hidden'));
  $('#' + name).classList.remove('hidden');
  document.querySelectorAll('.nav').forEach(x => x.classList.toggle('active', x.dataset.section === name));
  $('#title').textContent = name[0].toUpperCase() + name.slice(1);
  if (name === 'dashboard') loadDashboard();
  if (name === 'products') loadResource('products', ['id','name','category_id','price','is_active']);
  if (name === 'categories') loadResource('categories', ['id','name','description']);
  if (name === 'customers') loadResource('customers', ['id','name','email','phone']);
  if (name === 'quotes') loadResource('quotes', ['id','customer_id','status','total']);
}

async function loadDashboard() {
  try {
    const data = await api('/admin/dashboard');
    $('#user-badge').textContent = 'Administrador';
    $('#dashboard').innerHTML = `<div class="grid">${Object.entries(data.counts).map(([k,v])=>`<div class="stat"><span>${k}</span><strong>${v}</strong></div>`).join('')}</div><div class="panel"><h2>Visão geral</h2><p>API, PostgreSQL, autenticação e permissões de administrador estão conectados.</p></div>`;
  } catch (err) { $('#dashboard').innerHTML = `<div class="panel"><h2>Acesso negado</h2><p>${err.message}</p></div>`; }
}

async function loadResource(resource, columns) {
  const section = $('#' + resource);
  section.innerHTML = '<div class="panel">Carregando...</div>';
  try {
    const rows = await api('/' + resource + '?limit=100');
    section.innerHTML = `<div class="panel"><div class="toolbar"><h2>${resource}</h2><button class="primary" onclick="createItem('${resource}')">Novo</button></div><div class="table-wrap"><table><thead><tr>${columns.map(c=>`<th>${c}</th>`).join('')}<th>Ações</th></tr></thead><tbody>${rows.map(row=>`<tr>${columns.map(c=>`<td>${row[c] ?? ''}</td>`).join('')}<td class="actions"><button onclick="editItem('${resource}',${row.id})">Editar</button><button onclick="deleteItem('${resource}',${row.id})">Excluir</button></td></tr>`).join('')}</tbody></table></div></div>`;
  } catch (err) { section.innerHTML = `<div class="panel"><h2>${resource}</h2><p>${err.message}</p></div>`; }
}

async function deleteItem(resource,id){ if(!confirm('Excluir este registro?')) return; try{await api(`/${resource}/${id}`,{method:'DELETE'});loadResource(resource,resource==='products'?['id','name','category_id','price','is_active']:resource==='categories'?['id','name','description']:resource==='customers'?['id','name','email','phone']:['id','customer_id','status','total']);}catch(e){alert(e.message)} }

async function createItem(resource){
  const name = prompt('Nome:'); if(!name) return;
  let payload;
  if(resource==='categories') payload={name,description:prompt('Descrição:')||null};
  else if(resource==='products') payload={category_id:Number(prompt('ID da categoria:')),name,description:prompt('Descrição:')||null,price:Number(prompt('Preço:')||0),image_url:null,is_active:true};
  else { alert('Cadastro rápido disponível nesta etapa apenas para categorias e produtos.'); return; }
  try{await api('/'+resource,{method:'POST',body:payload});loadResource(resource,resource==='products'?['id','name','category_id','price','is_active']:['id','name','description']);}catch(e){alert(e.message)}
}

async function editItem(resource,id){
  const name=prompt('Novo nome:'); if(!name) return;
  try{await api(`/${resource}/${id}`,{method:'PUT',body:resource==='categories'?{name,description:null}:{category_id:1,name,description:null,price:0,image_url:null,is_active:true}}); showSection(resource);}catch(e){alert(e.message)}
}

loadDashboard();
