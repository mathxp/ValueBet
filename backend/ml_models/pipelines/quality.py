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

from ml_models.pipelines.team_ratings import K_SHRINKAGE, MAX_PARTIDOS_POR_EQUIPO

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


def calcular_value_score(ev: float | None, confidence_score: int) -> int:
    """
    0-100. Un EV alto con confianza baja da un value score moderado -- no
    alto -- porque la confianza pondera directamente. Un EV negativo o nulo
    siempre da 0 (nunca hay "valor" sin EV positivo, sin importar la confianza).
    """
    if ev is None or ev <= 0:
        return 0
    puntos_ev = min(100, round(ev * 200))  # 50% de EV ya satura el puntaje
    return round(puntos_ev * (confidence_score / 100))
