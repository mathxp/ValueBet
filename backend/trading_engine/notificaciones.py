"""
Notificaciones automáticas de la app: se guardan en `Notificacion` (centro de
notificaciones con campana en el frontend) y además se envían como push
(Web Push / VAPID) a cada dispositivo que las activó.

Las genera el pipeline horario:
- Pronósticos muy seguros de partidos de las próximas 30 h (una vez por partido).
- Apuestas con valor nuevas (una vez por Operacion).
- Resultado de cada fecha cuando terminan todos sus partidos.

Las claves VAPID se generan solas la primera vez y quedan en la base
(`ClaveVapid`), así no hay que configurar nada en Render.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import timedelta

from django.utils import timezone

from db_models.models import ClaveVapid, Notificacion, Operacion, PronosticoRegistrado, SuscripcionPush

logger = logging.getLogger(__name__)

UMBRAL_SEGURO = 0.75
VENTANA_HORAS = 30
VAPID_SUB = "https://valuebetx.pages.dev"
SELECCION_TEXTO = {"1X": "{l} o empate", "X2": "{v} o empate", "12": "No hay empate"}


# ------------------------------------------------------------------ claves VAPID
def claves_vapid() -> ClaveVapid:
    clave = ClaveVapid.objects.first()
    if clave:
        return clave
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid01

    v = Vapid01()
    v.generate_keys()
    privada = v.private_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    publica_bytes = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    publica = base64.urlsafe_b64encode(publica_bytes).rstrip(b"=").decode()
    return ClaveVapid.objects.create(publica=publica, privada=privada)


# ------------------------------------------------------------------ envío
def enviar_push(notif: Notificacion) -> int:
    """Envía la notificación a todos los dispositivos suscritos; borra los que ya no existen."""
    suscripciones = list(SuscripcionPush.objects.all())
    if not suscripciones:
        return 0
    from py_vapid import Vapid01
    from pywebpush import WebPushException, webpush

    vapid = Vapid01.from_pem(claves_vapid().privada.encode())
    datos = json.dumps({"titulo": notif.titulo, "cuerpo": notif.cuerpo, "url": notif.url, "tag": notif.clave})
    enviados = 0
    for s in suscripciones:
        try:
            webpush(
                subscription_info={"endpoint": s.endpoint, "keys": {"p256dh": s.p256dh, "auth": s.auth}},
                data=datos,
                vapid_private_key=vapid,
                vapid_claims={"sub": VAPID_SUB},
                ttl=6 * 3600,
            )
            enviados += 1
        except WebPushException as exc:
            estado = getattr(exc.response, "status_code", None)
            if estado in (404, 410):  # el navegador revocó la suscripción
                s.delete()
            else:
                logger.warning("Push falló (%s): %s", estado, exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Push falló: %s", exc)
    return enviados


def notificar(clave: str, tipo: str, titulo: str, cuerpo: str = "", url: str = "/") -> Notificacion | None:
    """Crea la notificación (si no existía con esa clave) y la envía por push."""
    notif, creada = Notificacion.objects.get_or_create(
        clave=clave[:120], defaults={"tipo": tipo, "titulo": titulo[:150], "cuerpo": cuerpo, "url": url}
    )
    if not creada:
        return None
    enviar_push(notif)
    return notif


# ------------------------------------------------------------------ disparadores
def _texto_pick(reg: PronosticoRegistrado) -> str:
    l, v = reg.partido.equipo_local.nombre, reg.partido.equipo_visitante.nombre
    return SELECCION_TEXTO.get(reg.pick_seguro, reg.pick_seguro).format(l=l, v=v)


def _hora(dt) -> str:
    return timezone.localtime(dt).strftime("%d/%m %H:%M")


def avisar_pronosticos_seguros() -> int:
    ahora = timezone.now()
    candidatos = list(
        PronosticoRegistrado.objects.filter(
            notificado=False,
            reconstruido=False,
            partido__fecha_hora__gte=ahora,
            partido__fecha_hora__lte=ahora + timedelta(hours=VENTANA_HORAS),
        ).select_related("partido__equipo_local", "partido__equipo_visitante")
    )
    seguros = sorted((c for c in candidatos if c.prob_seguro >= UMBRAL_SEGURO), key=lambda c: -c.prob_seguro)
    if seguros:
        primero = seguros[0]
        titulo = (
            f"🔒 {_texto_pick(primero)} ({round(primero.prob_seguro * 100)}%)"
            if len(seguros) == 1
            else f"🔒 {len(seguros)} pronósticos muy seguros para hoy y mañana"
        )
        cuerpo = "\n".join(
            f"{_texto_pick(c)} — {round(c.prob_seguro * 100)}% · "
            f"{c.partido.equipo_local.nombre} vs {c.partido.equipo_visitante.nombre} · {_hora(c.partido.fecha_hora)}"
            for c in seguros
        )
        notificar(
            "seguros:" + ",".join(str(c.partido_id) for c in seguros),
            Notificacion.Tipo.PRONOSTICO_SEGURO,
            titulo,
            cuerpo,
            "/",
        )
    PronosticoRegistrado.objects.filter(pk__in=[c.pk for c in candidatos]).update(notificado=True)
    return len(seguros)


def avisar_value_bets() -> int:
    nuevas = [
        op
        for op in Operacion.objects.filter(estado=Operacion.Estado.RECOMENDADA).select_related(
            "partido__equipo_local", "partido__equipo_visitante"
        )
        if not (op.metadata or {}).get("notificado")
    ]
    if not nuevas:
        return 0
    cuerpo = "\n".join(
        f"{op.partido.equipo_local.nombre} vs {op.partido.equipo_visitante.nombre}: "
        f"{op.mercado} {op.seleccion} @ {op.cuota_apostada} (prob. {round(op.probabilidad_modelo * 100)}%)"
        for op in nuevas
    )
    titulo = "💰 Nueva apuesta con valor" if len(nuevas) == 1 else f"💰 {len(nuevas)} apuestas con valor nuevas"
    notificar("vb:" + ",".join(str(op.id) for op in nuevas), Notificacion.Tipo.VALUE_BET, titulo, cuerpo, "/dashboard")
    for op in nuevas:
        op.metadata = {**(op.metadata or {}), "notificado": True}
        op.save(update_fields=["metadata", "actualizado_en"])
    return len(nuevas)


def avisar_resultados_de_fecha() -> int:
    """Cuando una fecha/ronda (con pronósticos tomados en vivo) termina completa, avisa cómo nos fue."""
    desde = timezone.now() - timedelta(days=4)
    claves = set(
        PronosticoRegistrado.objects.filter(
            reconstruido=False, acierto_1x2__isnull=False, partido__fecha_hora__gte=desde
        ).values_list("competicion", "etiqueta_fecha", "partido__temporada")
    )
    n = 0
    for competicion, etiqueta, temporada in claves:
        grupo = PronosticoRegistrado.objects.filter(
            competicion=competicion, etiqueta_fecha=etiqueta, partido__temporada=temporada
        )
        if grupo.filter(acierto_1x2__isnull=True).exists():
            continue  # todavía quedan partidos de esa fecha por jugarse
        total = grupo.count()
        seguros = grupo.filter(acierto_seguro=True).count()
        exactos = grupo.filter(acierto_1x2=True).count()
        nombre = etiqueta if competicion == "Liga de Primera" else f"{competicion} · {etiqueta}"
        if notificar(
            f"fecha:{temporada}:{competicion}:{etiqueta}",
            Notificacion.Tipo.RESULTADO_FECHA,
            f"📊 {nombre}: acertamos {seguros} de {total}",
            f"Pronóstico más seguro: {seguros}/{total} · Resultado exacto: {exactos}/{total}",
            "/",
        ):
            n += 1
    return n
