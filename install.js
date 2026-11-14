(() => {
  // Mantém o suporte offline sem exibir o quadro de instalação.
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    navigator.serviceWorker.register('./sw.js').catch(() => {});
  }
})();
