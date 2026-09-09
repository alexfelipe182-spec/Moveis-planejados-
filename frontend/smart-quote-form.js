// Compatibility entry point. The maintained workflow lives in smart-quotes.js.
(() => {
  if (window.openSmartQuote) return;
  window.openSmartQuote = () => window.createItem('quotes');
})();
