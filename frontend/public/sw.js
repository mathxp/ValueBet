// Service worker mínimo: no cachea nada (el dashboard siempre necesita datos
// en vivo), pero su sola presencia es uno de los requisitos que los
// navegadores piden para poder "instalar" la app (ver manifest.json). Si en
// algún momento se sirve por HTTPS, esto ya deja el camino listo.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
