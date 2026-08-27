(() => {
  'use strict';
  const config = window.IDEAL_SITE_CONFIG || {};

  function normalizePhone(raw) {
    const value = String(raw || '').trim();
    if (!/^[+\d().\s-]+$/.test(value)) return '';
    let digits = value.replace(/\D/g, '');
    if (!value.startsWith('+') && (digits.length === 10 || digits.length === 11)) digits = `55${digits}`;
    return /^[1-9]\d{9,14}$/.test(digits) ? digits : '';
  }

  function contactUrl(message) {
    const phone = normalizePhone(config.whatsappNumber || window.WHATSAPP_NUMBER);
    if (phone) return `https://wa.me/${phone}?text=${encodeURIComponent(message)}`;
    const email = String(config.contactEmail || '').trim();
    if (/^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(email)) {
      return `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent('Solicitação de orçamento')}&body=${encodeURIComponent(message)}`;
    }
    return '';
  }

  const defaultMessage = 'Olá! Quero solicitar um orçamento para móveis planejados.';
  const url = contactUrl(defaultMessage);
  const phone = normalizePhone(config.whatsappNumber || window.WHATSAPP_NUMBER);
  const channel = document.querySelector('#company-contact');
  const location = document.querySelector('#company-location');
  const hours = document.querySelector('#company-hours');
  const header = document.querySelector('.header-actions .whatsapp');
  const notice = document.querySelector('#contact-notice');

  if (location && typeof config.locationText === 'string') location.textContent = config.locationText;
  if (hours && typeof config.businessHours === 'string') hours.textContent = config.businessHours;
  if (channel) {
    channel.replaceChildren();
    if (url) {
      const link = document.createElement('a');
      link.href = url;
      link.textContent = phone ? `WhatsApp: +${phone}` : config.contactEmail;
      if (phone) { link.target = '_blank'; link.rel = 'noopener noreferrer'; }
      channel.append(link);
    } else {
      channel.textContent = 'Nosso canal digital está em preparação. Volte em breve para solicitar seu orçamento.';
    }
  }
  if (header) {
    header.textContent = phone ? 'WhatsApp' : url ? 'E-mail' : 'Contato';
    header.href = url || '#contato';
    if (phone) { header.target = '_blank'; header.rel = 'noopener noreferrer'; }
  }
  if (!url) {
    document.querySelectorAll('[data-quote]').forEach(button => {
      button.textContent = 'Ver canais de atendimento';
    });
  }

  // setupPublic handlers resolve this global function at click time.
  window.showWhatsApp = function(message = defaultMessage) {
    const destination = contactUrl(message);
    if (!destination) {
      document.querySelector('#contato')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (notice) {
        notice.textContent = 'O atendimento digital ainda não foi ativado. Nenhuma solicitação foi enviada.';
        notice.focus();
      }
      return;
    }
    if (destination.startsWith('https://wa.me/')) {
      window.open(destination, '_blank', 'noopener,noreferrer');
    } else {
      window.location.href = destination;
    }
  };
})();
