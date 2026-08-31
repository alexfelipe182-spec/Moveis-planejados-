const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function tools() {
  const context = {
    window:{createItem(){}}, document:{querySelector(){return null;},createElement(){return {}; }},
    FormData:class { constructor(form){this.form=form;} get(name){return this.form.values?.[name]??null;} }, api:async()=>({id:77,description:'Cozinha'}), toast(){}, showSection(){}, recordLookupField(){}, setupRecordLookups(){},
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'smart-quotes.js'),'utf8'),context);
  return context.window.smartQuoteTools;
}

test('item payload accepts the dimension example displayed by the form',()=>{
  const payload=tools().itemPayload({name:'Armário',quantity:1,unit_price:900,measurements:'2,40 × 2,10 × 0,60m'});
  assert.deepEqual(JSON.parse(JSON.stringify(payload)),{
    name:'Armário',quantity:1,unit_price:900,width:2.4,height:2.1,depth:0.6,
  });
});

test('an invalid dimension is rejected instead of being saved as a partial measurement',()=>{
  assert.throws(()=>tools().itemPayload({name:'Armário',quantity:1,unit_price:900,measurements:'2,40 × inválida × 0,60 m'}),/medidas/i);
});

test('uppercase X and optional unit suffixes remain valid',()=>{
  const payload=tools().itemPayload({name:'Armário',quantity:1,unit_price:900,measurements:'2,40m X 2,10m X 0,60m'});
  assert.deepEqual(JSON.parse(JSON.stringify(payload)),{name:'Armário',quantity:1,unit_price:900,width:2.4,height:2.1,depth:0.6});
});

test('a persisted quote is distinguished when opening its items fails',async()=>{
  const helper=tools();
  await assert.rejects(helper.createQuoteAndOpenItems({description:'Cozinha'},async()=>{throw new Error('offline');}),error=>error.quotePersisted===true&&error.quote.id===77);
});

test('analysis payload includes technical context and tracks every invalidating field',()=>{
  const helper=tools();
  const payload=helper.analysisPayload({values:{
    material_cost:'800',hardware_cost:'350',labor_cost:'900',finishing_cost:'450',profit_margin:'30',
    description:'  Cozinha planejada  ',measurements:' 3,20m × 2,40m ',materials:' MDF branco 18mm ',
  }});

  assert.deepEqual(JSON.parse(JSON.stringify(payload)),{
    material_cost:800,hardware_cost:350,labor_cost:900,finishing_cost:450,profit_margin:30,
    description:'Cozinha planejada',measurements:'3,20m × 2,40m',materials:'MDF branco 18mm',
  });
  assert.deepEqual(JSON.parse(JSON.stringify(helper.analysisFields)),[
    'material_cost','hardware_cost','labor_cost','finishing_cost','profit_margin','description','measurements','materials',
  ]);
});

test('analysis origin distinguishes external fallback from ordinary local analysis',()=>{
  const helper=tools();

  assert.equal(helper.analysisOrigin({analysis_source:'local-analysis'}),'Análise segura local');
  assert.equal(helper.analysisOrigin({analysis_source:'openai-assisted'}),'IA conectada + regras de segurança');
  assert.equal(helper.analysisOrigin({analysis_source:'local-fallback'}),'IA externa indisponível • análise local aplicada');
});
