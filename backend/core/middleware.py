"""Protección del backend cuando se expone por Cloudflare Tunnel.

Todo request que pasa por la red de Cloudflare trae el header ``Cf-Ray``.
Esos requests solo se aceptan si además traen ``X-Proxy-Secret`` igual a
``settings.PROXY_SECRET``, que únicamente conoce la Pages Function
(frontend/functions/api/[[path]].js). Así la URL del tunnel no sirve para
entrar directo a la API.

El acceso local / por la red de la casa (sin Cf-Ray) no cambia.
"""

import hmac

from django.conf import settings
from django.http import JsonResponse


class CloudflareProxySecretMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if "HTTP_CF_RAY" in request.META:
            expected = settings.PROXY_SECRET
            received = request.META.get("HTTP_X_PROXY_SECRET", "")
            if not expected or not hmac.compare_digest(received, expected):
                return JsonResponse({"detail": "Forbidden"}, status=403)
        return self.get_response(request)
