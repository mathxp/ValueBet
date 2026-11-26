"""
Resultados y fixtures de la Liga de Primera desde la API pública de ESPN.

api-football (plan gratuito) solo deja ver partidos de ayer/hoy/mañana, así
que si el pipeline se detiene unos días esos partidos quedan sin resultado
para siempre. ESPN no tiene esa restricción: con esto se rellenan los huecos
y se cargan las próximas fechas. api-football se sigue usando para cuotas.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import requests
from django.utils import timezone

from data_ingestion.equipos import Resolver
from db_models.models import Partido

logger = logging.getLogger(__name__)

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/chi.1/scoreboard"
HEADERS = {"User-Agent": "ValueBet-results/1.0 (personal, non-commercial)"}
LIGA = "Primera División"

_ESTADOS = {
    "STATUS_POSTPONED": Partido.Estado.POSPUESTO,
    "STATUS_CANCELED": Partido.Estado.CANCELADO,
    "STATUS_ABANDONED": Partido.Estado.CANCELADO,
}


def _get(fecha: str) -> dict:
    resp = requests.get(SCOREBOARD, params={"dates": fecha, "limit": 100}, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _estado(status: dict) -> str:
    tipo = status.get("type", {})
    if tipo.get("name") in _ESTADOS:
        return _ESTADOS[tipo["name"]]
    if tipo.get("state") == "post" and tipo.get("completed"):
        return Partido.Estado.FINALIZADO
    if tipo.get("state") == "in":
        return Partido.Estado.EN_VIVO
    return Partido.Estado.PROGRAMADO


def fechas_del_calendario() -> list[date]:
    """Días con partidos de la temporada actual, según ESPN."""
    data = _get(timezone.localdate().strftime("%Y%m%d"))
    calendario = (data.get("leagues") or [{}])[0].get("calendar", [])
    return sorted({datetime.fromisoformat(c.replace("Z", "+00:00")).date() for c in calendario})


def sincronizar_liga(desde: date | None = None, hasta: date | None = None) -> dict:
    """
    Crea/actualiza los Partido de la liga entre `desde` y `hasta` (incluidos).
    Por defecto: toda la temporada según el calendario de ESPN.
    """
    resolver = Resolver()
    fechas = [f for f in fechas_del_calendario() if (not desde or f >= desde) and (not hasta or f <= hasta)]
    stats = {"fechas": len(fechas), "creados": 0, "actualizados": 0, "sin_equipo": set()}

    for fecha in fechas:
        try:
            eventos = _get(fecha.strftime("%Y%m%d")).get("events", [])
        except requests.RequestException as exc:
            logger.warning("ESPN %s: %s", fecha, exc)
            continue
        for evento in eventos:
            _sincronizar_evento(evento, resolver, stats)

    stats["sin_equipo"] = sorted(stats["sin_equipo"])
    return stats


def _sincronizar_evento(evento: dict, resolver: Resolver, stats: dict) -> None:
    comp = evento["competitions"][0]
    lados = {c["homeAway"]: c for c in comp["competitors"]}
    if "home" not in lados or "away" not in lados:
        return

    equipos = {}
    for lado, c in lados.items():
        nombre = c["team"]["displayName"]
        resolver.guardar_logo(nombre, c["team"].get("logo", ""))
        equipos[lado] = resolver.equipo(nombre)
        if equipos[lado] is None:
            stats["sin_equipo"].add(nombre)
    if None in equipos.values():
        return

    temporada = str(evento.get("season", {}).get("year") or timezone.localdate().year)
    fecha_hora = datetime.fromisoformat(evento["date"].replace("Z", "+00:00"))
    estado = _estado(evento.get("status", {}))

    # Ida y vuelta: cada (local, visitante) se juega una sola vez por temporada.
    partido = (
        Partido.objects.filter(
            equipo_local=equipos["home"], equipo_visitante=equipos["away"], temporada=temporada
        )
        .order_by("-fecha_hora")
        .first()
    )
    cambios = {"fecha_hora": fecha_hora, "estado": estado}
    if estado == Partido.Estado.FINALIZADO:
        cambios["resultado"] = {
            **(partido.resultado if partido else {}),
            "local": int(lados["home"].get("score") or 0),
            "visitante": int(lados["away"].get("score") or 0),
        }

    if partido is None:
        Partido.objects.create(
            equipo_local=equipos["home"],
            equipo_visitante=equipos["away"],
            liga=LIGA,
            temporada=temporada,
            metricas_avanzadas={"espn_id": evento.get("id")},
            **cambios,
        )
        stats["creados"] += 1
        return

    if any(getattr(partido, k) != v for k, v in cambios.items()):
        for k, v in cambios.items():
            setattr(partido, k, v)
        partido.save(update_fields=[*cambios.keys(), "actualizado_en"])
        stats["actualizados"] += 1


def sincronizar_reciente() -> dict:
    """Para el pipeline horario: últimos 5 días + próximos 10."""
    hoy = timezone.localdate()
    return sincronizar_liga(desde=hoy - timedelta(days=5), hasta=hoy + timedelta(days=10))
