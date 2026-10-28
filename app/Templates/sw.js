/* Service Worker de Sazón Caribeño — notificaciones push (Web Push / VAPID). */

const BASE = new URL(self.registration.scope).pathname;
const ICONO = `${BASE}Imagenes/notificacion.png`;
const RUTA_APP = `${BASE}index.html`;

self.addEventListener('install', event => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', event => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', event => {
  let payload = {};
  if (event.data) {
    try {
      payload = event.data.json();
    } catch (error) {
      payload = { body: event.data.text() };
    }
  }

  const titulo = payload.title || 'Sazón Caribeño';
  const opciones = {
    body: payload.body || '',
    icon: payload.icon || ICONO,
    badge: payload.badge || ICONO,
    tag: payload.tag || 'sazoncaribeno',
    renotify: false,
    vibrate: [120, 60, 120],
    requireInteraction: true,
    data: {
      url: payload.url || RUTA_APP,
      orden_id: payload.data?.orden_id ?? null,
      tipo: payload.data?.tipo || null,
    },
  };

  event.waitUntil(self.registration.showNotification(titulo, opciones));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const destino = (event.notification.data && event.notification.data.url) || RUTA_APP;
  const url = new URL(destino, self.location.origin);
  const params = url.searchParams;

  event.waitUntil((async () => {
    const clientes = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const cliente of clientes) {
      if ('focus' in cliente && cliente.url.startsWith(new URL(BASE, self.location.origin).href)) {
        await cliente.focus();
        cliente.postMessage({
          tipo: 'destino',
          pantalla: params.get('pantalla'),
          mesa: params.get('mesa'),
          estudio: params.get('estudio'),
          novedades: params.get('novedades'),
        });
        return cliente;
      }
    }
    return self.clients.openWindow(url.href);
  })());
});
