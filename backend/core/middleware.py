"""Exige un secreto compartido para que solo la Pages Function de Cloudflare
(frontend/functions/api/[[path]].js) pueda usar la API.

- En producción (Render) ``PROXY_SECRET_REQUIRED=True``: todo request debe
  traer ``X-Proxy-Secret`` igual a ``settings.PROXY_SECRET``, salvo /healthz.
- En local, solo se exige si el request pasó por Cloudflare (header ``Cf-Ray``,
  p. ej. vía Cloudflare Tunnel); el acceso directo / red de la casa no cambia.
"""

import hmac

from django.conf import settings
from django.http import HttpResponse, JsonResponse

HEALTH_PATH = "/healthz"


class CloudflareProxySecretMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == HEALTH_PATH:
            return HttpResponse("ok", content_type="text/plain")

        if settings.PROXY_SECRET_REQUIRED or "HTTP_CF_RAY" in request.META:
            expected = settings.PROXY_SECRET
            received = request.META.get("HTTP_X_PROXY_SECRET", "")
            if not expected or not hmac.compare_digest(received, expected):
                return JsonResponse({"detail": "Forbidden"}, status=403)
        return self.get_response(request)
