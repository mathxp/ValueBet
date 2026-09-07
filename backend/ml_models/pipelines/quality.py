"""
Puntajes de calidad y confianza de una proyección -- fórmulas propias, no un
estándar de la industria, pensadas para ser transparentes y calculables solo
a partir de datos reales que ya tenemos (nada inventado):

- Data Quality Score: qué tan buena es la base de datos detrás del rating de
  cada equipo (cantidad de partidos, qué tan reciente es su último partido
  contado).
- Confidence Score: qué tan confiable es el análisis en sí -- no es "qué tan
  probable es que gane", es "qué tanto peso real (no shrinkage hacia el
  promedio de liga) hay detrás del número".
- Value Score: combina el valor esperado (EV) con la confianza, para
  distinguir "edge alto + confianza alta" (oportunidad fuerte) de "edge alto
  + confianza baja" (arriesgado, candidato a NO BET).
"""

from __future__ import annotations

from datetime import datetime

from django.utils import timezone

from ml_models.pipelines.team_ratings import K_SHRINKAGE, MAX_PARTIDOS_POR_EQUIPO, MIN_PARTIDOS_PARA_RATING
from trading_engine.risk_manager import EDGE_MAXIMO_CONFIABLE

# Umbrales por debajo de los cuales el sistema prefiere NO BET aunque haya edge.
MIN_DATA_QUALITY_SCORE = 40
MIN_CONFIDENCE_SCORE = 35


def peso_shrinkage(partidos: int) -> float:
    """Qué tan poco se apoya el rating en el promedio de liga (0 a 1). Mismo
    peso que usa calcular_ratings() internamente -- reexpuesto acá para no
    duplicar la fórmula."""
    return partidos / (partidos + K_SHRINKAGE)


def calcular_data_quality_score(
    partidos_local: int,
    partidos_visitante: int,
    ultimo_partido_local: datetime | None,
    ultimo_partido_visitante: datetime | None,
) -> int:
    """
    0-100. Dos componentes:
    - Cantidad de partidos disponibles (hasta 70 puntos): escala contra
      MAX_PARTIDOS_POR_EQUIPO, usando el equipo con MENOS historial de los dos
      (la cadena es tan fuerte como su eslabón más débil).
    - Antigüedad de los datos (hasta 30 puntos): penaliza si algún equipo
      lleva mucho tiempo sin jugar un partido contado en su rating.
    """
    partidos_minimos = min(partidos_local, partidos_visitante)
    puntos_cantidad = round(70 * min(partidos_minimos / MAX_PARTIDOS_POR_EQUIPO, 1.0))

    ahora = timezone.now()
    fechas = [f for f in (ultimo_partido_local, ultimo_partido_visitante) if f is not None]
    if not fechas:
        puntos_recencia = 0
    else:
        dias_max = max((ahora - f).days for f in fechas)
        puntos_recencia = 30 if dias_max <= 14 else max(0, 30 - (dias_max - 14))

    return min(100, puntos_cantidad + puntos_recencia)


def calcular_confidence_score(data_quality_score: int, partidos_local: int, partidos_visitante: int) -> int:
    """
    0-100. Parte del Data Quality Score y lo ajusta hacia abajo si el rating
    de alguno de los dos equipos todavía se apoya mucho en el promedio de
    liga (shrinkage) en vez de en su propio historial real.
    """
    peso_promedio = (peso_shrinkage(partidos_local) + peso_shrinkage(partidos_visitante)) / 2
    return round(data_quality_score * (0.5 + 0.5 * peso_promedio))


def calcular_value_score(
    ev: float | None,
    data_quality_score: int,
    confidence_score: int,
    calibrado: bool,
    partidos_local: int,
    partidos_visitante: int,
    es_anomalia: bool = False,
) -> int:
    """
    0-100, ponderado por seis componentes -- ninguno inventado, todos
    derivados de números que el sistema ya calcula en otro lado:

    - EV (30 pts): tamaño de la oportunidad. Se usa el EV proporcional
      (no el edge en puntos porcentuales) porque es lo mismo que ya
      compara `EDGE_MAXIMO_CONFIABLE` -- saturado en ese mismo techo, así
      que un EV "al límite de lo creíble" ya se lleva los 30 puntos.
    - Calibración (25 pts): 25 si el mercado tiene curva de calibración
      medida contra resultados reales (`CalibracionMercado`), 0 si no --
      binario a propósito, no hay forma de medir "cuánta" calibración sin
      inventar una escala.
    - Calidad de datos (15) y Confianza (15): proporcional directo a
      `data_quality_score`/`confidence_score` (0-100 cada uno).
    - Estabilidad (10 pts): qué tan lejos está el equipo con MENOS
      historial de los dos del doble del mínimo requerido
      (`MIN_PARTIDOS_PARA_RATING`) -- un rating con apenas el mínimo
      todavía puede moverse mucho con el próximo partido; con el doble,
      ya es bastante más estable.
    - Anomalías (5 pts): 0 si `es_anomalia` (edge extremo o mercado sin
      validar, ver trading_engine/scanner.py), 5 si no.

    Un EV negativo, nulo, o marcado como anomalía siempre da 0 -- nunca hay
    "valor" ahí, sin importar qué tan bien se vean los demás componentes.
    """
    if es_anomalia or ev is None or ev <= 0:
        return 0

    puntos_ev = min(30, round(ev * 30 / EDGE_MAXIMO_CONFIABLE))
    puntos_calibracion = 25 if calibrado else 0
    puntos_calidad = round(data_quality_score * 15 / 100)
    puntos_confianza = round(confidence_score * 15 / 100)

    partidos_minimos = min(partidos_local, partidos_visitante)
    puntos_estabilidad = round(10 * min(partidos_minimos / (2 * MIN_PARTIDOS_PARA_RATING), 1.0))

    puntos_anomalias = 5

    return puntos_ev + puntos_calibracion + puntos_calidad + puntos_confianza + puntos_estabilidad + puntos_anomalias
