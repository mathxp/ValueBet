"""
Ratings de ataque/defensa por equipo y proyección de xG para el próximo
partido -- el mismo principio que un modelo de Poisson ataque/defensa
clásico (Dixon-Coles).

La señal principal son los GOLES REALES de cada partido finalizado
(Partido.resultado), no una estimación: es la base más confiable que
tenemos, sobre todo ahora que hay un dataset histórico completo (fechas 1-21
2026, importado con `manage.py import_historical_dataset`) además de los
partidos que va completando api-football día a día. Antes de tener ese
historial usábamos un "proxy" de xG estimado a partir de tiros (dentro/fuera
del área) como aproximación; esas funciones se mantienen por si sirven para
afinar el rating con datos más finos en el futuro, pero calcular_ratings ya
no depende de ellas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from db_models.models import Partido

# Conversión promedio de tiro a gol según zona (valores de referencia de
# análisis públicos de fútbol, no medidos por nosotros). Ajustables si en el
# futuro se calibran contra resultados reales de la liga.
TASA_CONVERSION_DENTRO_AREA = 0.11
TASA_CONVERSION_FUERA_AREA = 0.03

MIN_PARTIDOS_PARA_RATING = 3
MAX_PARTIDOS_POR_EQUIPO = 15

# Shrinkage (regularización estadística, tipo James-Stein/Bayes empírico):
# sin esto, un equipo con pocos partidos y forma marcada en ambos extremos
# (ataque muy alto + rival con defensa muy mala) puede disparar la
# proyección multiplicativa a valores poco creíbles (ej. 3.9 goles
# esperados). K_SHRINKAGE es el "peso" en partidos que se le da al promedio
# de la liga -- un equipo con muchos partidos jugados se acerca a su
# promedio real; uno con pocos se acerca más al promedio de la liga.
K_SHRINKAGE = 8


def extraer_stats_equipo(stats_equipo: list[dict]) -> dict[str, float]:
    """Convierte el formato [{"type": .., "value": ..}] de api-football a un dict plano."""
    resultado = {}
    for stat in stats_equipo:
        valor = stat.get("value")
        if valor is None:
            valor = 0
        elif isinstance(valor, str) and valor.endswith("%"):
            valor = float(valor.rstrip("%"))
        resultado[stat["type"]] = valor
    return resultado


def calcular_proxy_xg_equipo(stats: dict[str, float]) -> float:
    dentro = float(stats.get("Shots insidebox", 0) or 0)
    fuera = float(stats.get("Shots outsidebox", 0) or 0)
    return round(dentro * TASA_CONVERSION_DENTRO_AREA + fuera * TASA_CONVERSION_FUERA_AREA, 3)


def calcular_proxy_xg_partido(estadisticas_api_football: list[dict]) -> dict[str, float] | None:
    """
    A partir de `metricas_avanzadas["estadisticas_api_football"]` (guardado por
    data_ingestion.tasks.fetch_match_statistics), calcula el proxy de xG de
    ambos equipos. Requiere que el partido ya haya terminado (si no, los
    tiros todavía no reflejan el partido completo).
    """
    if len(estadisticas_api_football) != 2:
        return None

    equipo_a, equipo_b = estadisticas_api_football
    return {
        str(equipo_a["team"]["id"]): calcular_proxy_xg_equipo(
            extraer_stats_equipo(equipo_a["statistics"])
        ),
        str(equipo_b["team"]["id"]): calcular_proxy_xg_equipo(
            extraer_stats_equipo(equipo_b["statistics"])
        ),
    }


@dataclass
class RatingEquipo:
    ataque: float  # goles a favor, promedio de sus últimos partidos
    defensa: float  # goles en contra, promedio de sus últimos partidos
    partidos: int
    ultimo_partido: datetime | None = None  # fecha del partido contado más reciente (Data Quality Score)


def _historial_finalizados(liga: str = "") -> list[Partido]:
    qs = Partido.objects.filter(estado=Partido.Estado.FINALIZADO).order_by("-fecha_hora")
    if liga:
        qs = qs.filter(liga=liga)
    return list(qs.select_related("equipo_local", "equipo_visitante")[:1000])


def calcular_ratings(liga: str = "") -> dict[int, RatingEquipo]:
    """Rating de ataque/defensa por equipo (api_football_id) a partir de goles reales."""
    partidos = _historial_finalizados(liga)

    por_equipo: dict[int, list[tuple[float, float]]] = {}
    ultimo_partido_por_equipo: dict[int, datetime] = {}
    for partido in partidos:
        goles_local = partido.resultado.get("local")
        goles_visitante = partido.resultado.get("visitante")
        if goles_local is None or goles_visitante is None:
            continue

        local_id = partido.equipo_local.api_football_id
        visitante_id = partido.equipo_visitante.api_football_id

        por_equipo.setdefault(local_id, [])
        por_equipo.setdefault(visitante_id, [])
        if len(por_equipo[local_id]) < MAX_PARTIDOS_POR_EQUIPO:
            por_equipo[local_id].append((goles_local, goles_visitante))
            ultimo_partido_por_equipo.setdefault(local_id, partido.fecha_hora)
        if len(por_equipo[visitante_id]) < MAX_PARTIDOS_POR_EQUIPO:
            por_equipo[visitante_id].append((goles_visitante, goles_local))
            ultimo_partido_por_equipo.setdefault(visitante_id, partido.fecha_hora)

    if not por_equipo:
        return {}

    crudos = {
        equipo_id: (
            sum(f for f, _ in partidos) / len(partidos),
            sum(c for _, c in partidos) / len(partidos),
            len(partidos),
        )
        for equipo_id, partidos in por_equipo.items()
    }
    promedio_liga_ataque = sum(ataque for ataque, _, _ in crudos.values()) / len(crudos)
    promedio_liga_defensa = sum(defensa for _, defensa, _ in crudos.values()) / len(crudos)

    ratings = {}
    for equipo_id, (ataque_crudo, defensa_cruda, n) in crudos.items():
        peso = n / (n + K_SHRINKAGE)
        ratings[equipo_id] = RatingEquipo(
            ataque=peso * ataque_crudo + (1 - peso) * promedio_liga_ataque,
            defensa=peso * defensa_cruda + (1 - peso) * promedio_liga_defensa,
            partidos=n,
            ultimo_partido=ultimo_partido_por_equipo.get(equipo_id),
        )
    return ratings


def _factor_localia(liga: str = "") -> tuple[float, float]:
    """
    Ventaja de local medida con goles reales: en esta liga, los locales
    anotan ~35% más que los visitantes (1.64 vs 1.22 goles/partido en el
    historial cargado). Los ratings de ataque/defensa mezclan local y
    visita en un solo promedio por equipo (partirlos por separado dejaría
    muy pocos partidos por equipo para que el shrinkage funcione bien), así
    que esta ventaja se aplica como un ajuste global aparte, no por equipo.

    Retorna (factor_local, factor_visita) relativos al promedio general de
    goles por equipo por partido -- factor_local > 1, factor_visita < 1.
    """
    partidos = _historial_finalizados(liga)
    goles_local = [p.resultado["local"] for p in partidos if "local" in p.resultado]
    goles_visita = [p.resultado["visitante"] for p in partidos if "visitante" in p.resultado]

    if not goles_local or not goles_visita:
        return 1.0, 1.0

    promedio_local = sum(goles_local) / len(goles_local)
    promedio_visita = sum(goles_visita) / len(goles_visita)
    promedio_general = (promedio_local + promedio_visita) / 2
    if promedio_general <= 0:
        return 1.0, 1.0

    return promedio_local / promedio_general, promedio_visita / promedio_general


def proyectar_xg(equipo_local_id: int, equipo_visitante_id: int, liga: str = "") -> tuple[float, float] | None:
    """
    Estima el xG esperado del próximo partido combinando el ataque de cada
    equipo, la defensa del rival, y la ventaja de jugar de local. Retorna
    None si a alguno de los dos le falta historial suficiente -- en ese caso
    el predictor se abstiene en vez de inventar un número.
    """
    ratings = calcular_ratings(liga)
    local = ratings.get(equipo_local_id)
    visitante = ratings.get(equipo_visitante_id)

    if not local or not visitante:
        return None
    if local.partidos < MIN_PARTIDOS_PARA_RATING or visitante.partidos < MIN_PARTIDOS_PARA_RATING:
        return None

    promedio_liga = sum(r.ataque for r in ratings.values()) / len(ratings)
    if promedio_liga <= 0:
        return None

    factor_local, factor_visita = _factor_localia(liga)

    xg_local = local.ataque * factor_local * (visitante.defensa / promedio_liga)
    xg_visitante = visitante.ataque * factor_visita * (local.defensa / promedio_liga)
    return round(xg_local, 3), round(xg_visitante, 3)
