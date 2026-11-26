"""
Resultados, fixtures y cuotas desde la API pública de ESPN (gratis, sin key).

- Liga de Primera (chi.1) y Copa Chile (chi.copa_chi).
- api-football (plan gratuito) solo deja ver partidos de ayer/hoy/mañana y
  tiene 100 consultas diarias; ESPN no tiene esas restricciones, así que es la
  fuente principal de fixtures/resultados.
- Cuotas: ESPN publica las de DraftKings (1X2 y más/menos goles, apertura y
  cierre) también para partidos ya jugados, lo que da historial de cuotas
  para backtesting de rentabilidad.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

import requests
from django.utils import timezone

from data_ingestion.equipos import Resolver
from db_models.models import HistorialCuotas, Partido

logger = logging.getLogger(__name__)

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard"
HEADERS = {"User-Agent": "ValueBet-results/1.0 (personal, non-commercial)"}
ORIGEN_CUOTAS = "DraftKings (ESPN)"

LIGA_PRINCIPAL = "Primera División"
COMPETICIONES = {
    "chi.1": LIGA_PRINCIPAL,
    "chi.copa_chi": "Copa Chile",
}

_ESTADOS = {
    "STATUS_POSTPONED": Partido.Estado.POSPUESTO,
    "STATUS_CANCELED": Partido.Estado.CANCELADO,
    "STATUS_ABANDONED": Partido.Estado.CANCELADO,
}

_RONDAS = {
    "group-stage": "Fase de grupos",
    "round-of-32": "Dieciseisavos",
    "round-of-16": "Octavos de final",
    "quarterfinals": "Cuartos de final",
    "semifinals": "Semifinal",
    "final": "Final",
}
_PIERNAS = {"1st Leg": "ida", "2nd Leg": "vuelta"}


def _get(slug: str, fecha: str) -> dict:
    resp = requests.get(
        SCOREBOARD.format(slug=slug), params={"dates": fecha, "limit": 100}, headers=HEADERS, timeout=20
    )
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


def _americana_a_decimal(valor) -> Decimal | None:
    """'+285' -> 3.85 ; '-120' -> 1.833. None si no es una cuota válida."""
    try:
        v = int(str(valor).replace("+", ""))
    except (TypeError, ValueError):
        return None
    if v == 0:
        return None
    dec = 1 + (v / 100 if v > 0 else 100 / abs(v))
    return Decimal(str(round(dec, 3)))


def fechas_liga() -> list[date]:
    """Días con partidos de la temporada de liga, según el calendario de ESPN."""
    data = _get("chi.1", timezone.localdate().strftime("%Y%m%d"))
    calendario = (data.get("leagues") or [{}])[0].get("calendar", [])
    fechas = set()
    for c in calendario:
        if isinstance(c, str):
            fechas.add(datetime.fromisoformat(c.replace("Z", "+00:00")).date())
    return sorted(fechas)


def sincronizar(slug: str, fechas: list[date], resolver: Resolver | None = None) -> dict:
    resolver = resolver or Resolver()
    stats = {"fechas": len(fechas), "creados": 0, "actualizados": 0, "cuotas": 0, "sin_equipo": set()}
    for fecha in fechas:
        try:
            eventos = _get(slug, fecha.strftime("%Y%m%d")).get("events", [])
        except requests.RequestException as exc:
            logger.warning("ESPN %s %s: %s", slug, fecha, exc)
            continue
        for evento in eventos:
            _sincronizar_evento(evento, COMPETICIONES[slug], resolver, stats)
    stats["sin_equipo"] = sorted(stats["sin_equipo"])
    return stats


def sincronizar_liga(desde: date | None = None, hasta: date | None = None) -> dict:
    """Liga completa (o un rango) según el calendario de ESPN."""
    fechas = [f for f in fechas_liga() if (not desde or f >= desde) and (not hasta or f <= hasta)]
    return sincronizar("chi.1", fechas)


def sincronizar_reciente() -> dict:
    """Pipeline horario: liga (calendario, -5/+21 días) y Copa Chile (día a día, -3/+21)."""
    hoy = timezone.localdate()
    resolver = Resolver()
    liga = [f for f in fechas_liga() if hoy - timedelta(days=5) <= f <= hoy + timedelta(days=21)]
    copa = [hoy + timedelta(days=d) for d in range(-3, 22)]
    return {
        "liga": sincronizar("chi.1", liga, resolver),
        "copa_chile": sincronizar("chi.copa_chi", copa, resolver),
    }


def _ronda(evento: dict, comp: dict, liga: str) -> str:
    if liga == LIGA_PRINCIPAL:
        return ""
    slug = (evento.get("season") or {}).get("slug", "")
    ronda = _RONDAS.get(slug, slug.replace("-", " ").capitalize())
    pierna = {1: "ida", 2: "vuelta"}.get((comp.get("leg") or {}).get("value"))
    if pierna is None:
        pierna = next(
            (v for n in comp.get("notes", []) for k, v in _PIERNAS.items() if (n.get("headline") or "").startswith(k)),
            None,
        )
    return f"{ronda} · {pierna}" if pierna else ronda


def _buscar_partido(evento_id: str, local, visita, liga: str, temporada: str, fecha_hora: datetime):
    partido = Partido.objects.filter(metricas_avanzadas__espn_id=evento_id).first()
    if partido:
        return partido
    qs = Partido.objects.filter(equipo_local=local, equipo_visitante=visita, liga=liga, temporada=temporada)
    if liga == LIGA_PRINCIPAL:
        # Ida y vuelta: cada (local, visitante) se juega una sola vez por temporada de liga.
        return qs.order_by("-fecha_hora").first()
    # Copas: el mismo cruce puede repetirse (grupos + eliminatoria) -> por cercanía de fecha.
    return qs.filter(
        fecha_hora__range=(fecha_hora - timedelta(days=4), fecha_hora + timedelta(days=4))
    ).first()


def _sincronizar_evento(evento: dict, liga: str, resolver: Resolver, stats: dict) -> None:
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
    evento_id = str(evento.get("id"))

    partido = _buscar_partido(evento_id, equipos["home"], equipos["away"], liga, temporada, fecha_hora)
    cambios = {"fecha_hora": fecha_hora, "estado": estado}
    if estado == Partido.Estado.FINALIZADO:
        cambios["resultado"] = {
            **(partido.resultado if partido else {}),
            "local": int(lados["home"].get("score") or 0),
            "visitante": int(lados["away"].get("score") or 0),
        }
    metricas_extra = {"espn_id": evento_id}
    ronda = _ronda(evento, comp, liga)
    if ronda:
        metricas_extra["ronda"] = ronda

    if partido is None:
        partido = Partido.objects.create(
            equipo_local=equipos["home"],
            equipo_visitante=equipos["away"],
            liga=liga,
            temporada=temporada,
            metricas_avanzadas=metricas_extra,
            **cambios,
        )
        stats["creados"] += 1
    else:
        metricas = dict(partido.metricas_avanzadas)
        cambia_metricas = any(metricas.get(k) != v for k, v in metricas_extra.items())
        if cambia_metricas or any(getattr(partido, k) != v for k, v in cambios.items()):
            for k, v in cambios.items():
                setattr(partido, k, v)
            metricas.update(metricas_extra)
            partido.metricas_avanzadas = metricas
            partido.save(update_fields=[*cambios.keys(), "metricas_avanzadas", "actualizado_en"])
            stats["actualizados"] += 1

    stats["cuotas"] += _guardar_cuotas(partido, comp)


def _guardar_cuotas(partido: Partido, comp: dict) -> int:
    """
    Guarda las cuotas de DraftKings que trae ESPN. Antes del partido se usa
    la cuota vigente ("close" = última publicada); un partido ya terminado
    solo se completa si nunca se guardó, con el registro fechado 1 h antes
    del inicio para que el backtest la trate como cuota previa al partido.
    """
    odds = (comp.get("odds") or [None])[0]
    if not odds:
        return 0

    cuotas: list[tuple[str, str, Decimal]] = []
    ml = odds.get("moneyline") or {}
    for lado, seleccion in (("home", "LOCAL"), ("draw", "EMPATE"), ("away", "VISITANTE")):
        valor = ((ml.get(lado) or {}).get("close") or {}).get("odds")
        dec = _americana_a_decimal(valor)
        if dec:
            cuotas.append(("1X2", seleccion, dec))
    linea = odds.get("overUnder")
    total = odds.get("total") or {}
    if linea is not None and float(linea) % 1 == 0.5:
        for lado, seleccion in (("over", "OVER"), ("under", "UNDER")):
            dec = _americana_a_decimal(((total.get(lado) or {}).get("close") or {}).get("odds"))
            if dec:
                cuotas.append((f"OVER_UNDER_{float(linea)}", seleccion, dec))
    if not cuotas:
        return 0

    ya_jugado = partido.estado in (Partido.Estado.FINALIZADO, Partido.Estado.EN_VIVO)
    existentes = HistorialCuotas.objects.filter(partido=partido, origen=ORIGEN_CUOTAS)
    if ya_jugado and existentes.exists():
        return 0

    nuevas = 0
    for mercado, seleccion, dec in cuotas:
        ultima = existentes.filter(mercado=mercado, seleccion=seleccion).order_by("-capturado_en").first()
        if ultima and ultima.cuota_back == dec:
            continue
        h = HistorialCuotas.objects.create(
            partido=partido, origen=ORIGEN_CUOTAS, mercado=mercado, seleccion=seleccion, cuota_back=dec
        )
        if ya_jugado:
            HistorialCuotas.objects.filter(pk=h.pk).update(capturado_en=partido.fecha_hora - timedelta(hours=1))
        nuevas += 1
    return nuevas
