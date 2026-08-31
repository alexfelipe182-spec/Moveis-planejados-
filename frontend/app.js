const API = window.API_BASE_URL || (location.hostname === 'localhost' ? 'http://localhost:8000/api/v1' : 'https://ideal-marcenaria-api.onrender.com/api/v1');
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const state = { user:null, resource:null, listResource:null, id:null, rows:[], categories:[], customers:[], search:'', status:'', csrfToken:'', workspaceAccess:null, offset:0, limit:25, total:0, loading:false, listError:'' };
const labels = {dashboard:'Dashboard',customers:'Clientes',quotes:'Orçamentos',projects:'Projetos',products:'Produtos',categories:'Serviços',users:'Usuários',activities:'Histórico',intelligence:'Central inteligente',workspace:'Plano e equipe',platform:'Plataforma'};
const statusLabels = {pending:'Pendente',analysis:'Em análise',approved:'Aprovado',rejected:'Recusado',completed:'Concluído',planning:'Planejamento',in_progress:'Em andamento',cancelled:'Cancelado'};
const csrf = () => state.csrfToken || document.cookie.split('; ').find(x=>x.startsWith('csrf_token='))?.split('=')[1] || '';
const escapeHtml = (v='') => String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const money = v => Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
let refreshPromise = null;
let sessionVersion = 0;
let listRequestVersion = 0;
let searchTimer = null;
function apiErrorMessage(status, data) {
  if (status === 429) return 'Muitas tentativas em pouco tempo. Aguarde um momento antes de tentar novamente.';
  if (status >= 500) return 'O servidor está temporariamente indisponível. Tente novamente em instantes.';
  if (Array.isArray(data?.detail)) {
    const names = {name:'Nome',email:'E-mail',password:'Senha',customer_id:'Cliente',category_id:'Categoria',supplier_id:'Fornecedor',description:'Descrição',price:'Valor',unit_cost:'Custo unitário',quantity:'Quantidade',waste_percent:'Perda (%)'};
    const fields = [...new Set(data.detail.map(item => names[item?.loc?.at(-1)]).filter(Boolean))];
    return fields.length ? `Revise os campos informados: ${fields.join(', ')}.` : 'Revise os campos do formulário. Há valores inválidos ou obrigatórios não preenchidos.';
  }
  if (typeof data?.detail === 'string' && data.detail.trim()) return data.detail.slice(0, 600);
  return status === 401 ? 'Sessão expirada. Faça login novamente.' : status === 403 ? 'Sua conta não tem permissão para esta ação.' : `Não foi possível concluir a solicitação (erro ${status}).`;
}
function toast(message,type='success'){
  const el=$('#toast');if(!el)return;
  const urgent=type==='error';
  el.setAttribute('role',urgent?'alert':'status');
  el.setAttribute('aria-live',urgent?'assertive':'polite');
  el.setAttribute('aria-atomic','true');
  el.textContent=message;el.className=`toast show ${type}`;
  clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.className='toast',3500);
}
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
  const deadlineController = options.signal ? null : new AbortController();
  let deadline = deadlineController ? setTimeout(() => deadlineController.abort(), 20000) : null;
  if (deadlineController) opts.signal = deadlineController.signal;
  const clearDeadline = () => {
    if (deadline !== null) clearTimeout(deadline);
    deadline = null;
  };
  if (opts.body && !(opts.body instanceof URLSearchParams) && typeof opts.body !== 'string') {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(opts.body);
  }
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(opts.method) && csrf()) {
    opts.headers['X-CSRF-Token'] = csrf();
  }
  try {
    const res = await fetch(API + path, opts);
    if (res.status === 204) return null;
    let data;
    try { data = await res.json(); }
    catch (error) {
      if (error.name === 'AbortError') throw error;
      if (res.ok) throw new Error('O servidor retornou uma resposta inválida. Confira os dados antes de repetir a operação.');
      data = {};
    }
    clearDeadline();
    if (res.status === 401 && retryAuth && !path.startsWith('/auth/')) {
      // A delayed response may belong to the session another request already renewed.
      if (requestVersion === sessionVersion) await refreshSession();
      return api(path, options, false);
    }
    if (!res.ok) {
      const error = new Error(apiErrorMessage(res.status, data));
      error.status = res.status;
      throw error;
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
  } catch (error) {
    if (deadlineController?.signal.aborted && error.name === 'AbortError') {
      const timeoutError = new Error('A resposta demorou mais que o esperado. Verifique sua conexão e tente novamente.');
      timeoutError.name = 'RequestTimeoutError';
      throw timeoutError;
    }
    throw error;
  } finally {
    clearDeadline();
  }
}
let authView = null;
let authReturnFocus = null;
let modalReturnFocus = null;
let recoveryToken = '';
const registrationPlans = {
  starter: { name:'Essencial', price:'R$ 49/mês' },
  pro: { name:'Profissional', price:'R$ 99/mês' },
  scale: { name:'Empresarial', price:'R$ 249/mês' },
};
let selectedRegistrationPlan = 'starter';
function updateRegistrationPlan(code='starter') {
  if (!registrationPlans[code]) return;
  selectedRegistrationPlan=code;
  const summary=$('#register-plan-summary'), plan=registrationPlans[code];
  if(summary) summary.textContent=`Plano ${plan.name} selecionado · ${plan.price} após o teste.`;
}
function choosePublicPlan(code) {
  updateRegistrationPlan(code);
  openAuth('register');
}
async function hydratePublicPlanPrices() {
  try {
    const plans=await api('/plans');
    plans.forEach(plan=>{
      const card=$(`[data-public-plan="${plan.code}"]`);
      const price=card?.querySelector?.('[data-plan-price]');
      if(price) price.textContent=money(plan.monthly_price_cents/100);
      if(registrationPlans[plan.code]) registrationPlans[plan.code].price=`${money(plan.monthly_price_cents/100)}/mês`;
    });
    updateRegistrationPlan(selectedRegistrationPlan);
  } catch (_) {
    // The static catalog remains usable when a sleeping API is still waking up.
  }
}
function storeRecoveryToken(token) {
  recoveryToken = String(token || '');
  try { sessionStorage.setItem('reset_token', recoveryToken); } catch (_) {}
}
function readRecoveryToken() {
  try { return sessionStorage.getItem('reset_token') || recoveryToken; } catch (_) { return recoveryToken; }
}
function clearRecoveryToken() {
  recoveryToken = '';
  try { sessionStorage.removeItem('reset_token'); } catch (_) {}
}
function openAuth(view='login') {
  const overlay = $('#auth-overlay');
  if (overlay.classList.contains('hidden')) authReturnFocus = document.activeElement;
  overlay.classList.remove('hidden'); overlay.setAttribute('aria-hidden','false'); showAuth(view);
}
function hideLoginPassword() {
  const field = $('#login-password'), button = $('#toggle-login-password');
  if (field) field.type = 'password';
  if (button) { button.textContent = 'Mostrar senha'; button.setAttribute('aria-pressed','false'); }
}
function toggleLoginPassword() {
  const field = $('#login-password'), button = $('#toggle-login-password');
  const visible = field.type === 'password';
  field.type = visible ? 'text' : 'password';
  button.textContent = visible ? 'Ocultar senha' : 'Mostrar senha';
  button.setAttribute('aria-pressed',String(visible));
}
function closeAuth(restoreFocus = true) {
  const overlay = $('#auth-overlay');
  overlay.classList.add('hidden'); overlay.setAttribute('aria-hidden','true'); authView=null;
  hideLoginPassword();
  if (restoreFocus && authReturnFocus?.isConnected) authReturnFocus.focus();
  authReturnFocus = null;
}
function showAuth(view) {
  authView=view;
  ['login','register','recovery','reset'].forEach(v=>$(`#${v}-view`)?.classList.toggle('hidden',v!==view));
  $('#auth-overlay [role="dialog"]')?.setAttribute('aria-labelledby',`${view}-title`);
  hideLoginPassword();
  $(`#${view}-view input`)?.focus();
}
function handleDialogKeys(event) {
  const overlay = ['#auth-overlay','#modal'].map(selector=>$(selector)).find(node=>node && !node.classList.contains('hidden'));
  if (!overlay) return;
  if (event.key === 'Escape') {
    event.preventDefault();
    if (overlay.id === 'auth-overlay') closeAuth(); else closeModal();
    return;
  }
  if (event.key !== 'Tab') return;
  const controls = $$('button, a[href], input, select, textarea, [tabindex]',overlay)
    .filter(node=>!node.disabled && node.tabIndex>=0 && node.getClientRects().length>0);
  const first=controls[0], last=controls.at(-1), active=document.activeElement;
  if (!first) { event.preventDefault(); $('[role="dialog"]',overlay)?.focus(); return; }
  if (!controls.includes(active) || (event.shiftKey && active===first) || (!event.shiftKey && active===last)) {
    event.preventDefault(); (event.shiftKey?last:first).focus();
  }
}
function showWhatsApp(message='Olá! Quero solicitar um orçamento para móveis planejados.'){const number=window.WHATSAPP_NUMBER;if(number)window.open(`https://wa.me/${String(number).replace(/\D/g,'')}?text=${encodeURIComponent(message)}`,'_blank','noopener');else toast('Configure window.WHATSAPP_NUMBER para ativar o WhatsApp.','error')}
function handleAuthLink() {
  const hashToken = new URLSearchParams(location.hash.slice(1)).get('reset_token');
  const queryToken = new URLSearchParams(location.search).get('reset_token');
  const token = hashToken || queryToken;
  if (token) {
    storeRecoveryToken(token);
    history.replaceState({}, '', location.pathname);
    openAuth('reset');
  } else if (location.hash === '#login' && !state.user) {
    openAuth('login');
  }
}
function setupPublic() {
  $$('#open-login').forEach(b=>b.addEventListener('click',()=>openAuth('login')));
  $('#close-auth').addEventListener('click',closeAuth);
  $('#auth-overlay').addEventListener('click',e=>{if(e.target.id==='auth-overlay')closeAuth()});
  $$('[data-quote]').forEach(b=>b.addEventListener('click',()=>showWhatsApp()));
  $$('[data-plan-choice]').forEach(b=>b.addEventListener('click',()=>choosePublicPlan(b.dataset.planChoice)));
  $('#show-register').addEventListener('click',()=>showAuth('register'));
  $('#show-recovery').addEventListener('click',()=>showAuth('recovery'));
  $$('[data-auth-back]').forEach(b=>b.addEventListener('click',()=>showAuth('login')));
  $('#login-form').addEventListener('submit',login);
  $('#register-form').addEventListener('submit',register);
  $('#recovery-form').addEventListener('submit',recovery);
  $('#reset-form').addEventListener('submit',resetPassword);
  $('#toggle-login-password')?.addEventListener('click',toggleLoginPassword);
  window.addEventListener('hashchange', handleAuthLink);
  handleAuthLink();
  hydratePublicPlanPrices();
}
let loginInProgress = false;
let loginAttemptVersion = 0;
const pendingAuthForms = new WeakSet();
async function submitAuthForm(event, pendingLabel, action) {
  event.preventDefault();
  const form = event.currentTarget || event.target;
  if (!form || pendingAuthForms.has(form)) return false;
  const button = form.querySelector('button[type="submit"]');
  const originalLabel = button?.textContent || '';
  const originalDisabled = button?.disabled || false;
  pendingAuthForms.add(form);
  form.setAttribute('aria-busy','true');
  if (button) { button.disabled = true; button.textContent = pendingLabel; }
  try {
    await action(form);
    return true;
  } finally {
    pendingAuthForms.delete(form);
    form.removeAttribute('aria-busy');
    if (button) { button.disabled = originalDisabled; button.textContent = originalLabel; }
  }
}
function setFormMessage(element, text='', type='') {
  const error=type==='error';
  element.className=`form-message${type?` ${type}`:''}`;
  element.setAttribute('role',error?'alert':'status');
  element.setAttribute('aria-live',error?'assertive':'polite');
  element.setAttribute('aria-atomic','true');
  element.textContent=text;
}
async function login(e) {
  e.preventDefault();
  if (loginInProgress) return;
  const form = $('#login-form'), button = form.querySelector('button[type="submit"]');
  const message = $('#login-error'), originalLabel = button.textContent;
  message.textContent = ''; loginInProgress = true;
  loginAttemptVersion += 1;
  button.disabled = true; button.textContent = 'Entrando...'; form.setAttribute('aria-busy','true');
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  let authenticated = false, denied = false;
  try {
    const body = new URLSearchParams({username:$('#login-email').value.trim().toLowerCase(),password:$('#login-password').value});
    await api('/auth/login',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body,signal:controller.signal});
    authenticated = true;
    // A fresh login must establish cookies; do not mask a missing session with refresh.
    const user = await api('/me', {signal:controller.signal}, false);
    if (!user.is_admin) { denied = true; throw new Error('Sua conta ainda não possui permissão administrativa.'); }
    state.user = user; $('#login-password').value = '';
    enterAdmin();
  } catch (error) {
    state.user = null;
    if (error.name === 'AbortError') {
      message.textContent = 'A resposta demorou mais que o esperado. Não foi possível confirmar o acesso. Tente entrar novamente.';
    } else if (authenticated && error.status === 401) {
      message.textContent = 'A senha foi aceita, mas a sessão não foi mantida. Permita cookies para este site e abra a página no mesmo endereço usado para entrar.';
    } else if (!authenticated && error.status === 401) {
      message.textContent = 'E-mail ou senha incorretos. Confira os dados e tente novamente.';
    } else if (error.name === 'TypeError') {
      message.textContent = 'Não foi possível conectar ao servidor. Confira se a prévia está ligada e recarregue a página.';
    } else {
      message.textContent = error.message;
    }
    if (denied) await api('/auth/logout',{method:'POST',signal:controller.signal}).catch(()=>{});
  } finally {
    clearTimeout(timeout);
    loginInProgress = false; button.disabled = false; button.textContent = originalLabel;
    form.removeAttribute('aria-busy');
  }
}
async function register(e){return submitAuthForm(e,'Criando espaço...',async form=>{const msg=$('#register-message');setFormMessage(msg);try{await api('/auth/register',{method:'POST',body:{organization_name:$('#register-organization').value.trim(),name:$('#register-name').value.trim(),email:$('#register-email').value.trim().toLowerCase(),password:$('#register-password').value,plan_code:selectedRegistrationPlan}});setFormMessage(msg,`Marcenaria criada no plano ${registrationPlans[selectedRegistrationPlan].name}. Agora entre com seu e-mail e senha para abrir o painel.`,'success');form.reset()}catch(err){setFormMessage(msg,err.message,'error')}})}
async function recovery(e){return submitAuthForm(e,'Enviando...',async()=>{const msg=$('#recovery-message');setFormMessage(msg);try{const data=await api('/auth/password-reset/request',{method:'POST',body:{email:$('#recovery-email').value.trim().toLowerCase()}});setFormMessage(msg,data.message+(data.debug_token?' Token de teste gerado.':''),'success');if(data.debug_token){storeRecoveryToken(data.debug_token);setTimeout(()=>showAuth('reset'),500)}}catch(err){setFormMessage(msg,err.message,'error')}})}
async function resetPassword(e){return submitAuthForm(e,'Redefinindo...',async form=>{const msg=$('#reset-message');setFormMessage(msg);try{const token=readRecoveryToken();if(!token)throw new Error('Token de recuperação não encontrado. Solicite novamente.');await api('/auth/password-reset/confirm',{method:'POST',body:{token,new_password:$('#reset-password').value}});clearRecoveryToken();setFormMessage(msg,'Senha redefinida com sucesso. Faça login.','success');form.reset();setTimeout(()=>showAuth('login'),900)}catch(err){setFormMessage(msg,err.message,'error')}})}
function enterAdmin(){closeAuth(false);$('#public-site').classList.add('hidden');$('#admin-app').classList.remove('hidden');$('#user-badge').textContent=state.user?.name||'Administrador';syncRoleNavigation();const skip=$('#skip-link');skip?.setAttribute?.('href','#admin-title');$('#admin-title')?.focus?.();loadDashboard();loadOnboardingCard();loadWorkspaceAccess().catch(()=>{})}
async function logout(){try{await api('/auth/logout',{method:'POST'})}finally{location.reload()}}
function applyTheme(dark) {
  document.body.classList.toggle('dark', dark);
  const toggle=$('#theme-toggle');
  if(toggle){const action=dark?'Ativar tema claro':'Ativar tema escuro';toggle.setAttribute('aria-pressed',String(dark));toggle.setAttribute('aria-label','Tema escuro');toggle.title=action;toggle.textContent=dark?'☀':'☾'}
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark ? '#14201e' : '#edf3ef');
}
function setupAdmin() {
  ensureSaasSections();
  $$('#admin-nav .nav').forEach(b=>b.addEventListener('click',()=>showSection(b.dataset.section)));
  $('#logout').addEventListener('click',logout);
  $('#modal-close').addEventListener('click',closeModal);
  $('#modal').addEventListener('click',e=>{if(e.target.id==='modal')closeModal()});
  document.addEventListener('keydown',handleDialogKeys);
  $('#item-form').addEventListener('submit',submitItem);
  $('#theme-toggle').addEventListener('click',()=>{
    const dark = !document.body.classList.contains('dark');
    applyTheme(dark);
    // Theme persistence is optional; blocked storage must never stop access.
    try { localStorage.setItem('ideal-theme',dark?'dark':'light'); } catch (_) {}
  });
  let dark = false;
  try { dark = localStorage.getItem('ideal-theme') === 'dark'; } catch (_) {}
  applyTheme(dark);
}
function ensureSaasSections() {
  const nav=$('#admin-nav'), main=$('.admin-main'), topbar=$('.topbar');
  if(nav&&!$('#nav-workspace')) nav.insertAdjacentHTML('beforeend','<button id="nav-intelligence" class="nav admin-only" data-section="intelligence" aria-label="Central inteligente" type="button">✦ <span>Central inteligente</span></button><button id="nav-workspace" class="nav admin-only" data-section="workspace" aria-label="Plano e equipe" type="button">◇ <span>Plano e equipe</span></button><button id="nav-platform" class="nav platform-only hidden" data-section="platform" aria-label="Plataforma" type="button">✦ <span>Plataforma</span></button>');
  if(topbar&&!$('#workspace-access-banner')) topbar.insertAdjacentHTML('afterend','<div id="workspace-access-banner" class="workspace-access-banner hidden" role="status"><strong>Espaço em modo somente leitura.</strong><span>Regularize a assinatura em Plano e equipe para voltar a criar ou alterar registros.</span><button class="btn secondary" type="button" onclick="showSection(\'workspace\')">Ver assinatura</button></div>');
  if(main&&!$('#workspace')) main.insertAdjacentHTML('beforeend','<section id="intelligence" class="admin-section hidden"></section><section id="workspace" class="admin-section hidden"></section><section id="platform" class="admin-section hidden"></section>');
}
function syncRoleNavigation() {
  const nodes=selector=>document.querySelectorAll?[...document.querySelectorAll(selector)]:[];
  nodes('.admin-only').forEach(node=>node.classList.toggle('hidden',!state.user?.is_admin));
  nodes('.platform-only').forEach(node=>node.classList.toggle('hidden',!state.user?.is_platform_admin));
}
function renderWorkspaceAccess(){
  const blocked=state.workspaceAccess===false,banner=$('#workspace-access-banner');banner?.classList.toggle('hidden',!blocked);
  $$('[data-workspace-write]').forEach(button=>button.disabled=blocked);
}
async function loadWorkspaceAccess(){
  try{const subscription=await api('/billing/subscription');state.workspaceAccess=subscription.access_allowed!==false}
  catch(error){if(error.status===404)state.workspaceAccess=true;else throw error}
  renderWorkspaceAccess();return state.workspaceAccess;
}
function workspaceCanWrite(){if(state.workspaceAccess!==false)return true;toast('O espaço está somente para leitura até a assinatura ser regularizada.','error');showSection('workspace');return false}
function showSection(name){
  if(name==='platform'&&!state.user?.is_platform_admin){toast('Somente o superadministrador pode abrir esta área.','error');name='dashboard'}
  const section=$(`#${name}`);if(!section)return;
  clearTimeout(searchTimer);listRequestVersion++;state.listResource=null;$$('.admin-section').forEach(s=>s.classList.add('hidden'));section.classList.remove('hidden');$$('#admin-nav .nav').forEach(b=>{const current=b.dataset.section===name;b.classList.toggle('active',current);if(current)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')});$('#admin-title').textContent=labels[name]||'Dashboard';
  if(name==='dashboard'){loadDashboard();loadOnboardingCard()}
  else if(name==='intelligence')loadIntelligence();
  else if(name==='workspace')loadWorkspace();
  else if(name==='platform')loadPlatform();
  else loadResource(name,{reset:true});
}
const subscriptionStatusLabels={trial:'Teste gratuito',active:'Ativa',past_due:'Pagamento pendente',canceled:'Cancelada'};
const featureLabels={customers:'Clientes',quotes:'Orçamentos',projects:'Projetos',costs:'Controle de custos',intelligence:'Inteligência de orçamento',automation:'Automações',production:'Produção',profitability:'Rentabilidade',advanced_reports:'Relatórios avançados',priority_support:'Suporte prioritário',assisted_onboarding:'Implantação assistida'};
const automationEventLabels={
  'quote.created':'Orçamento analisado', 'quote.updated':'Orçamento revisado',
  'quote.approved':'Orçamento aprovado', 'quote.rejected':'Orçamento recusado',
  'quote.shared':'Orçamento compartilhado', 'quote.accepted':'Orçamento aceito pelo cliente',
  'quote.declined':'Orçamento recusado pelo cliente', 'project.created':'Projeto criado',
  'project.status_changed':'Etapa de produção atualizada', 'project.cost_added':'Custo de produção registrado',
};
function intelligenceHtml(overview={}) {
  const external=overview.external_ai_status==='configured';
  const recent=(overview.recent||[]).map(row=>{
    const result=row.result||{}, title=result.message||automationEventLabels[row.event]||row.event||'Automação executada';
    const time=readableDateTime(row.created_at), failed=row.status==='failed';
    const detail=result.summary||((result.warnings||[])[0])||(result.status?`Novo estado: ${result.status}`:'Execução registrada para auditoria.');
    return `<li class="automation-item ${failed?'failed':'completed'}"><span class="automation-led" aria-hidden="true"></span><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(detail)}</p><small>${escapeHtml(time)} · ${failed?'Requer atenção':'Concluída'}</small></div><span class="badge ${failed?'':'success'}">${failed?'Falhou':'OK'}</span></li>`;
  }).join('')||'<li class="automation-empty"><strong>Nenhuma execução nesta instância ainda.</strong><span>Crie um orçamento inteligente ou avance um projeto para acompanhar as automações aqui.</span></li>';
  return `<div class="intelligence-hero"><div><span class="eyebrow">Automação + inteligência artificial</span><h2>Central inteligente</h2><p>Analise orçamentos, acompanhe eventos operacionais e mantenha cada decisão sob aprovação humana.</p></div><div class="intelligence-orbit" aria-hidden="true"><span>IA</span></div></div><div class="intelligence-status-grid"><article class="intelligence-status"><span>Motor de automação</span><strong>Operacional</strong><small>Eventos separados por marcenaria</small></article><article class="intelligence-status"><span>Análise segura local</span><strong>Ativa</strong><small>Continua funcionando sem provedor externo</small></article><article class="intelligence-status ${external?'connected':'local'}"><span>IA externa</span><strong>${external?'Conectada':'Modo local'}</strong><small>${external?'Regras financeiras continuam bloqueadas':'Configure uma chave somente quando decidir usar o provedor'}</small></article><article class="intelligence-status"><span>Execuções</span><strong>${escapeHtml(overview.total_executions||0)}</strong><small>${escapeHtml(overview.completed||0)} concluídas · ${escapeHtml(overview.failed||0)} falhas</small></article></div><div class="intelligence-actions"><button class="btn primary" type="button" data-intelligence-action="smart-quote">✨ Novo orçamento inteligente</button><button class="btn secondary" type="button" data-intelligence-action="quotes">Revisar orçamentos</button><button class="btn secondary" type="button" data-intelligence-action="projects">Acompanhar produção</button><button class="btn secondary" type="button" data-intelligence-action="refresh">Atualizar central</button></div><div class="panel automation-panel"><div class="panel-title"><div><span class="eyebrow">Rastreabilidade</span><h3>Execuções recentes</h3></div><span class="badge">Instância atual</span></div><ul class="automation-list">${recent}</ul><p class="automation-disclaimer">A IA sugere e alerta, mas não altera valores financeiros nem aprova orçamentos automaticamente.</p></div>`;
}
function readableDateTime(value){if(!value)return 'Data não informada';const date=new Date(value);return Number.isNaN(date.getTime())?'Data não informada':date.toLocaleString('pt-BR')}
async function loadIntelligence(){
  const section=$('#intelligence');if(!section)return;section.innerHTML='<div class="panel loading">Carregando central inteligente...</div>';
  try{
    const overview=await api('/automations/overview');section.innerHTML=intelligenceHtml(overview);
    section.querySelector('[data-intelligence-action="smart-quote"]')?.addEventListener('click',()=>createItem('quotes'));
    section.querySelector('[data-intelligence-action="quotes"]')?.addEventListener('click',()=>showSection('quotes'));
    section.querySelector('[data-intelligence-action="projects"]')?.addEventListener('click',()=>showSection('projects'));
    section.querySelector('[data-intelligence-action="refresh"]')?.addEventListener('click',loadIntelligence);
  }catch(error){section.innerHTML=`<div class="panel empty"><h2>Não foi possível carregar a central inteligente</h2><p>${escapeHtml(error.message)}</p><button class="btn primary" type="button" onclick="loadIntelligence()">Tentar novamente</button></div>`}
}
function readableDate(value){if(!value)return 'Não informado';const date=new Date(value);return Number.isNaN(date.getTime())?'Não informado':date.toLocaleDateString('pt-BR')}
function workspaceHtml(plans=[],subscription=null,onboarding={}) {
  const activePlan=plans.find(plan=>plan.code===subscription?.plan_code);
  const maxUsers=activePlan?.max_users||3;
  const status=subscriptionStatusLabels[subscription?.status]||'Não configurada';
  const allowed=Boolean(subscription&&subscription.access_allowed!==false);
  const providerNotice=subscription?.provider==='sandbox'
    ? 'Ambiente sandbox — nenhuma cobrança real será feita.'
    : 'A cobrança comercial depende do provedor configurado no servidor.';
  const planCards=plans.map(plan=>{
    const current=plan.code===subscription?.plan_code;
    const features=Object.entries(plan.features||{}).filter(([,enabled])=>Boolean(enabled)).map(([key])=>`<li>${escapeHtml(featureLabels[key]||key.replace(/_/g,' '))}</li>`).join('')||'<li>Recursos essenciais da marcenaria</li>';
    const buttonLabel=current&&allowed?'Plano atual':'Preparar seleção';
    return `<article class="saas-plan${current?' current':''}${plan.code==='pro'?' recommended':''}">${plan.code==='pro'?'<span class="public-plan-badge">Mais escolhido</span>':''}<div><span class="eyebrow">${current?'Plano da marcenaria':'Plano disponível'}</span><h3>${escapeHtml(plan.name)}</h3><p class="plan-price"><strong>${money(plan.monthly_price_cents/100)}</strong><span>/mês</span></p></div><p class="muted">Até ${escapeHtml(plan.max_users)} usuários.</p><ul>${features}</ul><button class="btn ${current&&allowed?'secondary':'primary'}" type="button" data-plan-code="${escapeHtml(plan.code)}" ${current&&allowed?'disabled':''}>${buttonLabel}</button></article>`;
  }).join('')||'<div class="empty"><p>Nenhum plano ativo foi disponibilizado.</p></div>';
  return `<div class="saas-heading"><div><span class="eyebrow">Gestão do espaço</span><h2>Plano e equipe</h2><p>Administre o acesso da sua marcenaria sem misturar dados com outras empresas.</p></div><span class="access-chip ${allowed?'allowed':'blocked'}">${allowed?'Acesso liberado':'Acesso pendente'}</span></div><div class="panel subscription-panel"><div><span class="eyebrow">Assinatura atual</span><h3>${escapeHtml(subscription?.plan_name||'Plano ainda não associado')}</h3><p class="muted">${escapeHtml(status)} · ${escapeHtml(providerNotice)}</p></div><dl class="subscription-facts"><div><dt>Equipe</dt><dd>${escapeHtml(onboarding.user_count||0)} de ${escapeHtml(maxUsers)} usuários</dd></div><div><dt>Fim do teste</dt><dd>${escapeHtml(readableDate(subscription?.trial_end))}</dd></div><div><dt>Próximo período</dt><dd>${escapeHtml(readableDate(subscription?.current_period_end))}</dd></div></dl><p id="billing-action-message" class="form-message" role="status" aria-live="polite"></p></div><div class="saas-plan-grid">${planCards}</div><div class="panel team-panel"><div class="panel-title"><div><span class="eyebrow">Equipe isolada por marcenaria</span><h3>Adicionar membro</h3></div><span class="badge">${escapeHtml(onboarding.user_count||0)} de ${escapeHtml(maxUsers)} usuários</span></div><form id="team-member-form" class="team-form"><label>Nome<input name="name" type="text" minlength="2" maxlength="120" autocomplete="name" required></label><label>E-mail<input name="email" type="email" autocomplete="email" required></label><label>Senha provisória<input name="password" type="password" minlength="8" maxlength="128" autocomplete="new-password" required></label><label>Permissão<select name="is_admin"><option value="false">Usuário da marcenaria</option><option value="true">Administrador da marcenaria</option></select></label><button class="btn primary" type="submit" ${allowed?'':'disabled'}>Adicionar membro</button><p id="team-member-message" class="form-message" role="status" aria-live="polite"></p></form></div>`;
}
async function loadWorkspace(){
  const section=$('#workspace');if(!section)return;section.innerHTML='<div class="panel loading">Carregando plano e equipe...</div>';
  try{
    const [plans,onboarding]=await Promise.all([api('/plans'),api('/onboarding/status')]);
    let subscription=null;
    try{subscription=await api('/billing/subscription')}catch(error){if(error.status!==404)throw error}
    state.workspaceAccess=Boolean(subscription&&subscription.access_allowed!==false);renderWorkspaceAccess();section.innerHTML=workspaceHtml(plans,subscription,onboarding);
    $('#team-member-form')?.addEventListener('submit',addTeamMember);
    $$('[data-plan-code]',section).forEach(button=>button.addEventListener('click',()=>requestPlan(button.dataset.planCode,button)));
  }catch(error){section.innerHTML=`<div class="panel empty"><h2>Não foi possível carregar plano e equipe</h2><p>${escapeHtml(error.message)}</p><button class="btn primary" type="button" onclick="loadWorkspace()">Tentar novamente</button></div>`}
}
async function requestPlan(planCode,button){
  if(button?.disabled)return;const message=$('#billing-action-message'),label=button?.textContent||'';
  if(button){button.disabled=true;button.textContent='Preparando...'}
  try{
    const result=await api('/billing/checkout',{method:'POST',body:{plan_code:planCode}});
    const sandbox=result?.mode==='test';
    setFormMessage(message,sandbox?'Sessão sandbox criada. Nenhuma cobrança real foi feita.':'Provedor configurado. O redirecionamento comercial ainda precisa ser concluído.',sandbox?'success':'error');
  }catch(error){setFormMessage(message,error.message,'error')}
  finally{if(button){button.disabled=false;button.textContent=label}}
}
async function addTeamMember(event){
  event.preventDefault();const form=event.currentTarget,button=form.querySelector('button[type="submit"]'),message=$('#team-member-message');
  if(form.dataset.pending==='true')return;form.dataset.pending='true';form.setAttribute('aria-busy','true');const label=button.textContent;button.disabled=true;button.textContent='Adicionando...';
  try{
    const values=new FormData(form);
    await api('/onboarding/members',{method:'POST',body:{name:String(values.get('name')||'').trim(),email:String(values.get('email')||'').trim().toLowerCase(),password:String(values.get('password')||''),is_admin:values.get('is_admin')==='true'}});
    form.reset();setFormMessage(message,'Membro adicionado somente à equipe desta marcenaria.','success');setTimeout(loadWorkspace,700);
  }catch(error){setFormMessage(message,error.message,'error')}
  finally{delete form.dataset.pending;form.removeAttribute('aria-busy');button.disabled=false;button.textContent=label}
}
function platformHtml(overview={},organizations=[]) {
  const statuses=Object.entries(overview.subscription_statuses||{}).map(([status,count])=>`${escapeHtml(subscriptionStatusLabels[status]||status)}: ${escapeHtml(count)}`).join(' · ')||'Sem assinaturas';
  const rows=organizations.map(org=>`<tr><td><strong>${escapeHtml(org.name)}</strong><small>${escapeHtml(org.slug)}</small></td><td>${escapeHtml(org.user_count)}</td><td>${escapeHtml(org.plan_id||'—')}</td><td><span class="badge">${escapeHtml(subscriptionStatusLabels[org.subscription_status]||org.subscription_status||'Sem assinatura')}</span></td><td><select aria-label="Status de ${escapeHtml(org.name)}" data-organization-status="${escapeHtml(org.id)}"><option value="active" ${org.status==='active'?'selected':''}>Ativa</option><option value="suspended" ${org.status==='suspended'?'selected':''}>Suspensa</option><option value="closed" ${org.status==='closed'?'selected':''}>Encerrada</option></select></td><td><button class="small-btn" type="button" data-save-organization="${escapeHtml(org.id)}">Salvar</button></td></tr>`).join('')||'<tr><td colspan="6" class="empty-row">Nenhuma marcenaria cadastrada.</td></tr>';
  return `<div class="saas-heading"><div><span class="eyebrow">Superadministração</span><h2>Administração da plataforma</h2><p>Visão agregada com metadados de contas; nenhuma informação operacional é exibida aqui.</p></div><span class="access-chip allowed">Acesso de plataforma</span></div><div class="stats platform-stats"><div class="stat"><span>Marcenarias</span><strong>${escapeHtml(overview.organizations||0)}</strong><small>${escapeHtml(overview.organizations||0)} marcenarias</small></div><div class="stat"><span>Usuários</span><strong>${escapeHtml(overview.users||0)}</strong><small>Contas cadastradas</small></div><div class="stat"><span>Assinaturas</span><strong>${escapeHtml(overview.subscriptions||0)}</strong><small>${statuses}</small></div></div><div class="panel"><div class="panel-title"><div><span class="eyebrow">Contas SaaS</span><h3>Marcenarias cadastradas</h3></div><span class="badge">Somente metadados</span></div><div class="table-wrap"><table class="table"><thead><tr><th>Marcenaria</th><th>Usuários</th><th>Plano</th><th>Assinatura</th><th>Status</th><th>Ação</th></tr></thead><tbody>${rows}</tbody></table></div><p id="platform-action-message" class="form-message" role="status" aria-live="polite"></p></div>`;
}
async function loadPlatform(){
  const section=$('#platform');if(!section)return;if(!state.user?.is_platform_admin){showSection('dashboard');return}section.innerHTML='<div class="panel loading">Carregando administração da plataforma...</div>';
  try{
    const [overview,organizations]=await Promise.all([api('/platform/overview'),api('/platform/organizations')]);section.innerHTML=platformHtml(overview,organizations);
    $$('[data-save-organization]',section).forEach(button=>button.addEventListener('click',()=>updateOrganizationStatus(Number(button.dataset.saveOrganization),button)));
  }catch(error){section.innerHTML=`<div class="panel empty"><h2>Não foi possível carregar a plataforma</h2><p>${escapeHtml(error.message)}</p><button class="btn primary" type="button" onclick="loadPlatform()">Tentar novamente</button></div>`}
}
async function updateOrganizationStatus(organizationId,button){
  const select=$(`[data-organization-status="${organizationId}"]`),message=$('#platform-action-message');if(!select||button?.disabled)return;
  if(!window.confirm(`Confirma alterar o status desta marcenaria para ${select.options[select.selectedIndex].text}?`))return;
  const label=button.textContent;button.disabled=true;button.textContent='Salvando...';
  try{await api(`/platform/organizations/${organizationId}/status?status=${encodeURIComponent(select.value)}`,{method:'PATCH'});setFormMessage(message,'Status da marcenaria atualizado e auditado.','success')}
  catch(error){setFormMessage(message,error.message,'error')}
  finally{button.disabled=false;button.textContent=label}
}
async function loadOnboardingCard(){
  try {
    const data=await api('/onboarding/status');
    for(let attempt=0;attempt<30;attempt+=1){
      const section=$('#dashboard');
      if(section&&!section.querySelector('.loading')){
        if(section.querySelector('.onboarding-card')) return;
        const checklist=Array.isArray(data.checklist)?data.checklist:[];
        const done=checklist.filter(item=>item.complete).length;
      const next=data.next_step?String(data.next_step).replace(/_/g,' '):'concluído';
        const subscription=data.subscription||{};
        const plan=subscription.plan_id?`Plano #${escapeHtml(subscription.plan_id)}`:'Plano inicial';
        section.insertAdjacentHTML('beforeend',`<div class="panel onboarding-card"><div class="panel-title"><div><span class="eyebrow">Primeiros passos</span><h3>${escapeHtml(data.organization?.name||'Sua marcenaria')}</h3></div><span class="badge success">${done}/${checklist.length} concluídos</span></div><p class="muted">${escapeHtml(plan)} · status ${escapeHtml(subscription.status||'pendente')}.</p><div class="onboarding-progress" role="progressbar" aria-valuemin="0" aria-valuemax="${checklist.length}" aria-valuenow="${done}"><span style="width:${checklist.length?Math.round(done/checklist.length*100):0}%"></span></div><p class="muted onboarding-next">${data.next_step?`Próximo: ${escapeHtml(next)}.`:'Onboarding inicial concluído.'}</p></div>`);
        return;
      }
      await new Promise(resolve=>setTimeout(resolve,50));
    }
  } catch (_) {
    // The dashboard remains usable when an older database has not migrated yet.
  }
}
async function loadDashboard(){const section=$('#dashboard');section.innerHTML='<div class="panel loading">Carregando visão geral...</div>';try{const [data,me]=await Promise.all([api('/admin/dashboard'),api('/me')]);state.user=me;$('#user-badge').textContent=me.name;const c=data.counts||{};const cards=[['Clientes',c.customers||0,'customers'],['Orçamentos',c.quotes||0,'quotes'],['Projetos',c.projects||0,'projects'],['Produtos',c.products||0,'products'],['Usuários',c.users||0,'users']];const recent=(data.recent_activities||[]).map(a=>`<li><strong>${escapeHtml(a.action)}</strong> · ${escapeHtml(a.description)}<small>${new Date(a.created_at).toLocaleString('pt-BR')}</small></li>`).join('')||'<li>Nenhuma atividade registrada ainda.</li>';section.innerHTML=`<div class="welcome"><div><span class="eyebrow">Visão geral</span><h2>Olá, ${escapeHtml(me.name.split(' ')[0])}. 👋</h2><p>Acompanhe clientes, orçamentos e projetos em um só lugar.</p></div><div class="welcome-actions"><button class="btn light" onclick="createItem('quotes')">Novo orçamento</button><button class="btn secondary" onclick="showSection('intelligence')">Central inteligente</button></div></div><div class="stats">${cards.map(([n,v,s])=>`<button class="stat" onclick="showSection('${s}')"><span>${n}</span><strong>${v}</strong><small>Gerenciar ${n.toLowerCase()} →</small></button>`).join('')}</div><div class="panel"><div class="panel-title"><div><span class="eyebrow">Atividade</span><h3>Últimas ações</h3></div><button class="btn secondary" onclick="showSection('activities')">Ver histórico</button></div><ul class="activity-list">${recent}</ul></div>`}catch(err){section.innerHTML=`<div class="panel empty"><h2>Não foi possível carregar o painel</h2><p>${escapeHtml(err.message)}</p><button class="btn primary" onclick="loadDashboard()">Tentar novamente</button></div>`}}
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
    if (['customers', 'categories', 'suppliers', 'materials'].includes(resource)) mergeReferences(resource, rows);
    if (['quotes', 'projects'].includes(resource)) await ensureReferences('customers', rows.map(row => row.customer_id));
    if (resource === 'products') await ensureReferences('categories', rows.map(row => row.category_id));
    if (resource === 'materials') await ensureReferences('suppliers', rows.map(row => row.supplier_id));
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
function formatDateOnly(value) {
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (match) return `${match[3]}/${match[2]}/${match[1]}`;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? escapeHtml(value) : date.toLocaleDateString('pt-BR');
}
function formatDateTime(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? escapeHtml(value) : date.toLocaleString('pt-BR');
}
function formatCell(resource,key,value){if(value===null||value===undefined||value==='')return'<span class="muted">—</span>';if(key==='price'||key==='total')return money(value);if(key==='is_admin')return value?'<span class="badge success">Administrador</span>':'<span class="badge">Usuário</span>';if(key==='is_active')return value?'<span class="badge success">Ativo</span>':'<span class="badge">Inativo</span>';if(key==='status')return`<span class="badge">${escapeHtml(statusLabels[value]||value)}</span>`;if(key==='category_id')return escapeHtml(state.categories.find(x=>x.id===value)?.name||`#${value}`);if(key==='customer_id')return escapeHtml(state.customers.find(x=>x.id===value)?.name||`#${value}`);if(key==='project_date')return formatDateOnly(value);if(key==='created_at')return formatDateTime(value);return escapeHtml(value)}
function field(label,name,type='text',value='',required=false,extra=''){return`<label>${label}${type==='textarea'?`<textarea name="${name}" ${required?'required':''} ${extra}>${escapeHtml(value)}</textarea>`:`<input name="${name}" type="${type}" value="${escapeHtml(value)}" ${required?'required':''} ${extra}>`}</label>`}
function selectField(label, name, options, value = '') {
  if (name === 'customer_id') return recordLookupField(label, 'customers', name, value);
  if (name === 'category_id') return recordLookupField(label, 'categories', name, value);
  return `<label>${label}<select name="${name}" required><option value="">Selecione...</option>${options.map(option => `<option value="${option.id}" ${String(option.id) === String(value) ? 'selected' : ''}>${escapeHtml(option.name)}</option>`).join('')}</select></label>`;
}
function recordLookupField(label, collection, name, value = '', required = true) {
  const selected = state[collection].find(row => String(row.id) === String(value));
  return `<div class="record-lookup" data-collection="${collection}"><div>${escapeHtml(label)}</div><input type="search" data-lookup-search maxlength="200" autocomplete="off" placeholder="Pesquisar em todos os registros..." aria-label="Pesquisar ${escapeHtml(label.toLowerCase())}"><select name="${name}" aria-label="${escapeHtml(label)}" ${required ? 'required' : ''} data-lookup-selected="${escapeHtml(value)}"><option value="">Selecione...</option>${selected ? `<option value="${selected.id}" selected>${escapeHtml(selected.name)}</option>` : ''}</select><div class="lookup-pagination"><button type="button" class="small-btn" data-lookup-prev disabled>Anterior</button><small data-lookup-info aria-live="polite">Carregando opções...</small><button type="button" class="small-btn" data-lookup-next disabled>Próxima</button></div></div>`;
}
async function setupRecordLookups(root) {
  await Promise.all($$('.record-lookup', root).map(async element => {
    const collection = element.dataset.collection;
    if (!['customers', 'categories', 'suppliers', 'materials'].includes(collection)) return;
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
let formRequestVersion = 0;
const pendingItemSaves = new WeakSet();
function openManagedModal(title, html, focusSelector = 'input, select, textarea, button', invalidatePending = true) {
  if (invalidatePending) ++formRequestVersion;
  const overlay = $('#modal'), form = $('#item-form');
  if (overlay.classList.contains('hidden')) modalReturnFocus = document.activeElement;
  $('#modal-title').textContent = title;
  form.removeAttribute('aria-busy');
  form.innerHTML = html;
  overlay.classList.remove('hidden'); overlay.setAttribute('aria-hidden', 'false');
  ($(focusSelector, form) || $('#modal-close') || $('[role="dialog"]', overlay))?.focus?.();
  return { form, content: form.firstElementChild, version: formRequestVersion };
}
async function openForm(resource, id = null) {
  const version = ++formRequestVersion, form = $('#item-form');
  const previousContents = form.firstElementChild;
  const current = () => version === formRequestVersion && form.firstElementChild === previousContents;
  try {
    const row = id ? (state.listResource === resource ? state.rows.find(item => item.id === id) : null) || await api(`${configs[resource].endpoint}/${id}`) : {};
    if (!current()) return false;
    if (resource === 'quotes' && id && !['pending', 'analysis'].includes(row.status)) throw new Error('Este orçamento já tem uma decisão registrada. Consulte a proposta ou crie uma nova revisão.');
    if (row.customer_id) await ensureReferences('customers', [row.customer_id]);
    if (row.category_id) await ensureReferences('categories', [row.category_id]);
    if (!current()) return false;
    state.resource = resource; state.id = id;
    openManagedModal(`${id ? 'Editar' : 'Novo'} ${resource === 'quotes' ? 'orçamento' : resource === 'customers' ? 'cliente' : resource === 'projects' ? 'projeto' : resource === 'products' ? 'produto' : resource === 'categories' ? 'serviço' : 'usuário'}`, `<div class="form-grid">${resource === 'quotes' ? quoteTechnicalForm(row) : formHtml(resource, row)}</div><p id="item-message" class="form-message error" role="alert" aria-live="polite"></p><div class="modal-actions"><button type="button" class="btn secondary" onclick="closeModal()">Cancelar</button><button type="submit" class="btn primary">${id ? 'Salvar alterações' : 'Cadastrar'}</button></div>`, 'input, select, textarea', false);
    // Production stages now use the dedicated /projects/{id}/status workflow.
    if (resource === 'projects') form.querySelector('select[name="status"]')?.closest('label')?.remove();
    const renderedContents = form.firstElementChild;
    await setupRecordLookups(form);
    return version === formRequestVersion && form.firstElementChild === renderedContents;
  } catch (error) {
    if (version !== formRequestVersion) return false;
    throw error;
  }
}
function createItem(resource){if(!workspaceCanWrite())return Promise.resolve(false);return openForm(resource).catch(error=>toast(error.message,'error'))}function editItem(resource,id){if(!workspaceCanWrite())return Promise.resolve(false);return openForm(resource,id).catch(error=>toast(error.message,'error'))}
function closeModal() {
  ++formRequestVersion;
  $('#modal').classList.add('hidden'); $('#modal').setAttribute('aria-hidden','true');
  $('#item-form').innerHTML=''; $('#item-form').removeAttribute('aria-busy');
  if (modalReturnFocus?.isConnected) modalReturnFocus.focus();
  modalReturnFocus = null;
}
async function submitItem(e) {
  e.preventDefault();
  if(!workspaceCanWrite())return false;
  if ($('.smart-quote-create', e.target) || $('.history-modal', e.target) || $('.production-modal', e.target)) return;
  const form = e.target, grid = $('.form-grid', form);
  if (!grid || pendingItemSaves.has(grid) || (form.reportValidity && !form.reportValidity())) return;
  const fd = new FormData(form), resource = state.resource, id = state.id, payload = {};
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
  if (resource === 'suppliers') {
    payload.email = payload.email || null;
    payload.is_active = fd.has('is_active');
  }
  if (resource === 'materials') {
    payload.supplier_id = payload.supplier_id ? Number(payload.supplier_id) : null;
    payload.unit_cost = Number(payload.unit_cost);
    payload.waste_percent = Number(payload.waste_percent);
    payload.is_active = fd.has('is_active');
  }
  const button = $('button[type="submit"]', form), label = button?.textContent;
  const message = $('#item-message', form);
  const controls = $$('button, input, select, textarea',form).map(control=>[control,control.disabled]);
  const current = () => grid.isConnected && $('.form-grid',form) === grid;
  pendingItemSaves.add(grid);
  if (message) message.textContent = '';
  controls.forEach(([control])=>{control.disabled=true;});
  if (button) button.textContent = 'Salvando...';
  form.setAttribute('aria-busy','true');
  const controller = new AbortController(), timeout = setTimeout(()=>controller.abort(),20000);
  let persisted = false;
  try {
    const endpoint = resource === 'users' ? `/admin/users/${id}` : id ? `${configs[resource].endpoint}/${id}` : configs[resource].endpoint;
    const method = resource === 'users' ? 'PATCH' : id ? 'PUT' : 'POST';
    const saved = await api(endpoint, { method, body: payload, signal:controller.signal });
    clearTimeout(timeout);
    persisted = true;
    if (['customers', 'categories', 'suppliers', 'materials'].includes(resource)) mergeReferences(resource, [saved]);
    if (!current()) return;
    closeModal(); toast(id ? 'Alterações salvas com sucesso.' : 'Cadastro realizado com sucesso.');
    if (state.listResource === resource) await loadResource(resource);
  } catch (error) {
    if (!current()) return;
    const text = persisted ? 'Salvo, mas a tela não foi atualizada. Confira a lista; não repita o cadastro.'
      : error.name === 'AbortError' || error.name === 'TypeError' || error.status >= 500 ? 'Não foi possível confirmar a gravação. Seus campos foram mantidos. Confira a lista antes de reenviar.'
      : error.message;
    if (message) message.textContent = text;
    else toast(text,'error');
  } finally {
    clearTimeout(timeout); pendingItemSaves.delete(grid);
    if (current()) {
      controls.forEach(([control,disabled])=>{control.disabled=disabled;});
      if (button) button.textContent = label;
      form.removeAttribute('aria-busy');
    }
  }
}
const pendingDeletes=new Set();
async function deleteItem(resource,id){
  if(!workspaceCanWrite())return false;
  const key=`${resource}:${id}`;
  if(pendingDeletes.has(key))return false;
  if(!confirm('Excluir este registro? Esta ação não pode ser desfeita.'))return false;
  const button=$(`#${resource} tr[data-row-id="${id}"] .danger`);
  const originalLabel=button?.textContent||'';
  const originalDisabled=button?.disabled||false;
  pendingDeletes.add(key);
  if(button){button.disabled=true;button.textContent='Excluindo...';button.setAttribute('aria-busy','true')}
  try{
    await api(`${configs[resource].endpoint}/${id}`,{method:'DELETE'});
    toast('Registro excluído.');
    await loadResource(resource);
    return true;
  }catch(err){
    toast(err.message,'error');
    return false;
  }finally{
    pendingDeletes.delete(key);
    if(button){button.disabled=originalDisabled;button.textContent=originalLabel;button.removeAttribute('aria-busy')}
  }
}
async function viewCustomerHistory(id) {
  const customer = state.rows.find(row => row.id === id), form = $('#item-form');
  openManagedModal(`Histórico — ${customer?.name || `Cliente #${id}`}`, '<div class="history-modal"><label>Pesquisar histórico<input type="search" id="history-search" maxlength="200" placeholder="Pesquisar em todo o histórico..."></label><div id="history-rows" aria-live="polite"></div><nav class="pagination" aria-label="Páginas do histórico"><button type="button" class="btn secondary" id="history-prev" disabled>Anterior</button><span id="history-count"></span><button type="button" class="btn secondary" id="history-next" disabled>Próxima</button><button type="button" class="btn secondary hidden" id="history-retry">Tentar novamente</button></nav></div><div class="modal-actions"><button type="button" class="btn secondary" onclick="closeModal()">Fechar</button></div>', '#history-search');
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
  await load();
}
async function boot() {
  setupPublic(); setupAdmin();
  const initialLoginAttempt = loginAttemptVersion;
  try {
    await api('/auth/csrf');
    if (initialLoginAttempt !== loginAttemptVersion) return;
    const me = await api('/me');
    // A startup check must not replace a newer login or dismiss another auth form.
    if (initialLoginAttempt !== loginAttemptVersion || loginInProgress || (authView && authView !== 'login')) return;
    if (me?.is_admin) { state.user=me; enterAdmin(); }
  } catch (_) {}
}
boot();
