"""
Estadísticas complementarias de equipo desde FotMob (vía la librería
LanusStats: https://github.com/federicorabanos/LanusStats, MIT).

IMPORTANTE -- alcance deliberadamente acotado:
Se evaluó traer xG real desde FBref/FotMob para reemplazar el proxy_xg
actual (ver ml_models/pipelines/team_ratings.py), pero ninguna de las dos
fuentes calcula un modelo de xG para la Primera División de Chile (se
verificó contra las respuestas en vivo de ambas APIs, no solo la
documentación): FBref solo expone conteo de tiros/goles en esta liga, y el
catálogo de estadísticas que FotMob realmente tiene pobladas para esta liga
(ver la respuesta de `leagueseasondeepstats`) no incluye
`expected_goals_team` pese a que la librería lo ofrezca como parámetro
válido en general.

Por eso estos datos se guardan como CONTEXTO INFORMATIVO en
`Equipo.metadata["fotmob"]` (se muestran en la pestaña Equipos) y
deliberadamente NO se mezclan en calcular_ratings() / proyectar_xg(): son
promedios de temporada sin calibrar contra resultados reales de esta liga,
y el resto del modelo pasó por un proceso explícito de auditoría y
calibración (ver ml_models/pipelines/calibracion.py) antes de influir en
una recomendación. Si en el futuro se quiere usar esto para ajustar
ratings, debería pasar por el mismo proceso de backtesting.

Requiere el paquete opcional `lanusstats` (ver requirements-scraping.txt) --
lanza un Chrome real (vía `nodriver`) para esquivar el anti-bot de FotMob,
así que es más lento y menos confiable que una API REST normal. No se llama
desde la tarea automática por hora (run_pipeline_once): se corre a mano,
ocasionalmente, con `manage.py actualizar_stats_fotmob`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from db_models.models import Equipo

logger = logging.getLogger(__name__)

LIGA_FOTMOB = "Primera Division Chile"

# Estadísticas de equipo que sí están pobladas para esta liga en FotMob
# (confirmado contra la respuesta real de la API, no solo la lista genérica
# de parámetros posibles que ofrece LanusStats).
STATS_A_TRAER = [
    "possession_percentage_team",
    "big_chance_team",
    "big_chance_missed_team",
    "ontarget_scoring_att_team",
    "corner_taken_team",
]

# FotMob usa nombres de equipo distintos a los nuestros (ver Equipo.nombre,
# cargados originalmente desde api-football) -- mapeo armado a mano contra
# la plantilla real de 16 equipos de la temporada vigente.
FOTMOB_A_EQUIPO = {
    "Colo Colo": "Colo Colo",
    "Palestino": "Palestino",
    "Universidad de Chile": "Universidad de Chile",
    "Universidad Catolica": "U. Catolica",
    "O'Higgins": "O'Higgins",
    "Ñublense": "Nublense",
    "Union Espanola": "Unión Española",
    "Union La Calera": "Union La Calera",
    "Huachipato": "Huachipato",
    "Everton CD": "Everton de Vina",
    "La Serena": "D. La Serena",
    "Cobresal": "Cobresal",
    "Deportes Iquique": "Deportes Iquique",
    "Deportes Limache": "Deportes Limache",
    "Audax Italiano": "A. Italiano",
    "Coquimbo Unido": "Coquimbo Unido",
}


def _fila_a_pares(df) -> list[tuple[str, float]]:
    """
    Extrae (nombre_equipo_fotmob, valor) de un DataFrame de
    `FotMob.get_teams_stats_season()`. La columna de nombre de equipo está
    duplicada en esa librería (aparece dos veces: una vez el nombre del
    equipo y otra vez, con la misma etiqueta 'name', el nombre de la
    estadística dentro del dict aplanado) -- por eso se accede por posición
    (columna índice 2) en vez de por nombre.
    """
    nombres = df.iloc[:, 2]
    valores = df["value"]
    return list(zip(nombres, valores))


def obtener_stats_temporada(temporada: str) -> dict[str, dict[str, float]]:
    """
    Trae las estadísticas de STATS_A_TRAER para todos los equipos de la
    liga en la temporada dada. Devuelve {nombre_equipo_interno: {stat: valor}}.

    Los equipos de FotMob que no están en FOTMOB_A_EQUIPO se ignoran con un
    warning (típicamente equipos que no juegan la temporada vigente y no
    tenemos motivo para mapear).
    """
    import LanusStats as ls

    fotmob = ls.FotMob()
    resultado: dict[str, dict[str, float]] = {}

    for stat in STATS_A_TRAER:
        df = fotmob.get_teams_stats_season(LIGA_FOTMOB, temporada, stat)
        for nombre_fotmob, valor in _fila_a_pares(df):
            nombre_interno = FOTMOB_A_EQUIPO.get(nombre_fotmob)
            if not nombre_interno:
                logger.warning("fotmob_stats: equipo sin mapear, se ignora: %s", nombre_fotmob)
                continue
            resultado.setdefault(nombre_interno, {})[stat] = valor

    return resultado


def actualizar_metadata_equipos(temporada: str) -> int:
    """
    Guarda las estadísticas en `Equipo.metadata["fotmob"]`. Retorna la
    cantidad de equipos actualizados.
    """
    stats_por_equipo = obtener_stats_temporada(temporada)

    actualizados = 0
    for equipo in Equipo.objects.filter(nombre__in=stats_por_equipo.keys()):
        equipo.metadata["fotmob"] = {
            "temporada": temporada,
            "actualizado_en": datetime.now(timezone.utc).isoformat(),
            **stats_por_equipo[equipo.nombre],
        }
        equipo.save(update_fields=["metadata"])
        actualizados += 1

    return actualizados
