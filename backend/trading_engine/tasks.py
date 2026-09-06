import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from db_models.models import Partido
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
