"""
Métricas de calibración: comparan las probabilidades que predijo el modelo
contra lo que realmente pasó, usando el historial de `AnalisisPartido` ya
resuelto (ver `AnalisisPartido.reconciliar`). Cálculo puro (sin acceso a
BD) para poder testear sin fixtures pesados -- el llamador arma los pares
(probabilidad, ocurrió) a partir del queryset que corresponda.

Nunca inventa un número si no hay suficientes casos resueltos -- ver
MIN_MUESTRA_CALIBRACION, mismo criterio que
AnalisisPartidoViewSet.rendimiento().
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

MIN_MUESTRA_CALIBRACION = 20
N_BUCKETS_CALIBRACION = 5  # buckets de 20 puntos porcentuales -- deciles serían ideales pero exigen mucha más muestra

# Un bucket con pocos casos no es evidencia confiable de nada -- se excluye
# de la curva de calibración en vez de dejar que un punto ruidoso (ej. n=1,
# frecuencia_real=0%) distorsione la interpolación.
MIN_N_POR_PUNTO_CALIBRACION = 10


@dataclass
class BucketCalibracion:
    rango: str
    n: int
    prob_promedio: float | None
    frecuencia_real: float | None


@dataclass
class ReporteCalibracion:
    mercado: str
    n: int
    datos_suficientes: bool
    brier_score: float | None = None
    log_loss: float | None = None
    buckets: list[BucketCalibracion] = field(default_factory=list)


def calcular_brier_score(pares: list[tuple[float, int]]) -> float:
    """Brier score binario: promedio de (probabilidad - resultado)^2. 0 es perfecto, 0.25 es "no mejor que decir 50/50"."""
    return sum((p - y) ** 2 for p, y in pares) / len(pares)


def calcular_log_loss(pares: list[tuple[float, int]], epsilon: float = 1e-9) -> float:
    """Log loss binario, con las probabilidades recortadas a [epsilon, 1-epsilon] para que log(0) no explote."""
    total = 0.0
    for p, y in pares:
        p_recortada = min(max(p, epsilon), 1 - epsilon)
        total += -(y * math.log(p_recortada) + (1 - y) * math.log(1 - p_recortada))
    return total / len(pares)


def calcular_buckets(pares: list[tuple[float, int]], n_buckets: int = N_BUCKETS_CALIBRACION) -> list[BucketCalibracion]:
    """
    Reliability diagram en forma de tabla: agrupa las predicciones en
    `n_buckets` rangos de probabilidad y compara, dentro de cada rango, la
    probabilidad promedio que dijo el modelo contra la frecuencia real con
    la que ocurrió -- si el modelo está bien calibrado, ambas columnas
    deberían parecerse.
    """
    ancho = 1.0 / n_buckets
    buckets = []
    for i in range(n_buckets):
        lo, hi = i * ancho, (i + 1) * ancho
        es_ultimo = i == n_buckets - 1
        en_rango = [(p, y) for p, y in pares if (lo <= p < hi) or (es_ultimo and p == 1.0)]

        if not en_rango:
            buckets.append(BucketCalibracion(rango=f"{lo * 100:.0f}-{hi * 100:.0f}%", n=0, prob_promedio=None, frecuencia_real=None))
            continue

        prob_promedio = sum(p for p, _ in en_rango) / len(en_rango)
        frecuencia_real = sum(y for _, y in en_rango) / len(en_rango)
        buckets.append(
            BucketCalibracion(
                rango=f"{lo * 100:.0f}-{hi * 100:.0f}%",
                n=len(en_rango),
                prob_promedio=round(prob_promedio, 3),
                frecuencia_real=round(frecuencia_real, 3),
            )
        )
    return buckets


def calcular_reporte(mercado: str, pares: list[tuple[float, int]]) -> ReporteCalibracion:
    n = len(pares)
    if n < MIN_MUESTRA_CALIBRACION:
        return ReporteCalibracion(mercado=mercado, n=n, datos_suficientes=False)

    return ReporteCalibracion(
        mercado=mercado,
        n=n,
        datos_suficientes=True,
        brier_score=round(calcular_brier_score(pares), 4),
        log_loss=round(calcular_log_loss(pares), 4),
        buckets=calcular_buckets(pares),
    )


def construir_curva_calibracion(
    pares: list[tuple[float, int]], n_buckets: int = N_BUCKETS_CALIBRACION, min_n: int = MIN_N_POR_PUNTO_CALIBRACION
) -> list[tuple[float, float]] | None:
    """
    Curva de calibración: un punto (probabilidad predicha promedio,
    frecuencia real) por cada bucket con muestra suficiente. None si hay
    menos de dos puntos confiables -- no alcanza para interpolar nada, y
    `aplicar_calibracion` debe usar la probabilidad cruda sin tocar en ese
    caso (nunca se inventa una corrección sin evidencia real detrás).
    """
    buckets = calcular_buckets(pares, n_buckets)
    puntos = [(b.prob_promedio, b.frecuencia_real) for b in buckets if b.n >= min_n]
    return puntos if len(puntos) >= 2 else None


def aplicar_calibracion(puntos: list[tuple[float, float]] | None, probabilidad_cruda: float) -> float:
    """
    Corrige `probabilidad_cruda` interpolando linealmente entre los puntos
    (predicho, real) medidos por `construir_curva_calibracion` -- fuera del
    rango observado, extrapola con el tramo más cercano a los extremos
    (recortado a [0, 1]). Si `puntos` es None (sin curva para ese mercado
    todavía), retorna la probabilidad cruda sin modificar.
    """
    if not puntos:
        return probabilidad_cruda

    puntos_ordenados = sorted(puntos)
    if len(puntos_ordenados) == 1:
        return min(max(puntos_ordenados[0][1], 0.0), 1.0)

    if probabilidad_cruda <= puntos_ordenados[0][0]:
        (x0, y0), (x1, y1) = puntos_ordenados[0], puntos_ordenados[1]
    elif probabilidad_cruda >= puntos_ordenados[-1][0]:
        (x0, y0), (x1, y1) = puntos_ordenados[-2], puntos_ordenados[-1]
    else:
        x0 = y0 = x1 = y1 = None
        for (xa, ya), (xb, yb) in zip(puntos_ordenados, puntos_ordenados[1:]):
            if xa <= probabilidad_cruda <= xb:
                x0, y0, x1, y1 = xa, ya, xb, yb
                break

    if x1 == x0:
        return min(max(y0, 0.0), 1.0)

    pendiente = (y1 - y0) / (x1 - x0)
    resultado = y0 + pendiente * (probabilidad_cruda - x0)
    return min(max(resultado, 0.0), 1.0)


def pares_desde_analisis(queryset) -> list[tuple[float, int]]:
    """
    Arma los pares (probabilidad, ocurrió) desde un queryset de
    AnalisisPartido ya resuelto -- probabilidad_seleccion es la probabilidad
    que el modelo le dio a la selección evaluada, prediccion_acertada si
    esa selección terminó ocurriendo.
    """
    return [
        (fila.probabilidad_seleccion, int(fila.prediccion_acertada))
        for fila in queryset
        if fila.probabilidad_seleccion is not None and fila.prediccion_acertada is not None
    ]
