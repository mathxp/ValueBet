"""
Gestión de riesgo: Criterio de Kelly fraccional.

El Kelly completo maximiza el crecimiento logarítmico del bankroll a largo
plazo, pero asume que la probabilidad estimada por el modelo es exacta. Como
nuestro modelo de ML nunca lo es (ver 2.2 Overfitting en prompt.md), apostamos
solo una fracción del Kelly completo (por defecto 25%, "quarter Kelly") para
reducir la varianza y sobrevivir a rachas negativas causadas por el propio
error del modelo.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings


@dataclass
class ValueBetEvaluation:
    probabilidad_modelo: float
    cuota_decimal: float
    valor_esperado: float  # edge: (prob * cuota) - 1
    kelly_completo: float
    kelly_fraccion_usada: float
    stake_sugerido: Decimal
    es_apuesta_de_valor: bool


def calcular_valor_esperado(probabilidad_modelo: float, cuota_decimal: float) -> float:
    """Edge esperado por unidad apostada: (p * cuota) - 1."""
    return (probabilidad_modelo * cuota_decimal) - 1


def calcular_kelly_completo(probabilidad_modelo: float, cuota_decimal: float) -> float:
    """
    f* = (b*p - q) / b
    donde b = cuota_decimal - 1 (ganancia neta por unidad), p = prob. de ganar,
    q = 1 - p. Retorna 0 si no hay edge positivo (nunca apostar en contra del modelo).
    """
    if cuota_decimal <= 1:
        return 0.0

    b = cuota_decimal - 1
    p = probabilidad_modelo
    q = 1 - p

    f_star = (b * p - q) / b
    return max(f_star, 0.0)


def evaluar_apuesta(
    probabilidad_modelo: float,
    cuota_decimal: float,
    bankroll: Decimal,
    kelly_fraccion: float | None = None,
    min_edge: float | None = None,
    stake_maximo: Decimal | None = None,
) -> ValueBetEvaluation:
    """
    Evalúa si una cuota de mercado representa una "value bet" dado el modelo,
    y de ser así, calcula el stake recomendado bajo Kelly fraccional.
    """
    kelly_fraccion = kelly_fraccion if kelly_fraccion is not None else settings.KELLY_FRACTION
    min_edge = min_edge if min_edge is not None else settings.MIN_EDGE_THRESHOLD
    stake_maximo = stake_maximo if stake_maximo is not None else Decimal(str(settings.MAX_STAKE_PER_BET))

    valor_esperado = calcular_valor_esperado(probabilidad_modelo, cuota_decimal)
    kelly_completo = calcular_kelly_completo(probabilidad_modelo, cuota_decimal)

    es_apuesta_de_valor = valor_esperado >= min_edge and kelly_completo > 0

    kelly_ajustado = kelly_completo * kelly_fraccion
    stake_sugerido = Decimal(str(kelly_ajustado)) * bankroll if es_apuesta_de_valor else Decimal("0")
    stake_sugerido = min(stake_sugerido, stake_maximo).quantize(Decimal("0.01"))

    return ValueBetEvaluation(
        probabilidad_modelo=probabilidad_modelo,
        cuota_decimal=cuota_decimal,
        valor_esperado=valor_esperado,
        kelly_completo=kelly_completo,
        kelly_fraccion_usada=kelly_fraccion,
        stake_sugerido=stake_sugerido,
        es_apuesta_de_valor=es_apuesta_de_valor,
    )
