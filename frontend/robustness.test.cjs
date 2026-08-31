const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,'app.js'),'utf8').replace(/\nboot\(\);\s*$/,'');
const reply = (status,body={})=>({status,ok:status<400,json:async()=>body});
function deferred(){let resolve,reject;const promise=new Promise((done,fail)=>{resolve=done;reject=fail;});return {promise,resolve,reject};}

function fixture() {
  const nodes={}, events=[], requests=[], notices=[], loads=[];
  const document={cookie:'',activeElement:null,querySelector:selector=>nodes[selector]||null,querySelectorAll:()=>[]};
  function element() {
    const classes=new Set();
    return {isConnected:true,disabled:false,tabIndex:0,textContent:'',type:'password',attributes:{},
      classList:{add:name=>classes.add(name),remove:name=>classes.delete(name),contains:name=>classes.has(name),toggle:(name,on)=>on?classes.add(name):classes.delete(name)},
      setAttribute(name,value){this.attributes[name]=value;},removeAttribute(name){delete this.attributes[name];},
      focus(){document.activeElement=this;},getClientRects(){return this.visible===false?[]:[{}];},
      querySelector(){return null;},querySelectorAll(){return [];}};
  }
  const form=element(); let html='',grid=null,button=null,message=null,controls=[];
  form.data={name:'Cliente de teste'}; form.reportValidity=()=>true;
  Object.defineProperty(form,'innerHTML',{get:()=>html,set:value=>{
    if(grid) grid.isConnected=false;
    html=value; grid=value.includes('class="form-grid"')?element():null;
    form.firstElementChild=grid || (value?element():null);
    button=element();button.textContent='Cadastrar';message=element();
    const locked=element();locked.disabled=true;controls=[button,element(),locked];
  }});
  form.innerHTML='<div class="form-grid"></div>';
  form.querySelector=selector=>selector==='.form-grid'?grid:selector==='button[type="submit"]'?button:selector==='#item-message'?message:null;
  form.querySelectorAll=()=>controls;
  nodes['#item-form']=form;
  nodes['#modal']=element();nodes['#modal'].id='modal';nodes['#modal'].classList.add('hidden');
  nodes['#modal-title']=element();nodes['#auth-overlay']=element();nodes['#auth-overlay'].id='auth-overlay';nodes['#auth-overlay'].classList.add('hidden');
  nodes['#login-password']=element();nodes['#toggle-login-password']=element();
  nodes['#auth-overlay [role="dialog"]']=element();
  for(const name of ['login','register','recovery','reset']){nodes[`#${name}-view`]=element();nodes[`#${name}-view input`]=element();}
  const context={URLSearchParams,AbortController,setTimeout,clearTimeout,document,location:{hostname:'localhost'},
    FormData:class {constructor(target){this.data={...target.data};}entries(){return Object.entries(this.data);}has(key){return key in this.data;}},
    fetch:async(url,options)=>{requests.push({url,options});return reply(200);}};
  context.window=context;vm.createContext(context);
  vm.runInContext(source+'\nglobalThis.testState=state;',context);
  context.toast=(text,type)=>notices.push({text,type});context.loadResource=async resource=>loads.push(resource);
  context.setupRecordLookups=async()=>{};
  context.testState.resource='customers';context.testState.id=null;context.testState.listResource='customers';
  return {c:context,nodes,form,document,element,requests,notices,loads,events,
    get grid(){return grid;},get button(){return button;},get message(){return message;},get controls(){return controls;},
    submit:()=>context.submitItem({preventDefault(){},target:form})};
}

test('validation arrays become readable field names without exposing submitted values',async()=>{
  const f=fixture();f.c.fetch=async()=>reply(422,{detail:[{loc:['body','email'],input:'private-value',msg:'invalid'},{loc:['body','name'],msg:'missing'}]});
  await assert.rejects(f.c.api('/customers',{method:'POST',body:{}}),error=>error.status===422 && error.message==='Revise os campos informados: E-mail, Nome.');
});
test('unknown structured errors use a readable fallback',async()=>{
  const f=fixture();f.c.fetch=async()=>reply(400,{detail:{private:'internal'}});
  await assert.rejects(f.c.api('/customers'),/Não foi possível concluir/);
});
test('a successful HTTP response with invalid JSON is never treated as a saved record',async()=>{
  const f=fixture();f.c.fetch=async()=>({status:200,ok:true,json:async()=>{throw new SyntaxError('html instead of json');}});
  await assert.rejects(f.c.api('/customers',{method:'POST',body:{}}),/resposta inválida/);
});
test('aborting response-body reading remains an abort rather than success',async()=>{
  const f=fixture();f.c.fetch=async()=>({status:200,ok:true,json:async()=>{throw Object.assign(new Error('abort'),{name:'AbortError'});}});
  await assert.rejects(f.c.api('/customers'),error=>error.name==='AbortError');
});
test('rate limits are explained without automatically replaying the request',async()=>{
  const f=fixture();let calls=0;f.c.fetch=async()=>{calls++;return reply(429);};
  await assert.rejects(f.c.api('/customers',{method:'POST',body:{}}),/Muitas tentativas/);assert.equal(calls,1);
});
test('double submit performs only one write and snapshots the original record',async()=>{
  const f=fixture(),gate=deferred(),calls=[];f.c.testState.id=7;
  f.c.api=(url,options)=>{calls.push({url,options});return gate.promise;};
  const first=f.submit();await f.submit();
  assert.equal(calls.length,1);assert.equal(calls[0].url,'/customers/7');assert.equal(calls[0].options.method,'PUT');
  assert.ok(f.controls.every(control=>control.disabled));assert.equal(f.button.textContent,'Salvando...');
  f.c.testState.id=null;gate.resolve({id:7,name:'Cliente de teste'});await first;
  assert.equal(f.notices[0].text,'Alterações salvas com sucesso.');
});
test('failed save keeps fields, restores controls and shows persistent inline feedback',async()=>{
  const f=fixture(),grid=f.grid;f.c.api=async()=>{throw new Error('Revise o e-mail.');};
  await f.submit();assert.equal(f.grid,grid);assert.equal(f.form.data.name,'Cliente de teste');
  assert.equal(f.message.textContent,'Revise o e-mail.');assert.deepEqual(f.controls.map(control=>control.disabled),[false,false,true]);
  assert.equal(f.button.textContent,'Cadastrar');assert.equal(f.form.attributes['aria-busy'],undefined);
});
test('an aborted save is not retried and explains its uncertain outcome',async()=>{
  const f=fixture();let expire,calls=0;
  f.c.setTimeout=(callback,delay)=>{assert.equal(delay,20000);expire=callback;return 1;};f.c.clearTimeout=()=>{};
  f.c.api=(_url,options)=>{calls++;return new Promise((_resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Object.assign(new Error('abort'),{name:'AbortError'})),{once:true}));};
  const pending=f.submit();expire();await pending;
  assert.equal(calls,1);assert.match(f.message.textContent,/Confira a lista antes de reenviar/);assert.equal(f.button.disabled,false);
});
test('an invalid form is not submitted',async()=>{
  const f=fixture();let calls=0;f.form.reportValidity=()=>false;f.c.api=async()=>{calls++;};
  await f.submit();assert.equal(calls,0);assert.equal(f.button.disabled,false);
});
test('a server failure during saving keeps the form and warns before another send',async()=>{
  const f=fixture();f.c.api=async()=>{throw Object.assign(new Error('Service unavailable'),{status:503});};
  await f.submit();assert.match(f.message.textContent,/Confira a lista antes de reenviar/);assert.equal(f.button.disabled,false);
});
test('an old save cannot close, re-enable or refresh a newer form',async()=>{
  const f=fixture(),gate=deferred();f.c.api=()=>gate.promise;
  const pending=f.submit();f.form.innerHTML='<div class="form-grid">Outro cadastro</div>';
  const newer=f.grid;f.button.disabled=true;f.form.setAttribute('aria-busy','true');
  gate.resolve({id:8,name:'Salvo'});await pending;
  assert.equal(f.grid,newer);assert.equal(f.button.disabled,true);assert.equal(f.form.attributes['aria-busy'],'true');
  assert.equal(f.notices.length,0);assert.equal(f.loads.length,0);
});
test('double delete sends one request, restores failure state and permits a later retry',async()=>{
  const f=fixture(),gate=deferred(),button=f.element();let calls=0,confirmations=0;
  button.textContent='Excluir';
  f.nodes['#customers tr[data-row-id="7"] .danger']=button;
  f.c.confirm=()=>{confirmations++;return true;};
  f.c.api=()=>{calls++;return gate.promise;};
  const first=f.c.deleteItem('customers',7);
  const duplicate=f.c.deleteItem('customers',7);
  assert.equal(confirmations,1);assert.equal(calls,1);
  assert.equal(button.disabled,true);assert.equal(button.textContent,'Excluindo...');assert.equal(button.attributes['aria-busy'],'true');
  gate.reject(new Error('Falha ao excluir.'));await Promise.all([first,duplicate]);
  assert.equal(f.notices.length,1);assert.equal(f.notices[0].text,'Falha ao excluir.');assert.equal(f.notices[0].type,'error');assert.equal(f.loads.length,0);
  assert.equal(button.disabled,false);assert.equal(button.textContent,'Excluir');assert.equal(button.attributes['aria-busy'],undefined);
  f.c.api=async()=>{calls++;};
  await f.c.deleteItem('customers',7);
  assert.equal(confirmations,2);assert.equal(calls,2);assert.equal(f.loads.length,1);
});
test('late form loading cannot replace a more recently requested record',async()=>{
  const f=fixture(),gate=deferred();f.c.api=url=>url.endsWith('/1')?gate.promise:Promise.resolve({id:2,name:'Atual'});
  const old=f.c.openForm('customers',1);await f.c.openForm('customers',2);
  const currentHtml=f.form.innerHTML;gate.resolve({id:1,name:'Antigo'});
  assert.equal(await old,false);assert.equal(f.form.innerHTML,currentHtml);assert.equal(f.c.testState.id,2);
});
test('closing a modal invalidates a pending form load',async()=>{
  const f=fixture(),gate=deferred();f.c.api=()=>gate.promise;
  const pending=f.c.openForm('customers',1);f.c.closeModal();gate.resolve({id:1,name:'Antigo'});
  assert.equal(await pending,false);assert.equal(f.form.innerHTML,'');assert.ok(f.nodes['#modal'].classList.contains('hidden'));
});
test('a late ordinary form cannot replace an intervening history or production view',async()=>{
  const f=fixture(),gate=deferred();f.c.api=()=>gate.promise;
  const pending=f.c.openForm('customers',1);f.form.innerHTML='<div class="history-modal">Histórico</div>';
  gate.resolve({id:1,name:'Antigo'});assert.equal(await pending,false);assert.match(f.form.innerHTML,/Histórico/);
});
test('finishing reference lookup cannot relabel a newer specialized modal',async()=>{
  const f=fixture(),gate=deferred();f.c.setupRecordLookups=()=>gate.promise;
  const pending=f.c.openForm('customers');f.form.innerHTML='<div class="production-modal">Produção</div>';
  gate.resolve();assert.equal(await pending,false);
});
test('a project date is rendered as the calendar day received from the API',()=>{
  const f=fixture();
  assert.equal(f.c.formatCell('projects','project_date','2026-08-28'),'28/08/2026');
});
test('managed modal moves focus inside and restores the trigger when closed',()=>{
  const f=fixture(),trigger=f.element(),firstField=f.element();
  f.document.activeElement=trigger;
  f.form.querySelector=selector=>selector==='[data-first]'?firstField:null;
  f.c.openManagedModal('Novo registro','<div data-first></div>','[data-first]');
  assert.equal(f.nodes['#modal-title'].textContent,'Novo registro');
  assert.equal(f.document.activeElement,firstField);
  f.c.closeModal();
  assert.equal(f.document.activeElement,trigger);
});
test('control boundary tokens meet 3:1 against their adjacent surfaces',()=>{
  const css=fs.readFileSync(path.join(__dirname,'design-system.css'),'utf8');
  const blocks=[css.match(/:root\s*{([\s\S]*?)}/)[1],css.match(/body\.dark\s*{([\s\S]*?)}/)[1]];
  const color=(block,name)=>block.match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`,'i'))[1];
  const luminance=hex=>hex.slice(1).match(/../g).map(value=>parseInt(value,16)/255)
    .map(value=>value<=.04045?value/12.92:((value+.055)/1.055)**2.4)
    .reduce((sum,value,index)=>sum+value*[.2126,.7152,.0722][index],0);
  const contrast=(a,b)=>{const values=[luminance(a),luminance(b)].sort((x,y)=>y-x);return(values[0]+.05)/(values[1]+.05);};
  for(const block of blocks){
    const line=color(block,'line-strong');
    for(const surface of ['bg','surface','surface-2']) assert.ok(contrast(line,color(block,surface))>=3,`${line} on ${surface}`);
  }
});
test('password visibility has an accessible state and resets when login is closed',()=>{
  const f=fixture();f.c.toggleLoginPassword();assert.equal(f.nodes['#login-password'].type,'text');
  assert.equal(f.nodes['#toggle-login-password'].attributes['aria-pressed'],'true');
  f.c.closeAuth();assert.equal(f.nodes['#login-password'].type,'password');assert.equal(f.nodes['#toggle-login-password'].attributes['aria-pressed'],'false');
});
test('auth forms update their dialog title and focus the correct first field',()=>{
  const f=fixture();f.c.showAuth('reset');
  assert.equal(f.nodes['#auth-overlay [role="dialog"]'].attributes['aria-labelledby'],'reset-title');
  assert.equal(f.document.activeElement,f.nodes['#reset-view input']);
});
test('Tab and Shift+Tab stay inside the visible dialog and skip disabled controls',()=>{
  const f=fixture(),overlay=f.nodes['#auth-overlay'],first=f.element(),disabled=f.element(),last=f.element();
  disabled.disabled=true;overlay.classList.remove('hidden');overlay.querySelectorAll=()=>[first,disabled,last];
  let prevented=0;f.document.activeElement=last;
  f.c.handleDialogKeys({key:'Tab',preventDefault(){prevented++;}});assert.equal(f.document.activeElement,first);
  f.c.handleDialogKeys({key:'Tab',shiftKey:true,preventDefault(){prevented++;}});assert.equal(f.document.activeElement,last);assert.equal(prevented,2);
});
test('Escape closes auth first, preserving the underlying edit form and restoring focus',()=>{
  const f=fixture(),trigger=f.element(),grid=f.grid;f.document.activeElement=trigger;
  f.nodes['#modal'].classList.remove('hidden');f.c.openAuth();
  f.c.handleDialogKeys({key:'Escape',preventDefault(){}});
  assert.ok(f.nodes['#auth-overlay'].classList.contains('hidden'));assert.equal(f.grid,grid);assert.equal(f.document.activeElement,trigger);
});
test('auth dialog titles, password button and robustness CI checks are wired in source',()=>{
  const html=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
  for(const view of ['login','register','recovery','reset'])assert.ok(html.includes(`id="${view}-title"`));
  assert.match(html,/id="toggle-login-password"[^>]+type="button"[^>]+aria-controls="login-password"/);
  const workflow=fs.readFileSync(path.join(__dirname,'../.github/workflows/postgres.yml'),'utf8');
  assert.match(workflow,/run: node frontend\/robustness.test.cjs/);
  assert.match(workflow,/run: node frontend\/smart-quotes.test.cjs/);
});
