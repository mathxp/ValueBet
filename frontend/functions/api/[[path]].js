// Cloudflare Pages Function: proxy de /api/* hacia la API Django en Render.
//
// Variables a definir en Pages -> Configuración -> Variables y secretos:
//   BACKEND_URL   URL de Render, ej. https://valuebet-api-xxxx.onrender.com (sin "/" al final)
//   PROXY_SECRET  mismo valor que PROXY_SECRET en Render (marcar como "Secreto")
//
// Al mantener /api/ en el mismo origen que el frontend, no hace falta CORS.
//
// Render (plan gratis) duerme el servicio tras 15 min sin uso y tarda ~30-50 s
// en despertar; mientras tanto responde 502/503 o corta la conexión. Por eso las
// lecturas (GET) se reintentan unas veces con espera creciente antes de rendirse.
const ESTADOS_DESPERTANDO = new Set([502, 503, 504]);
const ESPERAS_MS = [2000, 4000, 8000, 12000, 16000]; // ~42 s en total

const dormir = (ms) => new Promise((r) => setTimeout(r, ms));

export async function onRequest({ request, env }) {
  if (!env.BACKEND_URL || !env.PROXY_SECRET) {
    return Response.json(
      { detail: "Backend no configurado (faltan BACKEND_URL / PROXY_SECRET en Cloudflare Pages)." },
      { status: 503 },
    );
  }

  const incoming = new URL(request.url);
  const target = new URL(incoming.pathname + incoming.search, env.BACKEND_URL);

  const headers = new Headers(request.headers);
  headers.set("X-Proxy-Secret", env.PROXY_SECRET);
  headers.delete("Cookie");

  const esLectura = ["GET", "HEAD"].includes(request.method);
  // El cuerpo de un POST/PATCH solo se puede leer una vez: no se reintenta.
  const body = esLectura ? undefined : await request.arrayBuffer();
  const intentos = esLectura ? ESPERAS_MS.length + 1 : 1;

  let ultimo = null;
  for (let i = 0; i < intentos; i++) {
    try {
      const resp = await fetch(target, { method: request.method, headers, body, redirect: "manual" });
      if (!ESTADOS_DESPERTANDO.has(resp.status) || i === intentos - 1) {
        return new Response(resp.body, resp);
      }
      ultimo = resp.status;
    } catch {
      ultimo = "sin conexión";
    }
    if (i < intentos - 1) await dormir(ESPERAS_MS[i]);
  }

  return Response.json(
    { detail: `El servidor no respondió (${ultimo}). Puede estar despertando: reintenta en unos segundos.` },
    { status: 502 },
  );
}
