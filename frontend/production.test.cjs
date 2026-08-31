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
  const current=buttons.filter(button=>button.includes('aria-current="page"'));
  assert.equal(current.length,1);
  assert.match(current[0],/data-section="dashboard"/);
});
test('social sign-in choices are explicit and cannot pretend to authenticate',()=>{
  const html=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
  for(const [provider,label] of [['google','Google'],['linkedin','LinkedIn'],['facebook','Facebook']]) {
    const match=html.match(new RegExp('<button[^>]*data-social-provider="'+provider+'"[^>]*>.*?</button>'));
    assert.ok(match,provider);
    assert.match(match[0],/type="button"/);
    assert.match(match[0],/\sdisabled\s/);
    assert.match(match[0],/aria-describedby="social-login-notice"/);
    assert.ok(match[0].includes(label));
    assert.ok(match[0].includes('Em preparação'));
  }
  assert.match(html,/<form id="login-form">/);
  assert.match(html,/id="social-login-notice"/);
  assert.ok(!/accounts\.google\.com\/|linkedin\.com\/oauth|facebook\.com\/dialog/.test(html));
});
test('expanded login remains scrollable on short mobile screens',()=>{
  const css=fs.readFileSync(path.join(__dirname,'design-system.css'),'utf8');
  assert.match(css,/\.auth-card\s*\{[^}]*max-height: calc\(100dvh - 40px\);[^}]*overflow-y: auto/);
});
test('mobile admin topbar stays below the fixed navigation strip',()=>{
  const css=fs.readFileSync(path.join(__dirname,'professional.css'),'utf8');
  assert.match(css,/@media\s*\(max-width:760px\)[\s\S]*?\.topbar\{[^}]*top:64px/);
});
function mutationFixture() {
  const c=client(), notifications=[], controls=[{disabled:false},{disabled:true}], message={textContent:''};
  c.toast=(text,type)=>notifications.push({text,type});
  const view={isConnected:true, attributes:{}, querySelectorAll:()=>controls, querySelector:()=>message,
    setAttribute(key,value){this.attributes[key]=value;}, removeAttribute(key){delete this.attributes[key];}};
  return {run:c.productionTools.performMutation,view,controls,message,notifications};
}

test('studio design system loads last and preserves reduced-motion support',()=>{
  const html=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
  const css=fs.readFileSync(path.join(__dirname,'design-system.css'),'utf8');
  assert.ok(html.indexOf('./design-system.css')>html.indexOf('./professional.css'));
  assert.match(html,/<body>/);
  assert.doesNotMatch(html,/<body class="dark">/);
  assert.match(html,/<meta name="theme-color" content="#edf3ef">/);
  assert.match(css,/@media \(prefers-reduced-motion:\s*reduce\)/);
  assert.match(css,/@media \(max-width:\s*760px\)/);
  assert.ok(!css.includes('@import'));
  assert.ok(!css.includes('background-attachment: fixed'));
});
test('studio overrides cover the sidebar monogram and field focus',()=>{
  const css=fs.readFileSync(path.join(__dirname,'design-system.css'),'utf8');
  assert.match(css,/\.logo-mark,[\s\S]*?\.side-brand \.logo-mark\s*\{[^}]*background:\s*var\(--surface\)/);
  assert.match(css,/input:focus,[\s\S]*?select:focus\s*\{[^}]*box-shadow:\s*0 0 0 3px color-mix/);
  const workflow=fs.readFileSync(path.join(__dirname,'../.github/workflows/postgres.yml'),'utf8');
  const scan=workflow.split('\n').find(line=>line.includes('lorem ipsum'));
  assert.ok(scan.includes('frontend/design-system.css'));
});
test('modern LED signature is bounded, responsive and motion-safe',()=>{
  const css=fs.readFileSync(path.join(__dirname,'design-system.css'),'utf8');
  assert.match(css,/--gold:\s*#c99a2e/);
  assert.match(css,/--bg:\s*#f4f7f5/);
  assert.match(css,/\.hero-card::before,[\s\S]*?\.hero-card::after\s*\{/);
  assert.match(css,/\.hero-card::before\s*\{[^}]*height:\s*2px/);
  assert.match(css,/\.hero-card::after\s*\{[\s\S]*?width:\s*2px/);
  assert.match(css,/@keyframes studio-led/);
  assert.match(css,/@media \(prefers-reduced-motion:\s*reduce\)[\s\S]*?animation:\s*none !important/);
  assert.match(css,/\.skip-link\s*\{[\s\S]*?position:\s*fixed[\s\S]*?translateY\(calc\(-100% - 24px\)\)/);
  assert.match(css,/\.skip-link:focus-visible\s*\{\s*transform:\s*translateY\(0\)/);
});
test('social metadata identifies Multi-Marcenarias without inventing a public URL',()=>{
  const html=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
  assert.match(html,/<meta property="og:title" content="Multi-Marcenarias \| Móveis planejados">/);
  assert.match(html,/<meta name="twitter:title" content="Multi-Marcenarias \| Móveis planejados">/);
  assert.ok(!html.includes('property="og:url"'));
});
test('theme toggle updates body, accessible state and browser color',()=>{
  const c=client(), attributes={}, toggle={textContent:'',title:'',setAttribute:(name,value)=>{attributes['#theme-toggle:'+name]=value;}}, themeMeta={setAttribute:(name,value)=>{attributes['meta[name="theme-color"]:'+name]=value;}}, body={classList:{toggle:(name,value)=>{attributes[name]=value;}}};
  c.document.body=body;
  c.document.querySelector=selector=>selector==='#theme-toggle'?toggle:themeMeta;
  c.applyTheme(false);
  assert.equal(attributes.dark,false);
  assert.equal(attributes['#theme-toggle:aria-pressed'],'false');
  assert.equal(attributes['meta[name="theme-color"]:content'],'#edf3ef');
  assert.equal(attributes['#theme-toggle:aria-label'],'Tema escuro');
  assert.equal(toggle.title,'Ativar tema escuro');
  assert.equal(toggle.textContent,'☾');
  c.applyTheme(true);
  assert.equal(attributes.dark,true);
  assert.equal(attributes['#theme-toggle:aria-pressed'],'true');
  assert.equal(attributes['meta[name="theme-color"]:content'],'#14201e');
  assert.equal(attributes['#theme-toggle:aria-label'],'Tema escuro');
  assert.equal(toggle.title,'Ativar tema claro');
  assert.equal(toggle.textContent,'☀');
});
test('core studio text and accent colors meet normal-text contrast',()=>{
  const css=fs.readFileSync(path.join(__dirname,'design-system.css'),'utf8');
  const luminance=hex=>{
    const rgb=hex.match(/[a-f0-9]{2}/gi).map(channel=>parseInt(channel,16)/255)
      .map(value=>value<=.04045?value/12.92:((value+.055)/1.055)**2.4);
    return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;
  };
  for(const selector of [':root','body.dark']) {
    const block=css.slice(css.indexOf(selector));
    const tokens=Object.fromEntries([...block.slice(0,block.indexOf('}')).matchAll(/--([\w-]+):\s*(#[a-f0-9]{6});/g)].map(match=>[match[1],match[2]]));
    for(const foreground of ['ink','muted','accent']) {
      for(const background of ['bg','surface','surface-2']) {
        const levels=[luminance(tokens[foreground]),luminance(tokens[background])].sort((a,b)=>b-a);
        assert.ok((levels[0]+.05)/(levels[1]+.05)>=4.5,selector+' '+foreground+'/'+background);
      }
    }
  }
});
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
