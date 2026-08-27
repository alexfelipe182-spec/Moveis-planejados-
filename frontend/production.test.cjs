const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
function client() {
  const context = { location:{hostname:'localhost'}, document:{querySelector:()=>null}, URLSearchParams,
    FormData:class { constructor(form){this.form=form;} get(key){return this.form[key] ?? null;} } };
  context.window=context; vm.createContext(context);
  const app=fs.readFileSync(path.join(__dirname,'app.js'),'utf8').replace(/\nboot\(\);\s*$/,'');
  vm.runInContext(app,context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'production.js'),'utf8'),context);
  return context;
}
test('new resources expose the correct authenticated endpoints',()=>{
  const c=client();
  assert.equal(vm.runInContext('configs.suppliers.endpoint',c),'/suppliers');
  assert.equal(vm.runInContext('configs.materials.endpoint',c),'/materials');
});
test('supplier text is escaped and has editable contact fields',()=>{
  const c=client(), html=c.formHtml('suppliers',{name:'"><script>alert(1)</script>'});
  assert.ok(html.includes('&lt;script&gt;'));
  assert.ok(!html.includes('<script>'));
  assert.match(html,/name="contact_name"/);
  assert.match(html,/name="is_active"/);
});
test('material supplier is optional and supports searchable pagination',()=>{
  const c=client(), html=c.formHtml('materials',{unit_cost:'12.30',waste_percent:'10'});
  assert.match(html,/data-collection="suppliers"/);
  assert.match(html,/name="supplier_id" aria-label="Fornecedor"  data-lookup-selected/);
  assert.match(html,/name="unit_cost"/);
  assert.match(html,/name="waste_percent"/);
});
test('project stages are ordered and terminal states cannot advance',()=>{
  const c=client(), flow=c.productionTools.nextStage;
  let step='planning', seen=[];
  while(flow[step]){step=flow[step];seen.push(step);}
  assert.deepEqual(seen,['measurement','technical_design','purchasing','production','installation','delivered','completed']);
  assert.equal(flow.completed,undefined); assert.equal(flow.cancelled,undefined);
});
test('cost payload uses project context and never sends a client-calculated total',()=>{
  const c=client(), payload=c.productionTools.costPayload({material_id:'125',category:'material',description:' MDF ',quantity:'2',unit_cost:'0',project_id:'999',total_cost:'1'},7);
  assert.deepEqual(JSON.parse(JSON.stringify(payload)),{project_id:7,material_id:125,category:'material',description:'MDF',quantity:2,unit_cost:0});
});
test('cost without material is supported and existing customer forms still work',()=>{
  const c=client();
  assert.equal(c.productionTools.costPayload({material_id:'',category:'labor',description:'Montagem',quantity:'1',unit_cost:'50'},7).material_id,null);
  assert.match(c.formHtml('customers',{}),/name="name"/);
});

test('Multi-Marcenarias identity is consistent across public page and proposals',()=>{
  const html=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
  const proposal=fs.readFileSync(path.join(__dirname,'quote-proposal.js'),'utf8');
  assert.match(html,/<title>Multi-Marcenarias \| Móveis planejados<\/title>/);
  assert.equal((html.match(/>MM<\/span>/g)||[]).length,4);
  assert.ok(!/Marcenaria Ideal|>MI<\/span>|<small>Ideal/.test(html));
  assert.ok(!proposal.includes('Marcenaria Ideal'));
  assert.match(proposal,/Multi-Marcenarias/);
});
test('collapsed admin navigation keeps explicit accessible names',()=>{
  const html=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
  const buttons=html.match(/<button class="nav[^>]+>/g)||[];
  assert.equal(buttons.length,8);
  for(const button of buttons) assert.match(button,/aria-label="[^"]+"/);
});
function mutationFixture() {
  const c=client(), notifications=[], controls=[{disabled:false},{disabled:true}], message={textContent:''};
  c.toast=(text,type)=>notifications.push({text,type});
  const view={isConnected:true, attributes:{}, querySelectorAll:()=>controls, querySelector:()=>message,
    setAttribute(key,value){this.attributes[key]=value;}, removeAttribute(key){delete this.attributes[key];}};
  return {run:c.productionTools.performMutation,view,controls,message,notifications};
}
test('one pending mutation blocks another and restores original disabled states',async()=>{
  const f=mutationFixture(); let resolveWrite, writes=0;
  const pending=new Promise(resolve=>{resolveWrite=resolve;});
  const first=f.run(f.view,()=>{writes++;return pending;},async()=>true,'Atualizado');
  assert.ok(f.controls.every(control=>control.disabled));
  assert.equal(f.view.attributes['aria-busy'],'true');
  await f.run(f.view,()=>{writes++;},async()=>true,'Duplicado');
  assert.equal(writes,1);
  resolveWrite(); await first;
  assert.deepEqual(f.controls.map(control=>control.disabled),[false,true]);
  assert.equal(f.view.attributes['aria-busy'],undefined);
  assert.deepEqual(f.notifications,[{text:'Atualizado',type:'success'}]);
});
test('saved mutation with failed refresh does not claim the total was updated',async()=>{
  const f=mutationFixture();
  await f.run(f.view,async()=>{},async()=>false,'Total atualizado');
  assert.equal(f.notifications[0].type,'error');
  assert.match(f.notifications[0].text,/Salvo, mas/);
  assert.match(f.notifications[0].text,/não repita/);
});
test('refresh exception is distinguished from failed write',async()=>{
  const f=mutationFixture();
  await f.run(f.view,async()=>{},async()=>{throw new Error('offline');},'Atualizado');
  assert.match(f.message.textContent,/Salvo, mas/);
  assert.equal(f.notifications.length,0);
  assert.equal(f.controls[0].disabled,false);
});
test('failed write is not replayed and leaves fields available for review',async()=>{
  const f=mutationFixture(); let writes=0, refreshes=0;
  await f.run(f.view,async()=>{writes++;throw new Error('Sem conexão');},async()=>{refreshes++;},'Atualizado');
  assert.equal(writes,1); assert.equal(refreshes,0);
  assert.match(f.message.textContent,/Confira a lista/);
  assert.equal(f.controls[0].disabled,false);
});
test('closing the modal during a write prevents stale refresh and notifications',async()=>{
  const f=mutationFixture(); let refreshed=false;
  await f.run(f.view,async()=>{f.view.isConnected=false;},async()=>{refreshed=true;},'Atualizado');
  assert.equal(refreshed,false); assert.equal(f.notifications.length,0);
});
test('new attempt clears the old error and can run after a failed write',async()=>{
  const f=mutationFixture();
  await f.run(f.view,async()=>{throw new Error('Falha anterior');},async()=>true,'Atualizado');
  assert.match(f.message.textContent,/Falha anterior/);
  await f.run(f.view,async()=>{assert.equal(f.message.textContent,'');},async()=>true,'Atualizado');
  assert.deepEqual(f.notifications,[{text:'Atualizado',type:'success'}]);
});
