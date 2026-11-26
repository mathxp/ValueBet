"""
Avisos por Telegram (opcional): si TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID no
están configurados, todo esto es un no-op silencioso.

- Pronósticos muy seguros de partidos que se juegan en las próximas 30 h
  (una vez por partido, PronosticoRegistrado.notificado).
- Apuestas con valor nuevas (una vez por Operacion, metadata["notificado"]).
"""

from __future__ import annotations

import html
import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from db_models.models import Operacion, PronosticoRegistrado

logger = logging.getLogger(__name__)

UMBRAL_SEGURO = 0.75
VENTANA_HORAS = 30
SELECCION_TEXTO = {"1X": "{l} o empate", "X2": "{v} o empate", "12": "No hay empate"}


def configurado() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


def enviar(texto: str) -> bool:
    if not configurado():
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": texto,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.warning("Telegram: no se pudo enviar el aviso: %s", exc)
        return False


def _hora(dt) -> str:
    return timezone.localtime(dt).strftime("%a %d %H:%M")


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
    seguros = [c for c in candidatos if c.prob_seguro >= UMBRAL_SEGURO]
    if seguros and configurado():
        lineas = ["🔒 <b>Pronósticos más seguros (próximas 30 h)</b>", ""]
        for c in sorted(seguros, key=lambda c: c.prob_seguro, reverse=True):
            l, v = c.partido.equipo_local.nombre, c.partido.equipo_visitante.nombre
            pick = SELECCION_TEXTO.get(c.pick_seguro, c.pick_seguro).format(l=l, v=v)
            lineas.append(
                f"• <b>{html.escape(pick)}</b> — {round(c.prob_seguro * 100)}%\n"
                f"   {html.escape(l)} vs {html.escape(v)} · {html.escape(c.etiqueta_fecha)} · {_hora(c.partido.fecha_hora)}"
            )
        if not enviar("\n".join(lineas)):
            return 0
    if configurado():
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
    if not nuevas or not configurado():
        return 0
    lineas = ["💰 <b>Apuestas con valor nuevas</b>", ""]
    for op in nuevas:
        p = op.partido
        lineas.append(
            f"• {html.escape(p.equipo_local.nombre)} vs {html.escape(p.equipo_visitante.nombre)} · {_hora(p.fecha_hora)}\n"
            f"   {html.escape(op.mercado)} {html.escape(op.seleccion)} @ {op.cuota_apostada} "
            f"(prob. {round(op.probabilidad_modelo * 100)}%, stake ${op.stake})"
        )
    if not enviar("\n".join(lineas)):
        return 0
    for op in nuevas:
        op.metadata = {**(op.metadata or {}), "notificado": True}
        op.save(update_fields=["metadata", "actualizado_en"])
    return len(nuevas)
