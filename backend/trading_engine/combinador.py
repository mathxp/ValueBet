"""
Arma combinadas (apuestas múltiples) de hasta MAX_PATAS partidos distintos.

A diferencia del escáner de apuestas individuales (que prioriza EDGE/EV),
acá el criterio de selección de las patas es la PROBABILIDAD -- el objetivo
explícito que pidió el usuario es "tratar de acertar", no maximizar valor
esperado por pata. Combinar patas de EV individualmente positivo, usando el
producto de sus propias cuotas (no un precio de combinada real de una casa,
que suele traer un margen extra), da matemáticamente un EV combinado también
positivo -- eso no es lo que hay que vigilar acá.

Lo que sí hay que vigilar es EDGE_MAXIMO_CONFIABLE: 2-3 edges individuales
razonables (ej. 12-15% cada uno) se COMPONEN multiplicativamente al
combinarlos ((1+edge₁)×(1+edge₂)×... -1), y fácilmente superan el 35% que ya
se considera estadísticamente inverosímil para una apuesta individual -- ahí
`evaluar_apuesta` bloquea la combinada como anomalía (edge_extremo), igual
que bloquearía una apuesta individual con ese mismo edge.

Reglas duras:
- Nunca dos patas del mismo partido (estarían correlacionadas).
- Solo patas de mercados con calibración real (mismo criterio que un value
  bet individual) -- una combinada ya multiplica el riesgo de cada pata
  entre sí, no tiene sentido arrancar de una probabilidad sin validar.
- Solo la pata de mayor probabilidad por partido (si Cobresal-Limache tiene
  candidatas en 1X2 y Doble Oportunidad, se usa una sola, la más segura).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from db_models.models import AnalisisPartido, CalibracionMercado, Combinada, ConfiguracionRiesgo, Partido
from trading_engine.exchange_client import get_exchange_client
from trading_engine.risk_manager import evaluar_apuesta

MAX_PATAS = 3
MIN_PATAS = 2
PROBABILIDAD_MINIMA_PATA = 0.55

# Multiplicador extra sobre la fracción de Kelly configurada: cada pata ya
# pasó su propio filtro de confianza, pero combinarlas compone el riesgo de
# que el modelo se equivoque en cualquiera de ellas -- se apuesta bastante
# menos que lo que Kelly diría tomando el combinado a valor nominal.
FRACCION_KELLY_COMBINADA = 0.5


def _mercado_calibrado(mercado: str, mercados_calibrados: set[str]) -> bool:
    if mercado == "DOBLE_OPORTUNIDAD":
        return "1X2" in mercados_calibrados
    return mercado in mercados_calibrados


def _candidatas_por_partido(horas_adelante: int = 72) -> dict[int, AnalisisPartido]:
    """La mejor pata (mayor probabilidad) por partido, entre los análisis más
    recientes de partidos programados dentro de la ventana."""
    horizonte = timezone.now() + timedelta(hours=horas_adelante)
    mercados_calibrados = set(CalibracionMercado.objects.values_list("mercado", flat=True))

    analisis = (
        AnalisisPartido.objects.filter(
            partido__estado=Partido.Estado.PROGRAMADO,
            partido__fecha_hora__gte=timezone.now(),
            partido__fecha_hora__lte=horizonte,
            recomendacion=AnalisisPartido.Recomendacion.VALUE_BET,
            probabilidad_seleccion__gte=PROBABILIDAD_MINIMA_PATA,
        )
        .exclude(mercado="GENERAL")
        .select_related("partido")
        .order_by("-fecha_analisis")
    )

    mejor_por_partido: dict[int, AnalisisPartido] = {}
    vista_por_partido_mercado: set[tuple[int, str]] = set()
    for fila in analisis:
        clave_version = (fila.partido_id, fila.mercado)
        if clave_version in vista_por_partido_mercado:
            continue  # ya se vio una versión más reciente de este (partido, mercado)
        vista_por_partido_mercado.add(clave_version)

        if not _mercado_calibrado(fila.mercado, mercados_calibrados):
            continue

        actual = mejor_por_partido.get(fila.partido_id)
        if actual is None or fila.probabilidad_seleccion > actual.probabilidad_seleccion:
            mejor_por_partido[fila.partido_id] = fila

    return mejor_por_partido


def generar_combinada(horas_adelante: int = 72) -> Combinada | None:
    """
    Arma UNA combinada con las mejores 2-3 patas disponibles (una por
    partido). Retorna None si no hay al menos MIN_PATAS candidatas, o si
    `evaluar_apuesta` bloquea el resultado -- normalmente porque el edge
    combinado superó EDGE_MAXIMO_CONFIABLE (ver docstring del módulo), no
    porque el EV haya dado negativo (eso es matemáticamente raro combinando
    patas ya individualmente positivas).
    """
    candidatas = sorted(
        _candidatas_por_partido(horas_adelante).values(),
        key=lambda a: a.probabilidad_seleccion,
        reverse=True,
    )[:MAX_PATAS]

    if len(candidatas) < MIN_PATAS:
        return None

    cuota_combinada = Decimal("1")
    probabilidad_combinada = 1.0
    for pata in candidatas:
        cuota_combinada *= pata.cuota_mercado
        probabilidad_combinada *= pata.probabilidad_seleccion
    cuota_combinada = cuota_combinada.quantize(Decimal("0.001"))

    config = ConfiguracionRiesgo.actual()
    bankroll = get_exchange_client().get_account_balance()

    evaluacion = evaluar_apuesta(
        probabilidad_modelo=probabilidad_combinada,
        cuota_decimal=float(cuota_combinada),
        bankroll=bankroll,
        kelly_fraccion=config.kelly_fraction * FRACCION_KELLY_COMBINADA,
        min_edge=config.min_edge_threshold,
        stake_maximo=config.max_stake_per_bet,
    )

    if not evaluacion.es_apuesta_de_valor or evaluacion.stake_sugerido <= Decimal("0"):
        return None

    # No repetir la misma combinación de partidos si ya hay una recomendada
    # vigente -- el escaneo puede correr muchas veces antes de que se resuelva.
    partidos_ids = sorted(pata.partido_id for pata in candidatas)
    for existente in Combinada.objects.filter(estado=Combinada.Estado.RECOMENDADA):
        if sorted(existente.patas.values_list("partido_id", flat=True)) == partidos_ids:
            return existente

    combinada = Combinada.objects.create(
        cuota_combinada=cuota_combinada,
        probabilidad_combinada=probabilidad_combinada,
        valor_esperado=evaluacion.valor_esperado,
        kelly_fraccion_usada=evaluacion.kelly_fraccion_usada,
        stake=evaluacion.stake_sugerido,
    )
    combinada.patas.set(candidatas)
    return combinada
