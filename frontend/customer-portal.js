(() => {
  'use strict';
  const CUSTOMER_API = `${window.API_BASE_URL || (['localhost','127.0.0.1','[::1]'].includes(location.hostname) ? `http://${location.hostname}:8000/api/v1` : 'https://ideal-marcenaria-api.onrender.com/api/v1')}/customer-portal`;
  const portalState = { me: null, quotes: [], projects: [], messages: [], view: 'home', csrfToken: '', accessToken: '' };
  const statusLabels = {sent:'Aguardando sua decisão',accepted:'Proposta aceita',declined:'Proposta recusada',completed:'Concluído',planning:'Planejamento',in_progress:'Em andamento',measurement:'Medição',technical_design:'Projeto técnico',purchasing:'Compras',production:'Produção',installation:'Instalação',delivered:'Entregue',cancelled:'Cancelado'};
  const projectProgress = {planning:10,measurement:20,technical_design:35,purchasing:50,in_progress:55,production:70,installation:88,delivered:96,completed:100,cancelled:0};
  const safe = (value='') => String(value ?? '').replace(/[&<>'"]/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[character]));
  const money = value => Number(value || 0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
  const date = value => value ? new Date(value).toLocaleDateString('pt-BR') : '—';
  const dateTime = value => value ? new Date(value).toLocaleString('pt-BR') : '—';
  const cookie = name => document.cookie.split('; ').find(item => item.startsWith(`${name}=`))?.split('=').slice(1).join('=') || '';

  async function customerApi(path, options={}) {
    const opts = {credentials:'include', ...options, headers:{...(options.headers||{})}};
    if (portalState.accessToken && !opts.headers.Authorization) opts.headers.Authorization = `Bearer ${portalState.accessToken}`;
    if (opts.body && typeof opts.body !== 'string') {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }
    if (['POST','PUT','PATCH','DELETE'].includes(opts.method)) {
      const token = portalState.csrfToken || decodeURIComponent(cookie('customer_csrf_token'));
      if (token) opts.headers['X-CSRF-Token'] = token;
    }
    const response = await fetch(CUSTOMER_API + path, opts);
    const data = response.status === 204 ? null : await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data?.detail || `Erro ${response.status}`);
    if (data?.csrf_token) portalState.csrfToken = data.csrf_token;
    if (data?.access_token) portalState.accessToken = data.access_token;
    return data;
  }

  function mount() {
    if (document.querySelector('#customer-auth-overlay')) return;
    document.body.insertAdjacentHTML('beforeend', `
      <div id="customer-auth-overlay" class="customer-auth-overlay hidden" aria-hidden="true">
        <div class="customer-auth-card" role="dialog" aria-modal="true" aria-labelledby="customer-auth-title">
          <button id="customer-auth-close" class="close" type="button" aria-label="Fechar">×</button>
          <div class="customer-auth-brand"><span class="mark" aria-hidden="true">MM</span><span><strong>Portal do Cliente</strong><small>Acompanhe sua marcenaria</small></span></div>
          <section id="customer-login-view" class="customer-auth-view">
            <span class="eyebrow">Acesso do cliente</span><h2 id="customer-auth-title">Bem-vindo</h2><p>Consulte propostas, projetos e mensagens da sua marcenaria.</p>
            <form id="customer-login-form"><label>Código da marcenaria<input id="customer-business-slug" autocomplete="organization" required></label><label>E-mail<input id="customer-email" type="email" autocomplete="username" required></label><label>Senha<div class="customer-password-field"><input id="customer-password" type="password" minlength="8" autocomplete="current-password" required><button type="button" data-customer-password="customer-password">Mostrar</button></div></label><button class="btn primary wide" type="submit">Entrar no portal</button><div id="customer-login-message" class="customer-message" role="alert"></div></form>
            <div class="customer-auth-actions"><button class="customer-link" data-customer-view="recovery" type="button">Esqueci minha senha</button><button class="customer-link" data-management-login type="button">Sou da marcenaria</button></div>
          </section>
          <section id="customer-activate-view" class="customer-auth-view hidden"><span class="eyebrow">Primeiro acesso</span><h2>Crie sua senha</h2><p>O convite vincula você com segurança à marcenaria que o enviou.</p><form id="customer-activate-form"><label>Nova senha<div class="customer-password-field"><input id="customer-activate-password" type="password" minlength="8" autocomplete="new-password" required><button type="button" data-customer-password="customer-activate-password">Mostrar</button></div></label><button class="btn primary wide" type="submit">Ativar meu portal</button><div id="customer-activate-message" class="customer-message" role="alert"></div></form></section>
          <section id="customer-recovery-view" class="customer-auth-view hidden"><span class="eyebrow">Recuperação</span><h2>Recupere seu acesso</h2><form id="customer-recovery-form"><label>Código da marcenaria<input id="customer-recovery-slug" required></label><label>E-mail<input id="customer-recovery-email" type="email" required></label><button class="btn primary wide" type="submit">Enviar instruções</button><div id="customer-recovery-message" class="customer-message" role="status"></div></form><button class="customer-link" data-customer-view="login" type="button">← Voltar</button></section>
          <section id="customer-reset-view" class="customer-auth-view hidden"><span class="eyebrow">Nova senha</span><h2>Redefina sua senha</h2><form id="customer-reset-form"><label>Nova senha<div class="customer-password-field"><input id="customer-reset-password" type="password" minlength="8" autocomplete="new-password" required><button type="button" data-customer-password="customer-reset-password">Mostrar</button></div></label><button class="btn primary wide" type="submit">Salvar nova senha</button><div id="customer-reset-message" class="customer-message" role="alert"></div></form></section>
        </div>
      </div>
      <div id="customer-portal-app" class="customer-portal-app hidden">
        <header class="customer-portal-header"><div class="customer-portal-brand"><span class="customer-portal-logo" aria-hidden="true">MM</span><span><strong id="customer-tenant-name">Portal do Cliente</strong><small id="customer-welcome">Acompanhamento do seu projeto</small></span></div><button id="customer-logout" class="btn secondary" type="button">Sair</button></header>
        <div class="customer-portal-shell"><nav class="customer-portal-nav" aria-label="Navegação do portal"><button class="active" data-portal-view="home" type="button">⌂ Visão geral</button><button data-portal-view="quotes" type="button">▤ Orçamentos</button><button data-portal-view="projects" type="button">▦ Projetos</button><button data-portal-view="messages" type="button">✉ Mensagens</button><button data-portal-view="profile" type="button">♙ Meus dados</button></nav><main class="customer-portal-main"><div id="customer-portal-content"></div></main></div>
      </div>
      <div id="customer-admin-modal" class="customer-admin-modal hidden" aria-hidden="true"><div class="customer-admin-card" role="dialog" aria-modal="true" aria-labelledby="customer-admin-title"><button class="close" id="customer-admin-close" type="button" aria-label="Fechar">×</button><h2 id="customer-admin-title">Portal do cliente</h2><div id="customer-admin-content"></div></div></div>`);
  }

  function injectEntryButtons() {
    const authLinks = document.querySelector('#login-view .auth-links');
    if (authLinks && !authLinks.querySelector('[data-customer-login]')) authLinks.insertAdjacentHTML('beforeend','<button type="button" data-customer-login>Sou cliente de uma marcenaria</button>');
    const loginButton = document.querySelector('#open-login');
    if (loginButton && !document.querySelector('.customer-entry')) {
      const button = document.createElement('button'); button.type='button'; button.className='customer-entry'; button.textContent='Área do cliente'; button.dataset.customerLogin=''; loginButton.before(button);
    }
  }

  function setAuthView(view) {
    document.querySelectorAll('.customer-auth-view').forEach(section => section.classList.toggle('hidden', section.id !== `customer-${view}-view`));
  }
  function openCustomerAuth(view='login') { const overlay=document.querySelector('#customer-auth-overlay'); overlay.classList.remove('hidden'); overlay.setAttribute('aria-hidden','false'); setAuthView(view); }
  function closeCustomerAuth() { const overlay=document.querySelector('#customer-auth-overlay'); overlay.classList.add('hidden'); overlay.setAttribute('aria-hidden','true'); }
  function setMessage(id, message, type='') { const element=document.querySelector(id); if(!element)return; element.textContent=message; element.className=`customer-message ${type}`; }
  function togglePassword(button) { const input=document.querySelector(`#${button.dataset.customerPassword}`); const visible=input.type==='password'; input.type=visible?'text':'password'; button.textContent=visible?'Ocultar':'Mostrar'; }

  async function login(event) {
    event.preventDefault(); setMessage('#customer-login-message','Entrando...');
    try {
      const data=await customerApi('/login',{method:'POST',body:{business_slug:document.querySelector('#customer-business-slug').value.trim().toLowerCase(),email:document.querySelector('#customer-email').value.trim().toLowerCase(),password:document.querySelector('#customer-password').value}});
      portalState.me=data; localStorage.setItem('customer_business_slug',data.tenant.slug); closeCustomerAuth(); await enterPortal();
    } catch(error) { setMessage('#customer-login-message',error.message,'error'); }
  }
  async function activate(event) {
    event.preventDefault(); setMessage('#customer-activate-message','Ativando...');
    try { const token=sessionStorage.getItem('customer_portal_token'); if(!token)throw new Error('Convite não encontrado. Peça um novo acesso à marcenaria.'); const data=await customerApi('/activate',{method:'POST',body:{token,password:document.querySelector('#customer-activate-password').value}}); portalState.me=data; sessionStorage.removeItem('customer_portal_token'); localStorage.setItem('customer_business_slug',data.tenant.slug); closeCustomerAuth(); await enterPortal(); } catch(error){setMessage('#customer-activate-message',error.message,'error');}
  }
  async function recover(event) {
    event.preventDefault(); setMessage('#customer-recovery-message','Enviando...');
    try { const data=await customerApi('/password-reset/request',{method:'POST',body:{business_slug:document.querySelector('#customer-recovery-slug').value.trim().toLowerCase(),email:document.querySelector('#customer-recovery-email').value.trim().toLowerCase()}}); setMessage('#customer-recovery-message',data.message,'success'); if(data.debug_token){sessionStorage.setItem('customer_portal_reset',data.debug_token);setAuthView('reset');} } catch(error){setMessage('#customer-recovery-message',error.message,'error');}
  }
  async function resetPassword(event) {
    event.preventDefault(); setMessage('#customer-reset-message','Salvando...');
    try { const token=sessionStorage.getItem('customer_portal_reset'); if(!token)throw new Error('Link de recuperação não encontrado.'); await customerApi('/password-reset/confirm',{method:'POST',body:{token,password:document.querySelector('#customer-reset-password').value}}); sessionStorage.removeItem('customer_portal_reset'); setMessage('#customer-reset-message','Senha alterada. Faça login.','success'); setTimeout(()=>setAuthView('login'),700); } catch(error){setMessage('#customer-reset-message',error.message,'error');}
  }

  async function loadPortalData() {
    const [me,quotes,projects,messages]=await Promise.all([customerApi('/me'),customerApi('/quotes'),customerApi('/projects'),customerApi('/messages')]);
    portalState.me=me; portalState.quotes=quotes; portalState.projects=projects; portalState.messages=messages;
  }
  async function enterPortal() {
    document.querySelector('#public-site')?.classList.add('hidden'); document.querySelector('#admin-app')?.classList.add('hidden'); document.querySelector('#customer-portal-app').classList.remove('hidden');
    await loadPortalData(); document.querySelector('#customer-tenant-name').textContent=portalState.me.tenant.name; document.querySelector('#customer-welcome').textContent=`Olá, ${portalState.me.customer.name}`; renderPortal('home'); history.replaceState({},'',`${location.pathname}#cliente`);
  }
  function renderPortal(view) {
    portalState.view=view; document.querySelectorAll('[data-portal-view]').forEach(button=>button.classList.toggle('active',button.dataset.portalView===view));
    const content=document.querySelector('#customer-portal-content');
    if(view==='home') content.innerHTML=homeHtml();
    if(view==='quotes') content.innerHTML=quotesHtml();
    if(view==='projects') content.innerHTML=projectsHtml();
    if(view==='messages') content.innerHTML=messagesHtml();
    if(view==='profile') content.innerHTML=profileHtml();
  }
  function heading(title,subtitle){return `<h1>${safe(title)}</h1><p class="customer-portal-subtitle">${safe(subtitle)}</p>`;}
  function homeHtml(){const pending=portalState.quotes.filter(item=>item.status==='sent').length,active=portalState.projects.filter(item=>!['completed','cancelled'].includes(item.status)).length;return `${heading(`Olá, ${portalState.me.customer.name.split(' ')[0]}`,'Acompanhe aqui tudo o que a sua marcenaria compartilhou com você.')}<div class="customer-summary"><article><span>Orçamentos</span><strong>${portalState.quotes.length}</strong></article><article><span>Aguardando decisão</span><strong>${pending}</strong></article><article><span>Projetos ativos</span><strong>${active}</strong></article></div><div class="customer-portal-card"><h3>Próximos passos</h3><p>${pending?'Você possui uma proposta aguardando sua decisão. Abra Orçamentos para analisar.':'Nenhuma proposta está aguardando sua decisão agora.'}</p></div>`;}
  function quotesHtml(){return `${heading('Meus orçamentos','Visualize propostas, imprima documentos e responda diretamente à marcenaria.')}<div class="customer-portal-grid">${portalState.quotes.length?portalState.quotes.map(quote=>`<article class="customer-portal-card"><div class="customer-card-head"><div><small>Orçamento #${quote.id}</small><h3>${safe(quote.description)}</h3></div><span class="customer-badge">${safe(statusLabels[quote.status]||quote.status)}</span></div><div class="customer-card-meta"><div><span>Valor da proposta</span><strong>${money(quote.total)}</strong></div><div><span>Data</span><strong>${date(quote.created_at)}</strong></div></div><div class="customer-card-actions"><button class="btn secondary" type="button" data-print-quote="${quote.id}">Visualizar / Salvar PDF</button>${quote.status==='sent'?`<button class="btn primary" type="button" data-quote-answer="accepted" data-quote-id="${quote.id}">Aceitar proposta</button><button class="btn secondary" type="button" data-quote-answer="declined" data-quote-id="${quote.id}">Recusar</button>`:''}</div></article>`).join(''):'<div class="customer-portal-card customer-empty">Nenhum orçamento compartilhado.</div>'}</div>`;}
  function projectsHtml(){return `${heading('Meus projetos','Acompanhe a etapa atual da fabricação até a entrega.')}<div class="customer-portal-grid">${portalState.projects.length?portalState.projects.map(project=>`<article class="customer-portal-card"><div class="customer-card-head"><h3>${safe(project.name)}</h3><span class="customer-badge">${safe(statusLabels[project.status]||project.status)}</span></div><p>${safe(project.description||'Projeto sob medida')}</p><div class="customer-progress" aria-label="Progresso aproximado"><span style="width:${projectProgress[project.status]??10}%"></span></div><div class="customer-card-meta"><div><span>Etapa atual</span><strong>${safe(statusLabels[project.status]||project.status)}</strong></div><div><span>Data prevista</span><strong>${date(project.project_date)}</strong></div></div></article>`).join(''):'<div class="customer-portal-card customer-empty">Nenhum projeto disponível ainda.</div>'}</div>`;}
  function messagesHtml(){return `${heading('Mensagens','Fale com a marcenaria sobre sua proposta ou projeto.')}<div class="customer-portal-card"><div class="customer-messages">${portalState.messages.length?portalState.messages.map(message=>`<div class="customer-chat ${message.author_type==='customer'?'customer':'staff'}"><strong>${message.author_type==='customer'?'Você':safe(portalState.me.tenant.name)}</strong><div>${safe(message.body)}</div><small>${dateTime(message.created_at)}</small></div>`).join(''):'<div class="customer-empty">Inicie a conversa com a marcenaria.</div>'}</div><form id="customer-message-form" class="customer-message-form"><textarea id="customer-message-body" maxlength="4000" placeholder="Escreva sua mensagem..." required></textarea><button class="btn primary" type="submit">Enviar mensagem</button><div id="customer-send-message" class="customer-message" role="status"></div></form></div>`;}
  function profileHtml(){const customer=portalState.me.customer;return `${heading('Meus dados','Confira os dados que a marcenaria possui para contato.')}<div class="customer-portal-card"><div class="customer-card-meta"><div><span>Nome</span><strong>${safe(customer.name)}</strong></div><div><span>E-mail</span><strong>${safe(customer.email||'—')}</strong></div><div><span>Telefone</span><strong>${safe(customer.phone||'—')}</strong></div><div><span>Endereço</span><strong>${safe(customer.address||'—')}</strong></div></div><p class="customer-portal-subtitle">Para corrigir algum dado, envie uma mensagem à marcenaria.</p></div>`;}

  async function answerQuote(id,status) { if(!confirm(`${status==='accepted'?'Aceitar':'Recusar'} a proposta #${id}?`))return; try{await customerApi(`/quotes/${id}/decision`,{method:'PATCH',body:{status}});await loadPortalData();renderPortal('quotes');}catch(error){alert(error.message);} }
  function printQuote(id) { const quote=portalState.quotes.find(item=>item.id===id); if(!quote)return; const popup=window.open('','_blank'); if(!popup){alert('Permita pop-ups para abrir a proposta.');return;} popup.opener=null; popup.document.write(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Orçamento #${quote.id}</title><style>body{font-family:Arial;margin:0;background:#f4f6f4;color:#18251f}.page{max-width:820px;margin:30px auto;background:white;padding:44px}.brand{font-size:26px;font-weight:800;color:#12372a}.head{display:flex;justify-content:space-between;border-bottom:2px solid #087a4f;padding-bottom:22px}.card{border:1px solid #d9e5de;border-radius:12px;padding:18px;margin:22px 0}.total{display:flex;justify-content:space-between;background:#12372a;color:white;padding:22px;border-radius:12px;font-size:22px}.actions{text-align:right;margin-top:22px}button{padding:12px 18px}@media print{body{background:white}.page{margin:0;max-width:none}.actions{display:none}}</style></head><body><main class="page"><div class="head"><div><div class="brand">${safe(portalState.me.tenant.name)}</div><p>Proposta comercial</p></div><div><strong>Orçamento #${quote.id}</strong><br>${date(quote.created_at)}</div></div><section class="card"><h2>${safe(quote.description)}</h2><p><strong>Medidas:</strong> ${safe(quote.measurements||'A confirmar')}</p><p><strong>Materiais:</strong> ${safe(quote.materials||'Conforme projeto')}</p><p><strong>Status:</strong> ${safe(statusLabels[quote.status]||quote.status)}</p></section><div class="total"><span>Valor total</span><strong>${money(quote.total)}</strong></div><div class="actions"><button onclick="window.print()">Imprimir / Salvar em PDF</button></div></main></body></html>`); popup.document.close(); }
  async function sendMessage(event){event.preventDefault();const body=document.querySelector('#customer-message-body').value.trim();if(!body)return;setMessage('#customer-send-message','Enviando...');try{await customerApi('/messages',{method:'POST',body:{body}});portalState.messages=await customerApi('/messages');renderPortal('messages');}catch(error){setMessage('#customer-send-message',error.message,'error');}}
  async function logout(){try{await customerApi('/logout',{method:'POST'});}finally{portalState.csrfToken='';portalState.accessToken='';location.href=location.pathname;}}

  function visibleCustomers(){const adminState=typeof state==='undefined'?{rows:[],search:''}:state;return (adminState.rows||[]).filter(row=>!adminState.search||Object.values(row).some(value=>String(value??'').toLowerCase().includes(adminState.search.toLowerCase())));}
  function enhanceCustomerRows(){const section=document.querySelector('#customers');if(!section||section.classList.contains('hidden'))return;const customers=visibleCustomers();section.querySelectorAll('tbody tr').forEach((row,index)=>{const customer=customers[index],actions=row.querySelector('.actions');if(!customer||!actions||actions.querySelector('[data-admin-customer-portal]'))return;const button=document.createElement('button');button.type='button';button.className='small-btn';button.dataset.adminCustomerPortal=String(customer.id);button.textContent='Portal';button.addEventListener('click',()=>openAdminPortal(customer));actions.prepend(button);});}
  async function openAdminPortal(customer){const modal=document.querySelector('#customer-admin-modal'),content=document.querySelector('#customer-admin-content');modal.classList.remove('hidden');modal.setAttribute('aria-hidden','false');content.innerHTML='<p>Carregando acesso e mensagens...</p>';try{const [status,messages]=await Promise.all([window.api(`/customer-portal/admin/customers/${customer.id}`),window.api(`/customer-portal/admin/customers/${customer.id}/messages`)]);renderAdminPortal(customer,status,messages);}catch(error){content.innerHTML=`<p class="customer-message error">${safe(error.message)}</p>`;}}
  function renderAdminPortal(customer,status,messages,invite=null){const content=document.querySelector('#customer-admin-content');content.innerHTML=`<p><strong>${safe(customer.name)}</strong><br>${safe(customer.email||'E-mail não cadastrado')}</p><div class="customer-admin-status"><strong>${status.activated?'Portal ativo':status.enabled?'Convite gerado, aguardando ativação':'Portal ainda não liberado'}</strong>${status.last_login_at?`<br><small>Último acesso: ${dateTime(status.last_login_at)}</small>`:''}</div><button id="customer-admin-invite" class="btn primary" type="button">${status.enabled?'Gerar novo convite':'Liberar acesso do cliente'}</button>${invite?`<div class="customer-admin-link"><input id="customer-invite-link" value="${safe(invite.invitation_url)}" readonly><button id="customer-copy-invite" class="btn secondary" type="button">Copiar</button></div><p class="customer-message success">Convite válido por 72 horas${invite.email_sent?' e enviado por e-mail.':'. Copie e envie ao cliente.'}</p>`:''}<h3>Mensagens</h3><div class="customer-admin-chat">${messages.length?messages.map(message=>`<p class="${message.author_type==='customer'?'customer':'staff'}"><strong>${message.author_type==='customer'?safe(customer.name):'Marcenaria'}:</strong> ${safe(message.body)}<br><small>${dateTime(message.created_at)}</small></p>`).join(''):'<p>Nenhuma mensagem ainda.</p>'}</div><form id="customer-admin-reply"><textarea id="customer-admin-reply-body" maxlength="4000" placeholder="Responder ao cliente..." required></textarea><button class="btn primary" type="submit">Enviar resposta</button></form>`;
    document.querySelector('#customer-admin-invite').addEventListener('click',async()=>{if(!confirm(`Gerar um convite de acesso para ${customer.name}?`))return;try{const result=await window.api(`/customer-portal/admin/customers/${customer.id}/invite`,{method:'POST'});renderAdminPortal(customer,{...status,enabled:true},messages,result);}catch(error){alert(error.message);}});
    document.querySelector('#customer-copy-invite')?.addEventListener('click',async()=>{const input=document.querySelector('#customer-invite-link');try{await navigator.clipboard.writeText(input.value);}catch(_){input.select();document.execCommand('copy');}document.querySelector('#customer-copy-invite').textContent='Copiado';});
    document.querySelector('#customer-admin-reply').addEventListener('submit',async event=>{event.preventDefault();const body=document.querySelector('#customer-admin-reply-body').value.trim();if(!body)return;try{await window.api(`/customer-portal/admin/customers/${customer.id}/messages`,{method:'POST',body:{body}});const next=await window.api(`/customer-portal/admin/customers/${customer.id}/messages`);renderAdminPortal(customer,status,next,invite);}catch(error){alert(error.message);}});
  }

  function bind() {
    document.addEventListener('click',event=>{
      const customerLogin=event.target.closest('[data-customer-login]');if(customerLogin){document.querySelector('#auth-overlay')?.classList.add('hidden');openCustomerAuth('login');}
      const management=event.target.closest('[data-management-login]');if(management){closeCustomerAuth();window.openAuth?.('login');}
      const view=event.target.closest('[data-customer-view]');if(view)setAuthView(view.dataset.customerView);
      const password=event.target.closest('[data-customer-password]');if(password)togglePassword(password);
      const portalView=event.target.closest('[data-portal-view]');if(portalView)renderPortal(portalView.dataset.portalView);
      const answer=event.target.closest('[data-quote-answer]');if(answer)answerQuote(Number(answer.dataset.quoteId),answer.dataset.quoteAnswer);
      const print=event.target.closest('[data-print-quote]');if(print)printQuote(Number(print.dataset.printQuote));
    });
    document.querySelector('#customer-auth-close').addEventListener('click',closeCustomerAuth);
    document.querySelector('#customer-auth-overlay').addEventListener('click',event=>{if(event.target.id==='customer-auth-overlay')closeCustomerAuth();});
    document.querySelector('#customer-login-form').addEventListener('submit',login);document.querySelector('#customer-activate-form').addEventListener('submit',activate);document.querySelector('#customer-recovery-form').addEventListener('submit',recover);document.querySelector('#customer-reset-form').addEventListener('submit',resetPassword);
    document.querySelector('#customer-logout').addEventListener('click',logout);document.querySelector('#customer-portal-content').addEventListener('submit',event=>{if(event.target.id==='customer-message-form')sendMessage(event);});
    document.querySelector('#customer-admin-close').addEventListener('click',()=>document.querySelector('#customer-admin-modal').classList.add('hidden'));
  }

  async function bootPortal() {
    mount(); injectEntryButtons(); bind();
    const originalRender=window.renderResource; if(typeof originalRender==='function'){window.renderResource=function(resource){const result=originalRender(resource);if(resource==='customers')enhanceCustomerRows();return result;};}
    const params=new URLSearchParams(location.search);const invite=params.get('customer_portal_token'),reset=params.get('customer_portal_reset'),slug=params.get('marcenaria')||localStorage.getItem('customer_business_slug')||'';
    document.querySelector('#customer-business-slug').value=slug;document.querySelector('#customer-recovery-slug').value=slug;
    if(invite){sessionStorage.setItem('customer_portal_token',invite);history.replaceState({},'',`${location.pathname}#cliente`);openCustomerAuth('activate');return;}
    if(reset){sessionStorage.setItem('customer_portal_reset',reset);history.replaceState({},'',`${location.pathname}#cliente`);openCustomerAuth('reset');return;}
    if(location.hash==='#cliente'){try{await enterPortal();}catch(_){document.querySelector('#customer-portal-app').classList.add('hidden');document.querySelector('#public-site')?.classList.remove('hidden');openCustomerAuth('login');}}
  }
  window.openCustomerPortal=openCustomerAuth;
  bootPortal();
})();
