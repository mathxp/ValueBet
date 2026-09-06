"""
Escáner de mercado: conecta predicción (ml_models) + cuotas en vivo (exchange)
+ gestión de riesgo (risk_manager) para DETECTAR Y RECOMENDAR value bets.

Esto es una herramienta de apoyo a la decisión, no un bot que aposta solo:
nunca llama a exchange_client.place_order(). Solo lee cuotas (get_market_odds)
y el bankroll de referencia para dimensionar el stake sugerido vía Kelly
(get_account_balance). Cada recomendación queda en estado RECOMENDADA para
que la revises vos -- ver db_models.models.Operacion.

Además, CADA análisis que se hace (haya o no una recomendación) queda
registrado en AnalisisPartido -- incluyendo los "NO BET" explícitos -- para
poder evaluar con el tiempo qué tan bueno es el modelo de verdad. Ver
db_models.models.AnalisisPartido y ml_models/pipelines/quality.py.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from db_models.models import AnalisisPartido, Operacion, Partido
from ml_models.pipelines.quality import (
    MIN_CONFIDENCE_SCORE,
    MIN_DATA_QUALITY_SCORE,
    calcular_confidence_score,
    calcular_data_quality_score,
    calcular_value_score,
)
from ml_models.pipelines.team_ratings import calcular_ratings
from ml_models.predictor import MatchPredictor
from trading_engine.exchange_client import ExchangeClient, get_exchange_client
from trading_engine.risk_manager import evaluar_apuesta

logger = logging.getLogger(__name__)


class OddsScanner:
    def __init__(
        self,
        exchange_client: ExchangeClient | None = None,
        predictor: MatchPredictor | None = None,
    ):
        self.exchange_client = exchange_client or get_exchange_client()
        self.predictor = predictor or MatchPredictor()

    def _market_id_for(self, partido: Partido) -> str:
        return partido.metricas_avanzadas.get("betfair_market_id") or str(partido.id)

    def _probabilidad_para(self, partido: Partido, mercado: str, seleccion: str) -> float | None:
        """Probabilidad del modelo para una selección, sea del mercado 1X2 o de
        Over/Under de goles totales (mercado="OVER_UNDER_2.5", etc.)."""
        if mercado == "1X2":
            probabilidades = self.predictor.predecir(partido)
            return probabilidades.get(seleccion) if probabilidades else None

        if mercado.startswith("OVER_UNDER_"):
            linea = float(mercado.removeprefix("OVER_UNDER_"))
            prob_over = self.predictor.predecir_probabilidad_over(partido, linea)
            if prob_over is None:
                return None
            return prob_over if seleccion == "OVER" else 1 - prob_over

        return None

    @staticmethod
    def _familia_mercado(mercado: str) -> str:
        """Agrupa mercados relacionados -- todas las líneas de Over/Under de un
        mismo partido son, en el fondo, la misma apuesta a "va a haber muchos/pocos
        goles" repetida con distinta línea. Recomendar las 4 a la vez es ruido, no
        4 señales independientes (están altamente correlacionadas entre sí)."""
        return "OVER_UNDER" if mercado.startswith("OVER_UNDER_") else mercado

    def _registrar_no_bet_general(self, partido: Partido, motivo: str) -> None:
        """Un solo registro cuando no se pudo evaluar nada del partido (sin
        cuotas, o sin xG proyectado) -- evita loguear una fila por cada mercado
        que ni siquiera se pudo intentar."""
        ultimo = AnalisisPartido.objects.filter(partido=partido, mercado="GENERAL").first()
        if ultimo and ultimo.motivo_no_bet == motivo:
            return
        AnalisisPartido.objects.create(
            partido=partido,
            mercado="GENERAL",
            recomendacion=AnalisisPartido.Recomendacion.NO_BET,
            motivo_no_bet=motivo,
        )

    def _calcular_scores(self, partido: Partido) -> tuple[int, int] | None:
        """(data_quality_score, confidence_score) según el historial real detrás
        del rating de cada equipo. None si alguno de los dos no tiene rating."""
        ratings = calcular_ratings(partido.liga)
        local = ratings.get(partido.equipo_local.api_football_id)
        visitante = ratings.get(partido.equipo_visitante.api_football_id)
        if not local or not visitante:
            return None

        data_quality = calcular_data_quality_score(
            local.partidos, visitante.partidos, local.ultimo_partido, visitante.ultimo_partido
        )
        confidence = calcular_confidence_score(data_quality, local.partidos, visitante.partidos)
        return data_quality, confidence

    # Tope del campo AnalisisPartido.cuota_justa (DecimalField max_digits=7,
    # decimal_places=3). Cuando la probabilidad es casi cero (ej. un
    # visitante que nunca gana), 1/probabilidad puede dispararse muy por
    # encima de lo que el campo puede guardar -- eso no es un dato útil de
    # todas formas (nadie ofrece esa cuota en la práctica), así que se topa
    # en vez de dejar que la escritura a la base de datos explote.
    CUOTA_JUSTA_MAXIMA = Decimal("9999.999")

    @classmethod
    def _cuota_justa_segura(cls, probabilidad: float) -> Decimal | None:
        if not probabilidad or probabilidad <= 0:
            return None
        return min(round(Decimal(str(1 / probabilidad)), 3), cls.CUOTA_JUSTA_MAXIMA)

    def _registrar_analisis(
        self, partido: Partido, mercado: str, seleccion: str, probabilidad: float,
        cuota_mercado: Decimal, data_quality: int, confidence: int,
        recomendacion: str, motivo_no_bet: str = "",
        kelly_fraccion: float | None = None, stake_sugerido: Decimal | None = None,
    ) -> AnalisisPartido | None:
        probabilidad_implicita = 1 / float(cuota_mercado) if cuota_mercado else None
        edge = (probabilidad - probabilidad_implicita) if probabilidad_implicita is not None else None
        ev = (probabilidad * float(cuota_mercado) - 1) if cuota_mercado else None
        value = calcular_value_score(ev, confidence)

        # No duplicar una fila idéntica en cada escaneo de 30s -- solo se
        # registra una fila nueva si la cuota de mercado cambió desde la
        # última vez (eso sí es información nueva, útil para CLV más adelante).
        ultimo = AnalisisPartido.objects.filter(partido=partido, mercado=mercado).order_by("-fecha_analisis").first()
        if ultimo and ultimo.cuota_mercado == cuota_mercado and ultimo.recomendacion == recomendacion:
            return ultimo

        goles = self.predictor.predecir_goles(partido)
        probabilidades_1x2 = self.predictor.predecir(partido) if mercado == "1X2" else None

        return AnalisisPartido.objects.create(
            partido=partido,
            mercado=mercado,
            seleccion_evaluada=seleccion,
            xg_local=goles[0] if goles else None,
            xg_visitante=goles[1] if goles else None,
            probabilidad_local=probabilidades_1x2.get("LOCAL") if probabilidades_1x2 else None,
            probabilidad_empate=probabilidades_1x2.get("EMPATE") if probabilidades_1x2 else None,
            probabilidad_visitante=probabilidades_1x2.get("VISITANTE") if probabilidades_1x2 else None,
            probabilidad_seleccion=probabilidad,
            cuota_mercado=cuota_mercado,
            cuota_justa=self._cuota_justa_segura(probabilidad),
            probabilidad_implicita=probabilidad_implicita,
            edge=edge,
            ev=ev,
            data_quality_score=data_quality,
            confidence_score=confidence,
            value_score=value,
            recomendacion=recomendacion,
            motivo_no_bet=motivo_no_bet,
            kelly_fraccion_usada=kelly_fraccion,
            stake_sugerido=stake_sugerido,
        )

    def escanear_partido(self, partido: Partido) -> list[Operacion]:
        market_id = self._market_id_for(partido)

        try:
            precios = self.exchange_client.get_market_odds(market_id)
        except Exception:
            logger.exception("Fallo al obtener cuotas para partido %s", partido.id)
            return []

        if not precios:
            self._registrar_no_bet_general(partido, "Sin cuotas de mercado disponibles todavía.")
            return []

        scores = self._calcular_scores(partido)
        if scores is None:
            self._registrar_no_bet_general(
                partido, "Datos insuficientes: algún equipo no tiene historial suficiente."
            )
            return []
        data_quality, confidence = scores

        bankroll = self.exchange_client.get_account_balance()

        candidatos: dict[str, tuple] = {}  # familia -> (precio, evaluacion), la de mayor EV
        for precio in precios:
            probabilidad = self._probabilidad_para(partido, precio.mercado, precio.seleccion)
            if probabilidad is None:
                continue

            evaluacion = evaluar_apuesta(
                probabilidad_modelo=probabilidad,
                cuota_decimal=float(precio.precio_back),
                bankroll=bankroll,
            )

            familia = self._familia_mercado(precio.mercado)
            mejor_actual = candidatos.get(familia)
            if mejor_actual is None or evaluacion.valor_esperado > mejor_actual[1].valor_esperado:
                candidatos[familia] = (precio, evaluacion)

        if not candidatos:
            self._registrar_no_bet_general(
                partido, "Datos insuficientes: algún equipo no tiene historial suficiente."
            )
            return []

        operaciones_creadas = []
        for precio, evaluacion in candidatos.values():
            es_value_bet = (
                evaluacion.es_apuesta_de_valor
                and evaluacion.stake_sugerido > Decimal("0")
                and data_quality >= MIN_DATA_QUALITY_SCORE
                and confidence >= MIN_CONFIDENCE_SCORE
            )

            if es_value_bet:
                motivo = ""
                recomendacion = AnalisisPartido.Recomendacion.VALUE_BET
            else:
                recomendacion = AnalisisPartido.Recomendacion.NO_BET
                if data_quality < MIN_DATA_QUALITY_SCORE:
                    motivo = f"Calidad de datos insuficiente ({data_quality}/100)."
                elif confidence < MIN_CONFIDENCE_SCORE:
                    motivo = f"Confianza del análisis insuficiente ({confidence}/100)."
                elif evaluacion.valor_esperado <= 0:
                    motivo = "Valor esperado negativo o nulo."
                else:
                    motivo = "Edge inferior al umbral mínimo configurado."

            self._registrar_analisis(
                partido=partido,
                mercado=precio.mercado,
                seleccion=precio.seleccion,
                probabilidad=evaluacion.probabilidad_modelo,
                cuota_mercado=precio.precio_back,
                data_quality=data_quality,
                confidence=confidence,
                recomendacion=recomendacion,
                motivo_no_bet=motivo,
                kelly_fraccion=evaluacion.kelly_fraccion_usada if es_value_bet else None,
                stake_sugerido=evaluacion.stake_sugerido if es_value_bet else None,
            )

            if not es_value_bet:
                continue

            # Una recomendación por selección/mercado por partido -- el
            # escaneo corre cada 30s (ver core/celery.py) y no queremos
            # spamear la misma señal una y otra vez mientras siga vigente.
            ya_existe = Operacion.objects.filter(
                partido=partido, mercado=precio.mercado, seleccion=precio.seleccion
            ).exists()
            if ya_existe:
                continue

            operacion = Operacion.objects.create(
                partido=partido,
                mercado=precio.mercado,
                seleccion=precio.seleccion,
                probabilidad_modelo=evaluacion.probabilidad_modelo,
                cuota_apostada=precio.precio_back,
                valor_esperado=evaluacion.valor_esperado,
                kelly_fraccion_usada=evaluacion.kelly_fraccion_usada,
                stake=evaluacion.stake_sugerido,
                estado=Operacion.Estado.RECOMENDADA,
            )
            operaciones_creadas.append(operacion)
            logger.info(
                "Recomendación generada: partido=%s mercado=%s seleccion=%s edge=%.3f stake=%s",
                partido.id,
                precio.mercado,
                precio.seleccion,
                evaluacion.valor_esperado,
                evaluacion.stake_sugerido,
            )

        return operaciones_creadas
