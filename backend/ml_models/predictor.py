"""
Clase principal que carga el modelo entrenado y devuelve probabilidades.

Mientras no exista un modelo entrenado en ml_models/weights/model.joblib
(se entrena a partir de datos históricos reales en ml_models/notebooks/),
se usa un modelo base de Poisson sobre xG. Si tampoco hay xG proyectado
para un partido (equipos sin suficiente historial todavía, ver
team_ratings.py), `predecir()` retorna None explícitamente -- NO se inventa
un prior neutro. Comparar una probabilidad inventada contra una cuota real
generaría "edges" que son puro ruido, no señal, y el scanner terminaría
apostando a ciegas; es preferible abstenerse hasta tener datos reales.
"""

from __future__ import annotations

import logging
import math
from functools import lru_cache
from pathlib import Path

import joblib

from db_models.models import Partido
from ml_models.pipelines.features import FEATURE_COLUMNS, build_features

logger = logging.getLogger(__name__)

WEIGHTS_PATH = Path(__file__).resolve().parent / "weights" / "model.joblib"
MAX_GOLES_SIMULADOS = 10


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def probabilidades_1x2_por_poisson(xg_local: float, xg_visitante: float) -> dict[str, float]:
    """
    Modelo de Poisson independiente: asume goles de cada equipo ~ Poisson(xG),
    y suma la probabilidad conjunta de cada marcador posible para obtener
    P(local gana), P(empate), P(visitante gana).
    """
    xg_local = max(xg_local, 0.01)
    xg_visitante = max(xg_visitante, 0.01)

    prob_local, prob_empate, prob_visitante = 0.0, 0.0, 0.0
    for goles_local in range(MAX_GOLES_SIMULADOS + 1):
        p_local = _poisson_pmf(goles_local, xg_local)
        for goles_visitante in range(MAX_GOLES_SIMULADOS + 1):
            p_conjunta = p_local * _poisson_pmf(goles_visitante, xg_visitante)
            if goles_local > goles_visitante:
                prob_local += p_conjunta
            elif goles_local == goles_visitante:
                prob_empate += p_conjunta
            else:
                prob_visitante += p_conjunta

    return {"LOCAL": prob_local, "EMPATE": prob_empate, "VISITANTE": prob_visitante}


def distribucion_goles_totales(xg_local: float, xg_visitante: float) -> dict[int, float]:
    """P(total de goles del partido == k) para k = 0..2*MAX_GOLES_SIMULADOS."""
    xg_local = max(xg_local, 0.01)
    xg_visitante = max(xg_visitante, 0.01)

    distribucion: dict[int, float] = {}
    for goles_local in range(MAX_GOLES_SIMULADOS + 1):
        p_local = _poisson_pmf(goles_local, xg_local)
        for goles_visitante in range(MAX_GOLES_SIMULADOS + 1):
            total = goles_local + goles_visitante
            distribucion[total] = distribucion.get(total, 0.0) + p_local * _poisson_pmf(
                goles_visitante, xg_visitante
            )
    return distribucion


def probabilidad_over(distribucion: dict[int, float], linea: float) -> float:
    """P(total de goles > linea). `linea` debe ser un valor .5 (2.5, 3.5, ...) para que
    el resultado nunca empate justo en la línea (el total de goles siempre es entero)."""
    return sum(p for total, p in distribucion.items() if total > linea)


@lru_cache(maxsize=1)
def _cargar_modelo_entrenado():
    if not WEIGHTS_PATH.exists():
        return None
    try:
        return joblib.load(WEIGHTS_PATH)
    except Exception:
        logger.exception("No se pudo cargar el modelo entrenado en %s", WEIGHTS_PATH)
        return None


class MatchPredictor:
    """
    Uso:
        predictor = MatchPredictor()
        goles = predictor.predecir_goles(partido)  # (1.8, 0.9) o None si no hay datos
        probabilidades = predictor.predecir(partido)  # {"LOCAL": .., "EMPATE": .., "VISITANTE": ..} o None
    """

    def __init__(self):
        self.modelo = _cargar_modelo_entrenado()
        self._curvas_calibracion_cache: dict[str, list | None] = {}

    def predecir_goles(self, partido: Partido) -> tuple[float, float] | None:
        """xG proyectado (local, visitante). Solo existe en el camino de Poisson."""
        features = build_features(partido.metricas_avanzadas)
        if features["xg_local"] == 0.0 and features["xg_visitante"] == 0.0:
            return None
        return features["xg_local"], features["xg_visitante"]

    def predecir(self, partido: Partido) -> dict[str, float] | None:
        if self.modelo is not None:
            return self._predecir_con_modelo(partido)

        goles = self.predecir_goles(partido)
        if goles is None:
            return None
        return probabilidades_1x2_por_poisson(*goles)

    def predecir_probabilidad_1x2(self, partido: Partido, seleccion: str) -> float | None:
        """
        P(seleccion) para el mercado 1X2 (LOCAL/EMPATE/VISITANTE), corregida con
        la curva de calibración medida contra resultados reales (mismo mecanismo
        que `predecir_probabilidad_over` -- ver `_calibrar`). `predecir()` sigue
        devolviendo las 3 probabilidades crudas (sin calibrar) para el panel
        informativo de goles proyectados; esta función es la que debe usarse para
        Edge/EV/Kelly de una selección puntual, que es donde importa que la
        probabilidad esté corregida.
        """
        probabilidades = self.predecir(partido)
        if probabilidades is None:
            return None
        probabilidad_cruda = probabilidades.get(seleccion)
        if probabilidad_cruda is None:
            return None
        return self._calibrar("1X2", probabilidad_cruda)

    def predecir_probabilidad_over(self, partido: Partido, linea: float) -> float | None:
        """
        P(goles totales > linea), ej. linea=2.5 para el mercado "Más de 2.5 goles".
        Se deriva de la misma proyección de xG que predecir_goles -- no depende del
        modelo entrenado (solo del camino de Poisson), ya que el mercado 1X2 y el de
        goles totales comparten la misma distribución conjunta de marcadores.

        La probabilidad cruda se corrige con la curva de calibración medida
        contra resultados reales (ver `_calibrar` y
        `manage.py backtest_modelo --guardar-calibracion`) -- si todavía no
        hay curva para esta línea, se usa la probabilidad cruda tal cual.
        """
        goles = self.predecir_goles(partido)
        if goles is None:
            return None
        distribucion = distribucion_goles_totales(*goles)
        probabilidad_cruda = probabilidad_over(distribucion, linea)
        return self._calibrar(f"OVER_UNDER_{linea}", probabilidad_cruda)

    def _calibrar(self, mercado: str, probabilidad_cruda: float) -> float:
        from ml_models.pipelines.calibracion import aplicar_calibracion

        if mercado not in self._curvas_calibracion_cache:
            from db_models.models import CalibracionMercado

            fila = CalibracionMercado.objects.filter(mercado=mercado).first()
            self._curvas_calibracion_cache[mercado] = fila.puntos if fila else None

        return aplicar_calibracion(self._curvas_calibracion_cache[mercado], probabilidad_cruda)

    def _predecir_con_modelo(self, partido: Partido) -> dict[str, float]:
        features = build_features(partido.metricas_avanzadas)
        vector = [[features[col] for col in FEATURE_COLUMNS]]
        # El modelo entrenado debe exponer predict_proba con clases
        # ordenadas ["EMPATE", "LOCAL", "VISITANTE"] (orden alfabético de
        # LabelEncoder) -- ajustar si el pipeline de entrenamiento cambia.
        probabilidades = self.modelo.predict_proba(vector)[0]
        clases = list(self.modelo.classes_)
        return dict(zip(clases, (float(p) for p in probabilidades)))
