const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, 'public-contact.js'), 'utf8');
function setup(config = {}) {
  const selectors = {};
  function element() { return { textContent: '', href: '', children: [], replaceChildren() { this.children = []; }, append(child) { this.children.push(child); }, focus() { this.focused = true; }, scrollIntoView() { this.scrolled = true; } }; }
  ['#company-contact', '#company-location', '#company-hours', '.header-actions .whatsapp', '#contact-notice', '#contato'].forEach(key => { selectors[key] = element(); });
  const buttons = [element(), element()];
  const opened = [];
  const window = { IDEAL_SITE_CONFIG: config, open: (...args) => opened.push(args), location: { href: '' } };
  const context = { window, document: { querySelector: key => selectors[key], querySelectorAll: () => buttons, createElement: element } };
  vm.runInNewContext(source, context);
  return { window, opened, selectors, buttons };
}

test('missing company contact is honest and never opens an invented destination', () => {
  const { window, opened, selectors, buttons } = setup();
  window.showWhatsApp();
  assert.equal(opened.length, 0);
  assert.equal(selectors['.header-actions .whatsapp'].textContent, 'Contato');
  assert.equal(selectors['#contact-notice'].focused, true);
  assert.match(selectors['#contact-notice'].textContent, /Nenhuma solicitação foi enviada/);
  assert.equal(buttons[0].textContent, 'Ver canais de atendimento');
});

test('configured WhatsApp uses a validated number and encoded message', () => {
  const { window, opened, selectors } = setup({ whatsappNumber: '+55 (13) 99999-0000' });
  window.showWhatsApp('Olá & medidas?');
  assert.equal(opened[0][0], `https://wa.me/5513999990000?text=${encodeURIComponent('Olá & medidas?')}`);
  assert.equal(opened[0][2], 'noopener,noreferrer');
  assert.equal(selectors['#company-contact'].children[0].rel, 'noopener noreferrer');
  assert.equal(selectors['#company-contact'].children[0].textContent, 'WhatsApp: +55 (13) 99999-0000');
});

test('a Brazilian number supplied with DDD receives country code', () => {
  const { window, opened } = setup({ whatsappNumber: '(13) 99999-0000' });
  window.showWhatsApp();
  assert.match(opened[0][0], /^https:\/\/wa\.me\/5513999990000\?/);
});

test('invalid contact cannot become a script URL', () => {
  const { window, opened } = setup({ whatsappNumber: 'javascript:5513999990000', contactEmail: 'x@example.com\nBcc:bad@example.com' });
  window.showWhatsApp();
  assert.equal(opened.length, 0);
  assert.equal(window.location.href, '');
});

test('email is a working fallback and company text is rendered as text', () => {
  const { window, selectors } = setup({ contactEmail: 'contato@example.com', locationText: '<script>bad</script>' });
  window.showWhatsApp('Um orçamento');
  assert.match(window.location.href, /^mailto:contato%40example\.com\?/);
  assert.equal(selectors['#company-location'].textContent, '<script>bad</script>');
});
