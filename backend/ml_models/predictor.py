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


def matriz_marcadores(xg_local: float, xg_visitante: float, rho: float = 0.0) -> list[list[float]]:
    """
    P(marcador = i-j) para i, j = 0..MAX_GOLES_SIMULADOS: Poisson
    independiente con la corrección de Dixon-Coles para los marcadores bajos
    (rho, ver ml_models/pipelines/team_ratings.py), renormalizada para sumar 1.
    """
    xg_local = max(xg_local, 0.01)
    xg_visitante = max(xg_visitante, 0.01)
    pl = [_poisson_pmf(k, xg_local) for k in range(MAX_GOLES_SIMULADOS + 1)]
    pv = [_poisson_pmf(k, xg_visitante) for k in range(MAX_GOLES_SIMULADOS + 1)]
    m = [[pl[i] * pv[j] for j in range(MAX_GOLES_SIMULADOS + 1)] for i in range(MAX_GOLES_SIMULADOS + 1)]
    if rho:
        m[0][0] *= max(1 - xg_local * xg_visitante * rho, 0.0)
        m[0][1] *= max(1 + xg_local * rho, 0.0)
        m[1][0] *= max(1 + xg_visitante * rho, 0.0)
        m[1][1] *= max(1 - rho, 0.0)
    total = sum(map(sum, m))
    return [[x / total for x in fila] for fila in m]


def probabilidades_1x2_por_poisson(xg_local: float, xg_visitante: float, rho: float = 0.0) -> dict[str, float]:
    """
    P(local gana), P(empate), P(visitante gana) sumando la probabilidad de
    cada marcador posible (Poisson + corrección Dixon-Coles si rho != 0).
    """
    m = matriz_marcadores(xg_local, xg_visitante, rho)
    n = len(m)
    local = sum(m[i][j] for i in range(n) for j in range(n) if i > j)
    empate = sum(m[i][i] for i in range(n))
    return {"LOCAL": local, "EMPATE": empate, "VISITANTE": max(1.0 - local - empate, 0.0)}


def distribucion_goles_totales(xg_local: float, xg_visitante: float, rho: float = 0.0) -> dict[int, float]:
    """P(total de goles del partido == k) para k = 0..2*MAX_GOLES_SIMULADOS."""
    m = matriz_marcadores(xg_local, xg_visitante, rho)
    distribucion: dict[int, float] = {}
    for i, fila in enumerate(m):
        for j, p in enumerate(fila):
            distribucion[i + j] = distribucion.get(i + j, 0.0) + p
    return distribucion


SIMULACIONES_POR_PARTIDO = 10_000


def simular_partido(xg_local: float, xg_visitante: float, rho: float = 0.0, n: int = SIMULACIONES_POR_PARTIDO, semilla: int = 0) -> dict:
    """
    Monte Carlo: juega el partido `n` veces muestreando marcadores de la
    distribución del modelo y cuenta lo que pasó. Con 10.000 simulaciones el
    error de muestreo es < 1 punto porcentual; la semilla fija (id del
    partido) hace que el resultado no cambie entre recargas de la página.
    """
    import numpy as np

    m = np.array(matriz_marcadores(xg_local, xg_visitante, rho))
    tam = m.shape[0]
    rng = np.random.default_rng(semilla)
    muestras = rng.choice(tam * tam, size=n, p=m.ravel() / m.sum())
    gl, gv = np.divmod(muestras, tam)

    conteo_marcadores: dict[tuple[int, int], int] = {}
    for a, b in zip(gl.tolist(), gv.tolist()):
        conteo_marcadores[(a, b)] = conteo_marcadores.get((a, b), 0) + 1
    top = sorted(conteo_marcadores.items(), key=lambda kv: kv[1], reverse=True)[:6]
    total = gl + gv
    return {
        "simulaciones": n,
        "victorias_local": int(np.sum(gl > gv)),
        "empates": int(np.sum(gl == gv)),
        "victorias_visitante": int(np.sum(gl < gv)),
        "ambos_anotan": int(np.sum((gl > 0) & (gv > 0))),
        "mas_de_1_5": int(np.sum(total > 1.5)),
        "mas_de_2_5": int(np.sum(total > 2.5)),
        "mas_de_3_5": int(np.sum(total > 3.5)),
        "goles_promedio_local": round(float(gl.mean()), 2),
        "goles_promedio_visitante": round(float(gv.mean()), 2),
        "marcadores_frecuentes": [{"local": a, "visitante": b, "veces": c} for (a, b), c in top],
    }


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
        return probabilidades_1x2_por_poisson(*goles, rho=partido.metricas_avanzadas.get("dc_rho", 0.0))

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

    # Peso del modelo al mezclarlo con la probabilidad implícita del mercado.
    # Con las cuotas guardadas (17 partidos resueltos) modelo y mercado rindieron
    # parecido (Brier 0.596 vs 0.619, mismo % de acierto), así que se usa la
    # mezcla equitativa: es la opción más robusta cuando ninguna fuente domina.
    PESO_MODELO_VS_MERCADO = 0.5

    def probabilidades_1x2_mercado(self, partido: Partido) -> dict[str, float] | None:
        """Probabilidad implícita 1X2 de las últimas cuotas capturadas, sin margen de la casa."""
        from db_models.models import HistorialCuotas

        cuotas = {}
        for seleccion in ("LOCAL", "EMPATE", "VISITANTE"):
            fila = (
                HistorialCuotas.objects.filter(partido=partido, mercado="1X2", seleccion=seleccion)
                .order_by("-capturado_en")
                .values_list("cuota_back", flat=True)
                .first()
            )
            if not fila or fila <= 1:
                return None
            cuotas[seleccion] = 1 / float(fila)
        total = sum(cuotas.values())
        return {s: v / total for s, v in cuotas.items()}

    def probabilidades_1x2_combinadas(self, partido: Partido) -> tuple[dict[str, float], bool] | None:
        """
        1X2 calibrado del modelo, mezclado con el mercado cuando hay cuotas.
        Retorna (probabilidades que suman 1, usó_mercado).
        """
        modelo = {s: self.predecir_probabilidad_1x2(partido, s) for s in ("LOCAL", "EMPATE", "VISITANTE")}
        if None in modelo.values():
            return None
        total = sum(modelo.values()) or 1.0
        modelo = {s: p / total for s, p in modelo.items()}

        mercado = self.probabilidades_1x2_mercado(partido)
        if mercado is None:
            return modelo, False
        w = self.PESO_MODELO_VS_MERCADO
        return {s: w * modelo[s] + (1 - w) * mercado[s] for s in modelo}, True

    # Cada selección de Doble Oportunidad es la suma de dos resultados del
    # 1X2 mutuamente excluyentes -- por definición, no hace falta (ni tiene
    # sentido) estimarla por separado.
    _DOBLE_OPORTUNIDAD_A = {"1X": "LOCAL", "12": "LOCAL", "X2": "EMPATE"}
    _DOBLE_OPORTUNIDAD_B = {"1X": "EMPATE", "12": "VISITANTE", "X2": "VISITANTE"}

    def predecir_probabilidad_doble_oportunidad(self, partido: Partido, seleccion: str) -> float | None:
        """
        P(seleccion) para Doble Oportunidad ("1X"=Local o Empate, "12"=Local o
        Visitante, "X2"=Empate o Visitante) -- se deriva sumando las dos
        probabilidades de 1X2 ya calibradas que la componen, en vez de pedirle
        una curva de calibración propia a este mercado. Es matemáticamente
        exacto (son resultados mutuamente excluyentes) y hereda la validación
        real que ya tiene 1X2, sin tener que backtestear un mercado nuevo
        desde cero antes de poder usarlo -- ver trading_engine/scanner.py
        sobre cómo esto se trata como "calibrado" igual que 1X2.
        """
        resultado_a = self._DOBLE_OPORTUNIDAD_A.get(seleccion)
        resultado_b = self._DOBLE_OPORTUNIDAD_B.get(seleccion)
        if resultado_a is None or resultado_b is None:
            return None

        prob_a = self.predecir_probabilidad_1x2(partido, resultado_a)
        prob_b = self.predecir_probabilidad_1x2(partido, resultado_b)
        if prob_a is None or prob_b is None:
            return None
        return prob_a + prob_b

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
        distribucion = distribucion_goles_totales(*goles, rho=partido.metricas_avanzadas.get("dc_rho", 0.0))
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
