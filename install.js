(() => {
  // Identidade visual: mantém o fundo marrom e destaca textos de ações em amarelo negrito.
  const applyColors = () => {
    if (document.getElementById('xango-yellow-actions')) return;
    const style = document.createElement('style');
    style.id = 'xango-yellow-actions';
    style.textContent = `
      button:not(.close):not([aria-label*="Fechar"]),
      input[type="button"], input[type="submit"],
      a.btn, a.button, .btn, .button {
        color: #ffdf45 !important;
        font-weight: 800 !important;
      }
      button *, .btn *, .button * { color: inherit !important; font-weight: inherit !important; }
    `;
    (document.head || document.documentElement).appendChild(style);
  };
  applyColors();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', applyColors, {once:true});
  // Atualiza o aplicativo instalado ao abrir ou retornar a ele.
  // Não altera dados, credenciais ou mecanismos de sincronização.
  if (!('serviceWorker' in navigator) || location.protocol !== 'https:') return;
  let refreshing = false;
  let registration;
  const check = () => {
    if (document.visibilityState !== 'visible' || !registration) return;
    registration.update().catch(() => {});
  };
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (refreshing) return;
    refreshing = true;
    // Evita recarregar uma tela com campos sendo editados.
    const active = document.activeElement;
    const editing = active && (active.matches('input,textarea,select,[contenteditable="true"]'));
    if (!editing) location.reload();
    else refreshing = false;
  });
  navigator.serviceWorker.register('./sw.js').then(reg => {
    registration = reg;
    const activate = () => {
      if (reg.waiting && navigator.serviceWorker.controller) {
        reg.waiting.postMessage('ACTIVATE_UPDATE');
      }
    };
    activate();
    reg.addEventListener('updatefound', () => {
      const worker = reg.installing;
      if (worker) worker.addEventListener('statechange', () => {
        if (worker.state === 'installed') activate();
      });
    });
    check();
    document.addEventListener('visibilitychange', check);
    window.addEventListener('pageshow', check);
    window.addEventListener('focus', check);
  }).catch(() => {});
})();
