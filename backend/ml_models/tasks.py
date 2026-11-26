import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from db_models.models import AnalisisPartido, Partido
from ml_models.pipelines.team_ratings import LIGA_MODELO, proyectar_xg, rho_dixon_coles

logger = logging.getLogger(__name__)


@shared_task
def project_xg_for_upcoming_matches(hours_ahead: int = 48) -> int:
    """
    Orquestador (usado por Celery beat): para cada partido próximo, proyecta
    xg_local/xg_visitante con el rating de ataque/defensa de team_ratings.py
    y lo deja en metricas_avanzadas para que ml_models.predictor los use.

    Si algún equipo no tiene historial suficiente todavía (liga recién
    empezando a acumular datos), no se escribe nada y ml_models.predictor
    retorna None para ese partido -- no hay señal, no se apuesta.

    Nunca pisa un xG cargado a mano desde el admin (metricas_avanzadas
    ["xg_fuente"] == "manual") -- ver db_models/admin.py.
    """
    horizonte = timezone.now() + timedelta(hours=hours_ahead)
    partidos = Partido.objects.filter(
        estado=Partido.Estado.PROGRAMADO,
        fecha_hora__lte=horizonte,
        fecha_hora__gte=timezone.now(),
    ).select_related("equipo_local", "equipo_visitante")

    actualizados = 0
    for partido in partidos:
        if partido.metricas_avanzadas.get("xg_fuente") == "manual":
            continue

        proyeccion = proyectar_xg(
            equipo_local_id=partido.equipo_local_id,
            equipo_visitante_id=partido.equipo_visitante_id,
            liga=LIGA_MODELO,
        )
        if not proyeccion:
            continue

        xg_local, xg_visitante = proyeccion
        metricas = dict(partido.metricas_avanzadas)
        metricas["xg_local"] = xg_local
        metricas["xg_visitante"] = xg_visitante
        metricas["xg_fuente"] = "dixon_coles"
        metricas["dc_rho"] = rho_dixon_coles(LIGA_MODELO)
        partido.metricas_avanzadas = metricas
        partido.save(update_fields=["metricas_avanzadas", "actualizado_en"])
        actualizados += 1

    logger.info("project_xg_for_upcoming_matches: %s partidos actualizados", actualizados)
    return actualizados


@shared_task
def reconciliar_analisis() -> int:
    """
    Orquestador (usado por Celery beat): para cada AnalisisPartido sin
    resolver de un partido que ya terminó, completa si la predicción/
    recomendación acertó, el PNL teórico, y el CLV contra la cuota de cierre.

    Esto es lo que permite responder objetivamente "¿qué tan bueno es el
    modelo?" con el tiempo -- ver AnalisisPartido.reconciliar() y la sección
    de rendimiento del modelo en /api/analisis/rendimiento/.
    """
    pendientes = AnalisisPartido.objects.filter(
        resuelto_en__isnull=True,
        partido__estado=Partido.Estado.FINALIZADO,
    ).select_related("partido")

    resueltos = 0
    for analisis in pendientes:
        analisis.reconciliar()
        resueltos += 1

    logger.info("reconciliar_analisis: %s análisis resueltos", resueltos)
    return resueltos
