(() => {
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
