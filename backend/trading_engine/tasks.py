import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from db_models.models import Partido
from trading_engine.combinador import generar_combinada
from trading_engine.scanner import OddsScanner

logger = logging.getLogger(__name__)


@shared_task
def scan_market_odds(minutes_ahead: int = 180) -> int:
    """
    Tarea periódica (cada 30s vía Celery beat): escanea cuotas de partidos
    próximos y genera recomendaciones para las que superen el umbral de edge.
    No ejecuta nada -- ver trading_engine/scanner.py.
    """
    horizonte = timezone.now() + timedelta(minutes=minutes_ahead)
    partidos = Partido.objects.filter(
        estado=Partido.Estado.PROGRAMADO,
        fecha_hora__lte=horizonte,
        fecha_hora__gte=timezone.now(),
    )

    scanner = OddsScanner()
    total_operaciones = 0
    for partido in partidos:
        operaciones = scanner.escanear_partido(partido)
        total_operaciones += len(operaciones)

    return total_operaciones


@shared_task
def generar_combinadas_pendientes(horas_adelante: int = 72) -> int:
    """
    Tarea periódica: arma una combinada (ver trading_engine/combinador.py) con
    las patas de mayor probabilidad disponibles entre los value bets ya
    detectados por scan_market_odds -- corre después del escaneo individual,
    nunca antes (necesita que ya existan AnalisisPartido con recomendacion=
    VALUE_BET para elegir entre ellos).
    """
    combinada = generar_combinada(horas_adelante=horas_adelante)
    return 1 if combinada else 0
