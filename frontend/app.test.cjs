const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8').split('function openAuth')[0];
const response = (status, body = {}) => ({ status, ok: status < 400, json: async () => body });
function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

function createClient(handler) {
  const calls = [];
  let deadline = null, deadlineDelay = null;
  const context = {
    URLSearchParams, AbortController,
    setTimeout:(callback,delay)=>{deadline=callback;deadlineDelay=delay;return 1;},
    clearTimeout:()=>{},
    document: { cookie: '', querySelector: () => null, querySelectorAll: () => [] },
    location: { hostname: 'site.example' },
    window: { API_BASE_URL: 'https://api.example/api/v1' },
    fetch: async (url, options) => {
      calls.push({ url, options: { ...options, headers: { ...options.headers } } });
      return handler(url, options, calls.length);
    },
  };
  vm.createContext(context);
  vm.runInContext(`${source}\nglobalThis.testApi = api; globalThis.testState = state;`, context);
  context.testState.csrfToken = 'csrf-old';
  return { api: context.testApi, state: context.testState, calls, expire:()=>deadline?.(), get deadlineDelay(){return deadlineDelay;} };
}

function createLoginClient(handler) {
  const button={textContent:'Entrar',disabled:false};
  const form={querySelector:()=>button,setAttribute(){},removeAttribute(){}};
  const fields={'#login-form':form,'#login-error':{textContent:''},'#login-email':{value:' Preview@Example.com '},'#login-password':{value:'Preview-local-123!'}};
  const calls=[], entered=[];
  const context={URLSearchParams,AbortController,setTimeout,clearTimeout,location:{hostname:'localhost'},window:{API_BASE_URL:'http://127.0.0.1:8765/api/v1'},
    document:{cookie:'',querySelector:selector=>fields[selector]},
    fetch:async(url,options)=>{calls.push({url,options});return handler(url,options);}};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'app.js'),'utf8').replace(/\nboot\(\);\s*$/,''),context);
  context.closeAuth=()=>{}; context.enterAdmin=()=>entered.push(true);
  return {context,fields,button,calls,entered,submit:()=>context.login({preventDefault(){}})};
}
function createAccessFormClient(kind, handler) {
  const button={textContent:{register:'Cadastrar',recovery:'Enviar instruções',reset:'Redefinir senha'}[kind],disabled:false};
  const attributes={};
  const form={
    querySelector:()=>button,
    setAttribute:(name,value)=>{attributes[name]=value;},
    removeAttribute:name=>{delete attributes[name];},
    resetCalls:0,
    reset(){this.resetCalls++;},
  };
  const message={textContent:'',className:'form-message',attributes:{role:'status','aria-live':'polite'},classList:{add(value){message.className+=' '+value;}},setAttribute(name,value){this.attributes[name]=value;}};
  const fields={
    [`#${kind}-form`]:form,
    [`#${kind}-message`]:message,
    '#register-name':{value:' Cliente Teste '},
    '#register-organization':{value:' Oficina Teste '},
    '#register-email':{value:' Cliente@Example.com '},
    '#register-password':{value:'senha-segura'},
    '#recovery-email':{value:' Cliente@Example.com '},
    '#reset-password':{value:'nova-senha-segura'},
  };
  const calls=[];
  const context={
    URLSearchParams,AbortController,setTimeout:()=>1,clearTimeout:()=>{},
    location:{hostname:'localhost',hash:'',search:'',pathname:'/'},history:{replaceState(){}},
    sessionStorage:{getItem:()=>kind==='reset'?'reset-token':null,setItem(){},removeItem(){}},
    document:{cookie:'',querySelector:selector=>fields[selector]},window:{API_BASE_URL:'http://127.0.0.1:8765/api/v1',addEventListener(){}},
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'app.js'),'utf8').replace(/\nboot\(\);\s*$/,''),context);
  context.api=(url,options)=>{calls.push({url,options});return handler(url,options);};
  const event={preventDefault(){},target:form,currentTarget:form};
  return {context,button,form,message,attributes,calls,submit:()=>context[kind==='reset'?'resetPassword':kind](event)};
}
function prepareBoot(c, view='login') {
  for (const name of ['login','register','recovery','reset']) {
    c.fields[`#${name}-view`]={classList:{toggle(){}}};
  }
  c.context.setupPublic=()=>c.context.showAuth(view);
  c.context.setupAdmin=()=>{};
}

for (const view of ['reset','recovery','register']) {
  test(`restoring an admin session does not interrupt the ${view} form`,async()=>{
    const c=createLoginClient(url=>response(200,url.endsWith('/me')?{id:1,is_admin:true}:{}));
    prepareBoot(c,view);
    await c.context.boot();
    assert.equal(c.entered.length,0);
  });
}
test('normal startup still restores a valid admin session',async()=>{
  const c=createLoginClient(url=>response(200,url.endsWith('/me')?{id:1,is_admin:true}:{}));
  prepareBoot(c);
  await c.context.boot();
  assert.equal(c.entered.length,1);
});
test('startup can renew an expired session without treating refresh as a newer login',async()=>{
  const replies=[response(200,{csrf_token:'old'}),response(401),response(200,{csrf_token:'new'}),response(200,{id:1,is_admin:true})];
  const c=createLoginClient(()=>replies.shift());
  prepareBoot(c);
  await c.context.boot();
  assert.equal(c.entered.length,1); assert.equal(c.calls.length,4);
  assert.ok(c.calls[2].url.endsWith('/auth/refresh'));
});
test('startup never admits a non-admin account',async()=>{
  const c=createLoginClient(url=>response(200,url.endsWith('/me')?{id:1,is_admin:false}:{}));
  prepareBoot(c);
  await c.context.boot();
  assert.equal(c.entered.length,0);
  assert.equal(vm.runInContext('state.user',c.context),null);
});
test('a late startup response cannot overwrite a more recent manual login',async()=>{
  const gate=deferred(), started=deferred(); let meCalls=0;
  const c=createLoginClient(url=>{
    if(url.endsWith('/me')) {
      if(++meCalls===1){started.resolve();return gate.promise;}
      return response(200,{id:2,is_admin:true});
    }
    return response(200);
  });
  prepareBoot(c);
  const boot=c.context.boot(); await started.promise;
  await c.submit();
  gate.resolve(response(200,{id:1,is_admin:true})); await boot;
  assert.equal(c.entered.length,1);
  assert.equal(vm.runInContext('state.user.id',c.context),2);
});
test('login wait expires without automatic replay and permits a manual retry',async()=>{
  let expire, cleared=0, attempt=0;
  const c=createLoginClient((_url,options)=>{
    if(++attempt>1) return response(200,{is_admin:true});
    return new Promise((_resolve,reject)=>options.signal?.addEventListener('abort',()=>reject(Object.assign(new Error('Aborted'),{name:'AbortError'})),{once:true}));
  });
  c.context.setTimeout=(callback,delay)=>{assert.equal(delay,20000);expire=callback;return 1;};
  c.context.clearTimeout=()=>cleared++;
  const pending=c.submit();
  assert.equal(typeof expire,'function'); expire(); await pending;
  assert.match(c.fields['#login-error'].textContent,/demorou/);
  assert.equal(c.button.disabled,false); assert.equal(c.calls.length,1); assert.equal(cleared,1);
  await c.submit();
  assert.equal(c.entered.length,1); assert.equal(cleared,2);
});
test('blocked theme storage cannot stop admin startup or the theme switch',()=>{
  const c=createLoginClient(()=>{}), themes=[], events={};
  c.context.document.querySelectorAll=()=>[];
  c.context.document.querySelector=selector=>({addEventListener:(event,handler)=>{events[selector+':'+event]=handler;}});
  c.context.document.addEventListener=()=>{};
  c.context.document.body={classList:{contains:()=>false}};
  c.context.localStorage={getItem(){throw new Error('Storage blocked');},setItem(){throw new Error('Storage blocked');}};
  c.context.applyTheme=dark=>themes.push(dark);
  assert.doesNotThrow(()=>c.context.setupAdmin());
  assert.doesNotThrow(()=>events['#theme-toggle:click']());
  assert.deepEqual(themes,[false,true]);
});
test('the same login deadline also bounds user verification after password acceptance',async()=>{
  const started=deferred(); let expire;
  const c=createLoginClient((url,options)=>{
    if(url.endsWith('/login')) return response(200);
    started.resolve();
    return new Promise((_resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Object.assign(new Error('Aborted'),{name:'AbortError'})),{once:true}));
  });
  c.context.setTimeout=callback=>{expire=callback;return 1;}; c.context.clearTimeout=()=>{};
  const pending=c.submit(); await started.promise;
  expire(); await pending;
  assert.equal(c.entered.length,0); assert.equal(c.button.disabled,false);
  assert.equal(c.calls.length,2); assert.equal(c.calls[0].options.signal,c.calls[1].options.signal);
  assert.match(c.fields['#login-error'].textContent,/Não foi possível confirmar/);
});

test('direct admin link opens the login form without authenticating or sending credentials',()=>{
  const c=createLoginClient(()=>{throw new Error('Unexpected request');}), opened=[];
  c.context.location.hash='#login'; c.context.location.search='';
  c.context.openAuth=view=>opened.push(view);
  c.context.handleAuthLink();
  assert.deepEqual(opened,['login']); assert.equal(c.calls.length,0);
});
test('ordinary navigation and an already authenticated admin do not reopen login',()=>{
  const c=createLoginClient(()=>{}), opened=[];
  c.context.location.search=''; c.context.location.hash='#projetos';
  c.context.openAuth=view=>opened.push(view);
  c.context.handleAuthLink();
  c.context.location.hash='#login';
  vm.runInContext('state.user = {is_admin:true}',c.context);
  c.context.handleAuthLink();
  assert.deepEqual(opened,[]);
});
test('password recovery keeps precedence over the direct login link',()=>{
  const c=createLoginClient(()=>{}), opened=[], stored=[], replaced=[];
  c.context.location.hash='#login'; c.context.location.search='?reset_token=synthetic-token'; c.context.location.pathname='/';
  c.context.openAuth=view=>opened.push(view);
  c.context.sessionStorage={setItem:(key,value)=>stored.push([key,value])};
  c.context.history={replaceState:(_state,_title,url)=>replaced.push(url)};
  c.context.handleAuthLink();
  assert.deepEqual(opened,['reset']);
  assert.deepEqual(stored,[['reset_token','synthetic-token']]); assert.deepEqual(replaced,['/']);
});
test('a reset link still opens when session storage is blocked',()=>{
  const c=createLoginClient(()=>{}),opened=[];
  c.context.location.hash='#reset_token=synthetic-token';c.context.location.search='';c.context.location.pathname='/';
  c.context.sessionStorage={setItem(){throw new Error('Storage blocked');}};
  c.context.history={replaceState(){}};c.context.openAuth=view=>opened.push(view);
  assert.doesNotThrow(()=>c.context.handleAuthLink());
  assert.deepEqual(opened,['reset']);
});
test('restored admin session closes the login overlay before showing the dashboard',()=>{
  const c=createLoginClient(()=>{}), actions=[];
  // Reload definitions, since the login fixture replaces enterAdmin for isolation.
  vm.runInContext(fs.readFileSync(path.join(__dirname,'app.js'),'utf8').match(/function enterAdmin\(\)[^\r\n]+/)[0],c.context);
  c.context.closeAuth=()=>actions.push('close');
  c.context.loadDashboard=()=>actions.push('dashboard');
  c.context.document.querySelector=selector=>({classList:{add:value=>actions.push(selector+':'+value),remove:value=>actions.push(selector+':remove-'+value)}});
  c.context.enterAdmin();
  assert.equal(actions[0],'close'); assert.equal(actions.at(-1),'dashboard');
  assert.ok(actions.includes('#public-site:hidden')); assert.ok(actions.includes('#admin-app:remove-hidden'));
});
test('admin email form appears before unavailable social login choices',()=>{
  const html=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
  assert.ok(html.indexOf('id="login-form"')<html.indexOf('class="social-login"'));
  assert.match(html,/type="submit">Entrar no painel<\/button>/);
  assert.match(html,/Para administrar a marcenaria, use o formulário acima/);
});

test('admin navigation exposes only the current section to assistive technology',()=>{
  function element(dataset={}) {
    const classes=new Set();
    return {dataset,attributes:{},textContent:'',classList:{add:name=>classes.add(name),remove:name=>classes.delete(name),contains:name=>classes.has(name),toggle:(name,on)=>on?classes.add(name):classes.delete(name)},setAttribute(name,value){this.attributes[name]=value;},removeAttribute(name){delete this.attributes[name];}};
  }
  const dashboard=element(),customers=element(),title=element();
  customers.classList.add('hidden');
  const dashboardNav=element({section:'dashboard'}),customersNav=element({section:'customers'});
  dashboardNav.classList.add('active'); dashboardNav.setAttribute('aria-current','page');
  const nodes={'#dashboard':dashboard,'#customers':customers,'#admin-title':title};
  const loads=[];
  const context={
    URLSearchParams,AbortController,setTimeout:()=>1,clearTimeout:()=>{},fetch:async()=>response(200),
    location:{hostname:'localhost'},window:{API_BASE_URL:'http://127.0.0.1:8765/api/v1'},
    document:{cookie:'',querySelector:selector=>nodes[selector]||null,querySelectorAll:selector=>selector==='.admin-section'?[dashboard,customers]:selector==='#admin-nav .nav'?[dashboardNav,customersNav]:[]},
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'app.js'),'utf8').replace(/\nboot\(\);\s*$/,''),context);
  context.loadResource=(resource,options)=>loads.push({resource,options});
  context.showSection('customers');
  assert.equal(dashboardNav.attributes['aria-current'],undefined);
  assert.equal(customersNav.attributes['aria-current'],'page');
  assert.equal(dashboard.classList.contains('hidden'),true);
  assert.equal(customers.classList.contains('hidden'),false);
  assert.equal(title.textContent,'Clientes');
  assert.equal(loads.length,1);
  assert.equal(loads[0].resource,'customers');
  assert.equal(loads[0].options.reset,true);
});

test('error notifications use an assertive alert and success returns to polite status',()=>{
  const attributes={};
  const toastNode={textContent:'',className:'toast',setAttribute:(name,value)=>{attributes[name]=value;}};
  const context={
    URLSearchParams,AbortController,setTimeout:()=>1,clearTimeout:()=>{},fetch:async()=>response(200),
    location:{hostname:'localhost'},window:{API_BASE_URL:'http://127.0.0.1:8765/api/v1'},
    document:{cookie:'',querySelector:selector=>selector==='#toast'?toastNode:null,querySelectorAll:()=>[]},
  };
  vm.createContext(context);
  vm.runInContext(`${source}\nglobalThis.testToast = toast;`,context);
  context.testToast('Não foi possível salvar.','error');
  assert.equal(attributes.role,'alert');
  assert.equal(attributes['aria-live'],'assertive');
  assert.equal(attributes['aria-atomic'],'true');
  context.testToast('Registro salvo.');
  assert.equal(attributes.role,'status');
  assert.equal(attributes['aria-live'],'polite');
});

for (const scenario of [
  {kind:'register',pending:'Criando espaço...',reply:{},resetCalls:1},
  {kind:'recovery',pending:'Enviando...',reply:{message:'Se o e-mail existir, enviaremos as instruções.'},resetCalls:0},
  {kind:'reset',pending:'Redefinindo...',reply:{},resetCalls:1},
]) {
  test(`${scenario.kind} prevents duplicate requests and exposes its pending state`,async()=>{
    const gate=deferred();
    const c=createAccessFormClient(scenario.kind,()=>gate.promise);
    const first=c.submit();
    assert.equal(c.calls.length,1);
    if (scenario.kind === 'register') {
      assert.equal(c.calls[0].options.body.organization_name, 'Oficina Teste');
      assert.equal(c.calls[0].options.body.email, 'cliente@example.com');
    }
    assert.equal(c.button.disabled,true);
    assert.equal(c.button.textContent,scenario.pending);
    assert.equal(c.attributes['aria-busy'],'true');
    await c.submit();
    assert.equal(c.calls.length,1);
    gate.resolve(scenario.reply); await first;
    assert.equal(c.button.disabled,false);
    assert.equal(c.attributes['aria-busy'],undefined);
    assert.equal(c.form.resetCalls,scenario.resetCalls);
  });
}

test('failed access request restores the original label and disabled state',async()=>{
  const c=createAccessFormClient('register',async()=>{throw new Error('Sem conexão.');});
  c.button.textContent='Aguardando validação';
  c.button.disabled=true;
  await c.submit();
  assert.equal(c.button.textContent,'Aguardando validação');
  assert.equal(c.button.disabled,true);
  assert.equal(c.attributes['aria-busy'],undefined);
  assert.match(c.message.textContent,/Sem conexão/);
  assert.equal(c.form.resetCalls,0);
});

test('access form errors are assertive while confirmations remain polite',async()=>{
  const failed=createAccessFormClient('register',async()=>{throw new Error('Revise os dados.');});
  await failed.submit();
  assert.equal(failed.message.attributes.role,'alert');
  assert.equal(failed.message.attributes['aria-live'],'assertive');
  assert.equal(failed.message.attributes['aria-atomic'],'true');

  const succeeded=createAccessFormClient('recovery',async()=>({message:'Instruções enviadas.'}));
  await succeeded.submit();
  assert.equal(succeeded.message.attributes.role,'status');
  assert.equal(succeeded.message.attributes['aria-live'],'polite');
  assert.equal(succeeded.message.attributes['aria-atomic'],'true');
});

test('login accepts demo credentials, normalizes email and enters only for admin',async()=>{
  const replies=[response(200,{csrf_token:'new'}),response(200,{id:1,is_admin:true})];
  const c=createLoginClient(()=>replies.shift());
  await c.submit();
  assert.equal(c.calls[0].options.body.get('username'),'preview@example.com');
  assert.equal(c.calls[0].options.body.get('password'),'Preview-local-123!');
  assert.equal(c.entered.length,1); assert.equal(c.fields['#login-password'].value,'');
  assert.equal(c.button.disabled,false); assert.equal(c.button.textContent,'Entrar');
});
test('incorrect login displays a clear message without automatic retries',async()=>{
  const c=createLoginClient(()=>response(401));
  await c.submit();
  assert.match(c.fields['#login-error'].textContent,/E-mail ou senha incorretos/);
  assert.equal(c.calls.length,1); assert.equal(c.entered.length,0);
  assert.equal(c.button.disabled,false);
});
test('lost cookies after accepted login are reported without masking them with refresh',async()=>{
  const replies=[response(200),response(401)];
  const c=createLoginClient(()=>replies.shift());
  await c.submit();
  assert.match(c.fields['#login-error'].textContent,/senha foi aceita/);
  assert.equal(c.calls.length,2); assert.ok(c.calls.every(call=>!call.url.endsWith('/refresh')));
  assert.equal(c.entered.length,0);
});
test('double submit sends only one login while pending',async()=>{
  const gate=deferred();
  const c=createLoginClient(url=>url.endsWith('/login')?gate.promise:response(200,{is_admin:true}));
  const first=c.submit();
  assert.equal(c.button.textContent,'Entrando...');
  await c.submit(); assert.equal(c.calls.length,1);
  gate.resolve(response(200)); await first;
  assert.equal(c.entered.length,1);
});
test('non-admin remains denied and is logged out',async()=>{
  const replies=[response(200),response(200,{is_admin:false}),response(200)];
  const c=createLoginClient(()=>replies.shift());
  await c.submit();
  assert.match(c.fields['#login-error'].textContent,/permissão administrativa/);
  assert.ok(c.calls[2].url.endsWith('/logout')); assert.equal(c.entered.length,0);
});
test('network failure leaves login available for a manual retry',async()=>{
  const c=createLoginClient(()=>{throw new TypeError('Failed to fetch');});
  await c.submit();
  assert.match(c.fields['#login-error'].textContent,/conectar ao servidor/);
  assert.equal(c.button.disabled,false); assert.equal(c.entered.length,0);
});

test('401 refreshes once and replays the body with the rotated CSRF token', async () => {
  const replies = [response(401, { detail: 'Token expirado' }), response(200, { csrf_token: 'csrf-new' }), response(201, { id: 42 })];
  const { api, state, calls } = createClient(() => replies.shift());
  const body = { name: 'Cliente' };
  const result = await api('/customers', { method: 'POST', body });
  assert.deepEqual(result, { id: 42 });
  assert.equal(calls.length, 3);
  assert.equal(calls[1].url, 'https://api.example/api/v1/auth/refresh');
  assert.equal(calls[1].options.headers['X-CSRF-Token'], 'csrf-old');
  assert.equal(calls[2].options.headers['X-CSRF-Token'], 'csrf-new');
  assert.equal(calls[2].options.body, JSON.stringify(body));
  assert.deepEqual(body, { name: 'Cliente' });
  assert.equal(state.csrfToken, 'csrf-new');
});

test('concurrent 401 responses share the same refresh request', async () => {
  const bothStarted = deferred();
  const refreshing = deferred();
  const releaseRefresh = deferred();
  let originalRequests = 0;
  let refreshes = 0;
  const { api } = createClient(async (url, options) => {
    if (url.endsWith('/auth/refresh')) {
      refreshes += 1;
      refreshing.resolve();
      await releaseRefresh.promise;
      return response(200, { csrf_token: 'csrf-new' });
    }
    if (options.headers['X-CSRF-Token'] === 'csrf-old') {
      originalRequests += 1;
      if (originalRequests === 2) bothStarted.resolve();
      await bothStarted.promise;
      return response(401);
    }
    return response(200);
  });
  const first = api('/customers', { method: 'POST', body: { name: 'Cliente' } });
  const second = api('/quotes', { method: 'POST', body: { description: 'Orçamento' } });
  await refreshing.promise;
  releaseRefresh.resolve();
  await Promise.all([first, second]);
  assert.equal(refreshes, 1);
});

test('a delayed 401 reuses an already renewed session instead of refreshing again', async () => {
  const delayed = deferred();
  const issued = deferred();
  let quoteCalls = 0;
  let refreshes = 0;
  const { api } = createClient(async (url, options) => {
    if (url.endsWith('/auth/refresh')) {
      refreshes += 1;
      return response(200, { csrf_token: 'csrf-new' });
    }
    if (url.endsWith('/quotes') && ++quoteCalls === 1) {
      issued.resolve();
      return delayed.promise;
    }
    return response(options.headers['X-CSRF-Token'] === 'csrf-old' ? 401 : 200);
  });
  const late = api('/quotes', { method: 'POST', body: { description: 'Orçamento' } });
  await issued.promise;
  await api('/customers', { method: 'POST', body: { name: 'Cliente' } });
  delayed.resolve(response(401));
  await late;
  assert.equal(refreshes, 1);
});

test('a refresh service failure is not masked as invalid authentication', async () => {
  const { api, calls } = createClient((url) => url.endsWith('/auth/refresh')
    ? response(503, { detail: 'Serviço temporariamente indisponível' })
    : response(401, { detail: 'Token expirado' }));
  await assert.rejects(api('/me'), error=>error.status===503 && /servidor está temporariamente indisponível/.test(error.message));
  assert.equal(calls.length, 2);
});

test('failed login does not try to refresh an unrelated session', async () => {
  const { api, calls } = createClient(() => response(401, { detail: 'E-mail ou senha inválidos' }));
  await assert.rejects(api('/auth/login', { method: 'POST', body: new URLSearchParams({ username: 'test@example.com', password: 'invalid' }) }), /E-mail ou senha inválidos/);
  assert.equal(calls.length, 1);
});

test('a repeated 401 after renewal does not create a refresh loop', async () => {
  const { api, calls } = createClient((url) => url.endsWith('/auth/refresh')
    ? response(200, { csrf_token: 'csrf-new' })
    : response(401, { detail: 'Acesso inválido' }));
  await assert.rejects(api('/me'), /Acesso inválido/);
  assert.equal(calls.length, 3);
});

test('a failed response cannot overwrite the CSRF token', async () => {
  const { api, state } = createClient(() => response(403, { detail: 'Acesso negado', csrf_token: 'not-a-session' }));
  await assert.rejects(api('/customers'), /Acesso negado/);
  assert.equal(state.csrfToken, 'csrf-old');
});

test('a failed refresh releases the shared promise for a later attempt', async () => {
  let refreshes = 0;
  let renewed = false;
  const { api } = createClient((url) => {
    if (url.endsWith('/auth/refresh')) {
      if (++refreshes === 1) return response(503, { detail: 'Serviço indisponível' });
      renewed = true;
      return response(200, { csrf_token: 'csrf-new' });
    }
    return response(renewed ? 200 : 401);
  });
  await assert.rejects(api('/me'), error=>error.status===503 && /servidor está temporariamente indisponível/.test(error.message));
  await api('/me');
  assert.equal(refreshes, 2);
});

test('loading a CSRF token alone does not mark an expired session as renewed', async () => {
  const delayed = deferred();
  const issued = deferred();
  let meCalls = 0;
  let refreshes = 0;
  const { api } = createClient((url) => {
    if (url.endsWith('/auth/csrf')) return response(200, { csrf_token: 'csrf-loaded' });
    if (url.endsWith('/auth/refresh')) {
      refreshes += 1;
      return response(200, { csrf_token: 'csrf-new' });
    }
    if (++meCalls === 1) {
      issued.resolve();
      return delayed.promise;
    }
    return response(200);
  });
  const original = api('/me');
  await issued.promise;
  await api('/auth/csrf');
  delayed.resolve(response(401));
  await original;
  assert.equal(refreshes, 1);
});

test('a network error does not automatically replay a write', async () => {
  const { api, calls } = createClient(() => { throw new Error('Network unavailable'); });
  await assert.rejects(api('/customers', { method: 'POST', body: { name: 'Cliente' } }), /Network unavailable/);
  assert.equal(calls.length, 1);
});

test('a request without a caller deadline aborts after 20 seconds with actionable feedback', async () => {
  const client = createClient((_url, options) => options.signal ? new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name:'AbortError' })), { once:true });
  }) : response(200, []));
  const pending = client.api('/customers');
  if (client.deadlineDelay === null) {
    await pending;
    assert.equal(client.deadlineDelay, 20000);
  }
  client.expire();
  await assert.rejects(pending, /demorou mais que o esperado/i);
  assert.equal(client.calls.length, 1);
});
