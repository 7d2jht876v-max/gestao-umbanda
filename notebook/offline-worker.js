// Only the application shell is available without the notebook.
const cacheName = 'notebook-offline-217-v1';
const assets = ['/index.html', '/notebook-client.js', '/install.js', '/manifest.webmanifest',
  '/baralho-cigano.html', '/icons/icon-192.png', '/icons/icon-512.png', '/icons/apple-touch-icon.png'];
self.addEventListener('install', event => event.waitUntil((async () => {
  const cache = await caches.open(cacheName);
  await cache.addAll(assets.map(path => new Request(path, {cache:'reload'})));
  await self.skipWaiting();
})()));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  const path = url.pathname === '/' ? '/index.html' : url.pathname;
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || !assets.includes(path)) return;
  event.respondWith((async () => {
    const cache = await caches.open(cacheName);
    return await cache.match(path) || fetch(event.request);
  })());
});
