// Service worker: no cachea nada (el dashboard siempre necesita datos en vivo).
// Sirve para (1) poder instalar la app (ver manifest.json) y (2) recibir
// notificaciones push aunque la app esté cerrada (ver components/Notificaciones.jsx
// y backend/trading_engine/notificaciones.py).
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});

self.addEventListener("push", (event) => {
  let datos = {};
  try {
    datos = event.data ? event.data.json() : {};
  } catch {
    datos = { titulo: "ValueBet", cuerpo: event.data ? event.data.text() : "" };
  }
  const titulo = datos.titulo || "ValueBet";
  event.waitUntil(
    Promise.all([
      self.registration.showNotification(titulo, {
        body: datos.cuerpo || "",
        icon: "/icon-192.png",
        badge: "/favicon.png",
        tag: datos.tag || undefined,
        data: { url: datos.url || "/" },
      }),
      // Avisa a las pestañas abiertas para que actualicen la campana.
      self.clients.matchAll({ type: "window" }).then((clientes) =>
        clientes.forEach((c) => c.postMessage({ tipo: "notificacion-nueva" }))
      ),
    ])
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientes) => {
      for (const c of clientes) {
        if ("focus" in c) {
          c.navigate(url).catch(() => {});
          return c.focus();
        }
      }
      return self.clients.openWindow(url);
    })
  );
});
