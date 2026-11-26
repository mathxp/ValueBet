// Cloudflare Pages Function: proxy de /api/* hacia el backend Django que corre
// en la PC local, expuesto mediante Cloudflare Tunnel.
//
// Variables a definir en Pages -> Configuración -> Variables y secretos:
//   BACKEND_URL   URL del tunnel, ej. https://xxxx.trycloudflare.com (sin "/" al final)
//   PROXY_SECRET  mismo valor que PROXY_SECRET en backend/.env (marcar como "Secreto")
//
// Al mantener /api/ en el mismo origen que el frontend, no hace falta CORS y
// cambiar la URL del tunnel solo requiere editar BACKEND_URL (sin recompilar).
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

  try {
    const resp = await fetch(target, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      redirect: "manual",
    });
    return new Response(resp.body, resp);
  } catch {
    return Response.json(
      { detail: "No se pudo contactar el backend (¿PC apagada o tunnel caído?)." },
      { status: 502 },
    );
  }
}
