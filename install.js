(() => {
  let promptEvent;
  const panel = document.createElement('section');
  panel.className = 'card';
  panel.style.marginBottom = '16px';
  panel.innerHTML = '<h2>Aplicativo no celular e tablet</h2><p id="install-info"></p><div style="display:flex;gap:10px;flex-wrap:wrap"><button type="button" id="install-app">Instalar aplicativo</button><button type="button" id="update-app">Verificar atualização</button></div><p id="app-update-status" role="status" aria-live="polite"></p><small>Atualização 136 • Os dados são salvos neste aparelho. Para transferir cadastros, use o backup. As funções de nuvem precisam de internet.</small>';
  document.querySelector('main').prepend(panel);
  const info = panel.querySelector('#install-info');
  const install = panel.querySelector('#install-app');
  const status = panel.querySelector('#app-update-status');
  function render() {
    const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone;
    info.textContent = standalone ? 'Você está usando o aplicativo pela tela inicial.' : 'iPhone/iPad: abra no Safari, toque em Compartilhar e Adicionar à Tela de Início. Android: use Instalar aplicativo ou o menu do navegador.';
    install.hidden = !promptEvent || standalone;
  }
  addEventListener('beforeinstallprompt', e => {e.preventDefault();promptEvent=e;render();});
  addEventListener('appinstalled', () => {promptEvent=null;render();});
  install.onclick = async () => {if(!promptEvent)return;await promptEvent.prompt();await promptEvent.userChoice;promptEvent=null;render();};
  render();
  let registration;
  if('serviceWorker' in navigator && location.protocol === 'https:') {
    navigator.serviceWorker.register('./sw.js').then(r => {registration=r;if(r.waiting)status.textContent='Há uma atualização pronta. Salve os campos e toque em Verificar atualização.';}).catch(() => {status.textContent='Não foi possível preparar o uso offline. Tente novamente com internet.';});
  }
  panel.querySelector('#update-app').onclick = async () => {
    if(!navigator.onLine){status.textContent='Conecte o aparelho à internet para verificar atualizações.';return;}
    if(!confirm('Salve primeiro os campos que está editando. Atualizar e reabrir o aplicativo agora? Os cadastros salvos serão mantidos.'))return;
    try {
      if(registration){await registration.update();if(registration.installing)await new Promise((resolve,reject)=>{const w=registration.installing;const timer=setTimeout(()=>reject(Error('A atualização está demorando. Tente novamente.')),30000);w.addEventListener('statechange',()=>{if(w.state==='installed'){clearTimeout(timer);resolve();}if(w.state==='redundant'){clearTimeout(timer);reject(Error('Falha ao preparar a atualização.'));}});});if(registration.waiting){navigator.serviceWorker.addEventListener('controllerchange',()=>location.reload(),{once:true});registration.waiting.postMessage('ACTIVATE_UPDATE');return;}}
      location.reload();
    }catch(e){status.textContent=e.message||'Não foi possível atualizar. Tente novamente.';}
  };
})();
