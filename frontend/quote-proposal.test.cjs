const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, 'quote-proposal.js'), 'utf8');
const safe = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function setup(options = {}) {
  const quote = {id:7, customer_id:126, description:'Cozinha Aurora', status:'analysis', total:'4200.00', ...options.quote};
  const customer = {id:126, name:'Cliente atualizado', email:'aurora@example.com', phone:'(13) 99999-0000', ...options.customer};
  const items = options.items ?? [
    {name:'Armário inferior', description:'MDF 18 mm', quantity:'1.00', unit_price:'2400.00', subtotal:'2400.00'},
    {name:'Armário aéreo', description:'MDF 18 mm', quantity:'1.00', unit_price:'1800.00', subtotal:'1800.00'},
  ];
  const calls = [], messages = [], writes = [], timers = [];
  const popup = {opener:{}, closed:false, location:{href:''}, close(){this.closed=true;}, document:{
    title:'', body:{textContent:''}, open(){}, write:html=>writes.push(html), close(){},
  }};
  const context = {
    AbortController,
    setTimeout:callback=>{timers.push(callback);return timers.length;}, clearTimeout(){},
    escapeHtml:safe, money:value=>Number(value).toLocaleString('pt-BR',{style:'currency',currency:'BRL'}),
    state:{rows:options.missing ? [] : [quote], customers:[{id:126,name:'Nome antigo',phone:'(11) 98888-0000',...options.cachedCustomer}]},
    toast:(...args)=>messages.push(args),
    document:{querySelector:()=>null}, loadResource:async()=>{},
    window:{open:()=>options.blocked ? null : popup,renderResource(){}},
    api:async(url,init)=>{
      calls.push({url,init});
      if(options.handler) return options.handler(url,init,{quote,items,customer,popup});
      return url.endsWith('/items') ? items : url.startsWith('/customers/') ? customer : quote;
    },
  };
  vm.runInNewContext(source,context);
  return {calls,messages,writes,popup,timers,open:()=>context.window.openQuoteProposal(7),share:()=>context.window.shareQuote(7)};
}

test('proposal fetches fresh quote, items and customer; renders the complete itemized document',async()=>{
  const c=setup();
  await c.open();
  assert.deepEqual(c.calls.map(call=>call.url),['/quotes/7','/quotes/7/items','/customers/126']);
  const html=c.writes[0];
  for(const text of ['Cliente atualizado','Armário inferior','Armário aéreo','2.400,00','1.800,00','4.200,00','Composição do orçamento']) assert.ok(html.includes(text),text);
  assert.ok(!html.includes('Nome antigo'));
  assert.equal(c.popup.opener,null);
  assert.ok(c.calls.every(call=>call.init.signal===c.calls[0].init.signal));
});

test('customer, quote and item content is escaped in printable markup',async()=>{
  const c=setup({quote:{description:'<script>bad()</script>',total:10},customer:{name:'<img src=x onerror=bad()>'},
    items:[{name:'<svg onload=bad()>',description:'<script>item()</script>',quantity:'1',unit_price:10,subtotal:10}]});
  await c.open();
  const html=c.writes[0];
  assert.ok(!html.includes('<script>')); assert.ok(!html.includes('<img')); assert.ok(!html.includes('<svg'));
  assert.match(html,/&lt;script&gt;bad/); assert.match(html,/&lt;svg/);
});

for(const status of ['pending','analysis','rejected']){
  test(status+' is clearly marked as not approved',async()=>{
    const c=setup({quote:{status}});await c.open();assert.match(c.writes[0],/NÃO APROVADA/);
  });
}
test('approved real proposal is not labelled as draft or demonstration',async()=>{
  const c=setup({quote:{status:'approved'}});await c.open();
  assert.doesNotMatch(c.writes[0],/NÃO APROVADA|DEMONSTRAÇÃO — dados fictícios/);
});
test('synthetic proposal keeps its warning even after approval',async()=>{
  const c=setup({quote:{status:'approved',description:'[DEMONSTRAÇÃO] Cozinha Aurora'}});await c.open();
  assert.match(c.writes[0],/DEMONSTRAÇÃO — dados fictícios/);
});
test('legacy quote without items does not invent a breakdown',async()=>{
  const c=setup({items:[]});await c.open();
  assert.match(c.writes[0],/Sem itens detalhados/);assert.doesNotMatch(c.writes[0],/<table>/);
});
test('items and total from different revisions cannot produce an inconsistent proposal',async()=>{
  const c=setup({quote:{total:'5000.00'}});await c.open();
  assert.equal(c.writes.length,0);assert.match(c.popup.document.body.textContent,/proposta completa/);
});
test('money totals are compared in cents, including decimal fractions',async()=>{
  const c=setup({quote:{total:'0.30'},items:[
    {name:'A',quantity:1,unit_price:'0.10',subtotal:'0.10'},
    {name:'B',quantity:1,unit_price:'0.20',subtotal:'0.20'},
  ]});await c.open();assert.equal(c.writes.length,1);
});
for(const failure of ['items','customer','malformed']){
  test('no partial printable proposal when '+failure+' fails',async()=>{
    const c=setup({handler:(url,init,{quote,items,customer})=>{
      if(url.endsWith('/items')){
        if(failure==='items') throw Error('Internal secret');
        return failure==='malformed'?{}:items;
      }
      if(url.startsWith('/customers/')){
        if(failure==='customer') throw Error('Internal secret');
        return customer;
      }
      return quote;
    }});
    await c.open();
    assert.equal(c.writes.length,0);assert.match(c.popup.document.body.textContent,/proposta completa/);
    assert.doesNotMatch(c.popup.document.body.textContent,/secret/);
  });
}
test('blocked popup requests permission without fetching data',async()=>{
  const c=setup({blocked:true});await c.open();
  assert.equal(c.calls.length,0);assert.match(c.messages[0][0],/Permita pop-ups/);
});
test('closing the popup during loading prevents late writes',async()=>{
  const c=setup({handler:(url,init,{quote,items,customer,popup})=>{
    popup.closed=true;return url.endsWith('/items')?items:url.startsWith('/customers/')?customer:quote;
  }});
  await c.open();assert.equal(c.writes.length,0);
});
test('loading timeout leaves an error, not an empty printable quote',async()=>{
  const c=setup({handler:(url,{signal})=>new Promise((resolve,reject)=>{
    signal.addEventListener('abort',()=>reject(Object.assign(new Error('timeout'),{name:'AbortError'})));
  })});
  const pending=c.open();c.timers[0]();await pending;
  assert.equal(c.writes.length,0);assert.match(c.popup.document.body.textContent,/demorou demais/);
});
test('missing record does not open or fetch a proposal',async()=>{
  const c=setup({missing:true});await c.open();
  assert.equal(c.calls.length,0);assert.equal(c.writes.length,0);assert.match(c.messages[0][0],/não encontrado/);
});
test('sharing refreshes the customer and normalizes a Brazilian WhatsApp number',async()=>{
  const c=setup({quote:{status:'approved'}});
  await c.share();
  assert.deepEqual(c.calls.map(call=>call.url),['/quotes/7','/customers/126','/quotes/7/shared']);
  assert.ok(c.calls.every(call=>call.init.signal===c.calls[0].init.signal));
  assert.match(c.popup.location.href,/^https:\/\/wa\.me\/5513999990000\?text=/);
  assert.doesNotMatch(c.popup.location.href,/5511988880000/);
});
test('closing the WhatsApp window while loading prevents the sent-history record',async()=>{
  const c=setup({quote:{status:'approved'},handler:(url,init,{quote,customer,popup})=>{
    if(url.startsWith('/customers/')){popup.closed=true;return customer;}
    return quote;
  }});
  await c.share();
  assert.equal(c.calls.some(call=>call.url.endsWith('/shared')),false);
});
test('double click starts only one WhatsApp sharing workflow',async()=>{
  let release;
  const gate=new Promise(resolve=>{release=resolve;});
  const c=setup({quote:{status:'approved'},handler:async(url,init,{quote,customer})=>{
    if(url==='/quotes/7'){await gate;return quote;}
    return url.startsWith('/customers/')?customer:quote;
  }});
  const first=c.share();const second=c.share();
  assert.equal(c.calls.filter(call=>call.url==='/quotes/7').length,1);
  release();await Promise.all([first,second]);
});
test('public inspirations are labelled concepts, not delivered portfolio photos',()=>{
  const html=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
  assert.match(html,/Não são fotografias de obras realizadas/);
  assert.equal((html.match(/• Conceito/g)||[]).length,3);
  assert.doesNotMatch(html,/Projetos em destaque/);
  assert.doesNotMatch(fs.readFileSync(path.join(__dirname,'app.js'),'utf8'),/conectado à API e ao PostgreSQL/);
});
