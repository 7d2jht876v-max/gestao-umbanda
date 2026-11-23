/* Only public application assets are cached. User records remain in their existing storage. */
const CACHE = 'gestao-shell-217-5-navigation-yellow';
const ROOT = new URL('./', self.location.href);
const ASSETS = ['index.html','install.js','manifest.webmanifest','icons/icon-192.png','icons/icon-512.png','icons/apple-touch-icon.png','icons/icon-1024.png','supabase-config.js','baralho-cigano.html'];
const ALLOWED = new Set(ASSETS.map(path => new URL(path, ROOT).pathname));
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS.map(p => new URL(p, ROOT).href)))));
self.addEventListener('message', event => { if(event.data === 'ACTIVATE_UPDATE') self.skipWaiting(); });
self.addEventListener('activate', event => event.waitUntil((async () => {
  for(const key of await caches.keys()) if(key.startsWith('gestao-shell-') && key !== CACHE) await caches.delete(key);
  await self.clients.claim();
})()));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if(event.request.method !== 'GET' || url.origin !== ROOT.origin) return;
  const isHome = url.pathname === ROOT.pathname || url.pathname === new URL('index.html',ROOT).pathname;
  if(!isHome && !ALLOWED.has(url.pathname)) return;
  const key = isHome ? new URL('index.html',ROOT).href : url.origin + url.pathname;
  event.respondWith((async () => {
    try {
      const response = await fetch(event.request, {cache:'no-cache'});
      if(response.ok) {const cache = await caches.open(CACHE); await cache.put(key,response.clone()); return response;}
      return await caches.match(key) || response;
    } catch(error) {const cached = await caches.match(key); if(cached) return cached; throw error;}
  })());
});

/* Notificações push: recebidas apenas quando um servidor autorizado enviar um push.
   Nunca incluir dados pessoais ou financeiros no corpo da notificação. */
self.addEventListener('push', event => {
  let payload = {};
  try { payload = event.data ? event.data.json() : {}; } catch (_) { payload = {}; }
  const title = 'Gestão Umbanda — Templo Xangô';
  const allowedKinds = ['Comunicado','Estudo','Axé','Escala','Aviso'];
  const kind = allowedKinds.includes(payload.tipo) ? payload.tipo : 'Aviso';
  const body = 'Nova publicação: ' + kind + '. Abra o aplicativo para consultar.';
  const target = new URL('./', self.registration.scope).href;
  event.waitUntil(self.registration.showNotification(title, {
    body, icon: new URL('icons/icon-192.png', self.registration.scope).href,
    badge: new URL('icons/icon-192.png', self.registration.scope).href,
    tag: 'gestao-umbanda-publicacao-' + String(payload.id || 'nova').slice(0,60),
    data: {url: target}
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil((async () => {
    const target = new URL('./', self.registration.scope).href;
    const windows = await self.clients.matchAll({type:'window',includeUncontrolled:true});
    for (const client of windows) {
      if (new URL(client.url).origin === new URL(target).origin) {
        await client.focus(); return;
      }
    }
    await self.clients.openWindow(target);
  })());
});
