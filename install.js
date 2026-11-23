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

  // Cores sem alterar os valores ou a lógica do financeiro.
  const financialColors = () => {
    if (!document.getElementById('xango-finance-colors')) {
      const style = document.createElement('style');
      style.id = 'xango-finance-colors';
      style.textContent = '.xango-fin-title{color:#ffdf45!important;font-weight:800!important}.xango-fin-paid{color:#5cff86!important;font-weight:800!important}.xango-fin-debt{color:#ff7777!important;font-weight:800!important}';
      document.head.appendChild(style);
    }
    const titles = new Set(['Sessão cigana','Gastos loja','Sessão de Exu','Sessão especial','Segurança do ano','Ancestrais','Sessão Cosme','Mensalidades']);
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const parent = node.parentElement;
      if (!parent || parent.closest('script,style,textarea,input,button,select,[contenteditable],.xango-fin-paid,.xango-fin-debt,.xango-fin-title')) continue;
      const text = node.nodeValue;
      if (!text || !text.trim()) continue;
      const container = parent.closest('div,article,section');
      if (!container) continue;
      const bg = getComputedStyle(container).backgroundColor;
      const brown = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(bg);
      if (!brown || !(Number(brown[1]) > Number(brown[2])*1.12 && Number(brown[2]) > Number(brown[3])*1.12 && Number(brown[1]) < 180)) continue;
      if (titles.has(text.trim())) {nodes.push([node,'title']);continue;}
      if (/Pago no mês:|Em aberto no mês:|Em aberto no Financeiro|Débitos na Inadimplência:/.test(text)) nodes.push([node,'labels']);
    }
    for (const [node,kind] of nodes) {
      if (!node.parentNode) continue;
      const fragment = document.createDocumentFragment();
      if (kind === 'title') {
        const span = document.createElement('span');span.className='xango-fin-title';span.textContent=node.nodeValue;fragment.appendChild(span);
      } else {
        const parts = node.nodeValue.split(/(Pago no mês:\s*R\$\s*[\d.,]+|Em aberto no mês:\s*R\$\s*[\d.,]+|Em aberto no Financeiro|Débitos na Inadimplência:\s*R\$\s*[\d.,]+)/gi);
        for (const part of parts) {
          if (!part) continue;
          const cls = /^Pago no mês:/i.test(part)?'xango-fin-paid':/^(Em aberto|Débitos)/i.test(part)?'xango-fin-debt':'';
          if (cls) {const span=document.createElement('span');span.className=cls;span.textContent=part;fragment.appendChild(span);}
          else fragment.appendChild(document.createTextNode(part));
        }
      }
      node.parentNode.replaceChild(fragment,node);
    }
  };
  const scheduleFinancialColors = () => { if (document.body) financialColors(); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', scheduleFinancialColors, {once:true});
  else scheduleFinancialColors();
  window.addEventListener('pageshow',scheduleFinancialColors);
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
