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
