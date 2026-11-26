import logging
from datetime import datetime, timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import make_aware

from data_ingestion.api_clients.football_api import ApiFootballClient, ApiFootballError
from data_ingestion.scrapers.weather import get_weather_for_match
from db_models.models import Equipo, HistorialCuotas, Partido
from ml_models.pipelines.team_ratings import calcular_proxy_xg_partido

logger = logging.getLogger(__name__)

# api-football usa "Match Winner" para el mercado 1X2, con valores en inglés.
_SELECCION_POR_VALOR = {"Home": "LOCAL", "Draw": "EMPATE", "Away": "VISITANTE"}

# "Double Chance" de api-football -- "Home/Draw"=1X, "Home/Away"=12, "Draw/Away"=X2.
_SELECCION_DOBLE_OPORTUNIDAD_POR_VALOR = {"Home/Draw": "1X", "Home/Away": "12", "Draw/Away": "X2"}

# Líneas de Over/Under a considerar: las más líquidas (más apostadas, precios
# más ajustados) y donde el modelo de Poisson es menos sensible a un pequeño
# error en la proyección de xG. Las líneas extremas (0.5, 5.5+) casi no se
# ofrecen en la práctica y ahí un error chico en el xG cambia mucho la
# probabilidad de la cola -- por eso se tratan con el mismo cuidado que 4.5:
# nunca se recomiendan "a ojo", solo si tienen su propia curva de calibración
# medida contra resultados reales (ver manage.py backtest_modelo
# --guardar-calibracion y CalibracionMercado en trading_engine/scanner.py).
#
# 4.5 se sacó de la lista (antes estaba) tras verificar en la práctica que el
# proyector de xG (team_ratings.py:proyectar_xg) puede llegar a un total
# combinado alto multiplicando dos DEFENSAS flojas entre sí, sin que ninguno
# de los dos equipos tenga un ataque realmente destacado -- ej. Limache
# (ataque 1.76) vs Cobresal (ataque 1.41, promedio de liga 1.44) proyectó 4.13
# goles combinados y terminó en un resultado muy por debajo. Requerir 5+
# goles ya es un evento de cola incluso para el promedio real de la liga
# (2.7 goles/partido) -- no vale la pena confiar ahí en una interacción
# multiplicativa que ninguno de los dos equipos respalda con su propio
# historial de gol.
#
# 0.5 se agregó a pedido del usuario (quiere ver más líneas de goles cuando
# de verdad sean una apuesta buena) -- se habilita la ingesta de cuotas acá,
# pero el gate de calibración es el que decide si alguna vez se recomienda de
# verdad en vivo, exactamente igual que cualquier otro mercado.
LINEAS_OVER_UNDER_VALIDAS = {"0.5", "1.5", "2.5", "3.5"}

# Códigos de estado de fixture de api-football -> nuestro Partido.Estado.
_ESTADO_POR_CODIGO = {
    "TBD": Partido.Estado.PROGRAMADO,
    "NS": Partido.Estado.PROGRAMADO,
    "1H": Partido.Estado.EN_VIVO,
    "HT": Partido.Estado.EN_VIVO,
    "2H": Partido.Estado.EN_VIVO,
    "ET": Partido.Estado.EN_VIVO,
    "BT": Partido.Estado.EN_VIVO,
    "P": Partido.Estado.EN_VIVO,
    "LIVE": Partido.Estado.EN_VIVO,
    "INT": Partido.Estado.EN_VIVO,
    "FT": Partido.Estado.FINALIZADO,
    "AET": Partido.Estado.FINALIZADO,
    "PEN": Partido.Estado.FINALIZADO,
    "AWD": Partido.Estado.FINALIZADO,
    "WO": Partido.Estado.FINALIZADO,
    "PST": Partido.Estado.POSPUESTO,
    "SUSP": Partido.Estado.POSPUESTO,
    "CANC": Partido.Estado.CANCELADO,
    "ABD": Partido.Estado.CANCELADO,
}


def _get_or_create_equipo(team_payload: dict) -> Equipo:
    team = team_payload["team"]
    equipo, _ = Equipo.objects.update_or_create(
        api_football_id=team["id"],
        defaults={
            "nombre": team["name"],
            "pais": team.get("country", ""),
            "logo_url": team.get("logo", ""),
        },
    )
    return equipo


def _upsert_partido(item: dict) -> tuple[Partido, bool]:
    """Crea/actualiza un Partido a partir de un fixture de api-football.

    Retorna (partido, recien_finalizado) -- lo segundo sirve para disparar
    la captura de estadísticas finales justo cuando el partido termina.
    """
    fixture = item["fixture"]
    teams = item["teams"]
    goles = item.get("goals", {})

    equipo_local = _get_or_create_equipo({"team": teams["home"]})
    equipo_visitante = _get_or_create_equipo({"team": teams["away"]})

    estado_anterior = (
        Partido.objects.filter(api_football_id=fixture["id"])
        .values_list("estado", flat=True)
        .first()
    )
    estado_nuevo = _ESTADO_POR_CODIGO.get(fixture["status"]["short"], Partido.Estado.PROGRAMADO)

    defaults = {
        "equipo_local": equipo_local,
        "equipo_visitante": equipo_visitante,
        "liga": item.get("league", {}).get("name", ""),
        "temporada": str(item.get("league", {}).get("season", "")),
        "fecha_hora": make_aware(datetime.fromtimestamp(fixture["timestamp"])),
        "estado": estado_nuevo,
    }
    if goles.get("home") is not None and goles.get("away") is not None:
        defaults["resultado"] = {"local": goles["home"], "visitante": goles["away"]}

    partido, _ = Partido.objects.update_or_create(
        api_football_id=fixture["id"], defaults=defaults
    )
    recien_finalizado = (
        estado_nuevo == Partido.Estado.FINALIZADO and estado_anterior != Partido.Estado.FINALIZADO
    )
    return partido, recien_finalizado


@shared_task
def fetch_upcoming_fixtures(league_id: int) -> int:
    """
    Trae los partidos de ayer/hoy/mañana de una liga: guarda los nuevos y
    sincroniza el estado/resultado de los que ya se jugaron.

    El plan gratuito de api-football solo permite consultar `/fixtures?date=X`
    dentro de una ventana de +-1 día respecto a hoy (ni `next` ni `season` con
    la temporada actual funcionan), así que justo esa ventana es la que se
    recorre día a día -- de paso sirve para detectar partidos recién
    finalizados sin necesitar una tarea aparte.
    """
    client = ApiFootballClient()
    hoy = timezone.localdate()

    guardados = 0
    for fecha in (hoy - timedelta(days=1), hoy, hoy + timedelta(days=1)):
        try:
            fixtures = client.get_fixtures(league_id=league_id, date=fecha.isoformat())
        except ApiFootballError:
            logger.exception("Fallo al obtener fixtures de api-football para %s", fecha)
            continue

        for item in fixtures:
            partido, recien_finalizado = _upsert_partido(item)
            guardados += 1
            if recien_finalizado:
                fetch_match_statistics.delay(partido_id=partido.id)

    logger.info("fetch_upcoming_fixtures: %s partidos guardados/actualizados", guardados)
    return guardados


@shared_task
def fetch_match_statistics(partido_id: int) -> None:
    """Enriquece un partido con estadísticas avanzadas y clima."""
    client = ApiFootballClient()
    partido = Partido.objects.get(pk=partido_id)

    metricas = dict(partido.metricas_avanzadas)

    try:
        stats = client.get_fixture_statistics(partido.api_football_id)
        if stats:
            metricas["estadisticas_api_football"] = stats
            if partido.estado == Partido.Estado.FINALIZADO:
                proxy_xg = calcular_proxy_xg_partido(stats)
                if proxy_xg:
                    metricas["proxy_xg"] = proxy_xg
    except ApiFootballError:
        logger.exception("Fallo al obtener estadísticas de fixture %s", partido_id)

    try:
        injuries = client.get_injuries(partido.api_football_id)
        if injuries:
            metricas["lesiones"] = injuries
    except ApiFootballError:
        logger.exception("Fallo al obtener lesiones de fixture %s", partido_id)

    lat, lon = metricas.get("estadio_lat"), metricas.get("estadio_lon")
    if lat and lon:
        try:
            metricas["clima"] = get_weather_for_match(lat, lon, partido.fecha_hora.date())
        except Exception:
            logger.exception("Fallo al obtener clima para fixture %s", partido_id)

    partido.metricas_avanzadas = metricas
    partido.save(update_fields=["metricas_avanzadas", "actualizado_en"])


def _primer_bookmaker_con_mercado(bookmakers: list[dict], nombre_mercado: str) -> tuple[dict, str] | None:
    """Busca el primer bookmaker que ofrezca `nombre_mercado` -- no todas las casas
    ofrecen los mismos mercados para un mismo partido (ej. William Hill no siempre
    trae "Goals Over/Under" aunque sí traiga "Match Winner")."""
    for bookmaker in bookmakers:
        bet = next((b for b in bookmaker["bets"] if b["name"] == nombre_mercado), None)
        if bet:
            return bet, bookmaker["name"]
    return None


@shared_task
def fetch_and_store_odds(partido_id: int) -> int:
    """
    Guarda un snapshot de cuotas 1X2, Doble Oportunidad y goles totales
    (Over/Under) en HistorialCuotas para un partido.

    api-football (incluso en plan gratuito) da cuotas de casas de apuestas
    tradicionales (William Hill, Bet365, etc.), no de un exchange -- sirven
    como referencia de mercado para el bot mientras no haya cuenta de
    Betfair. Con cuenta de Betfair, esto se reemplaza por
    exchange_client.get_market_odds() en trading_engine/scanner.py.
    """
    client = ApiFootballClient()
    partido = Partido.objects.get(pk=partido_id)

    try:
        respuesta = client.get_odds(partido.api_football_id)
    except ApiFootballError:
        logger.exception("Fallo al obtener cuotas de fixture %s", partido_id)
        return 0

    if not respuesta:
        return 0

    bookmakers = respuesta[0].get("bookmakers", [])
    guardados = 0

    match_winner = _primer_bookmaker_con_mercado(bookmakers, "Match Winner")
    if match_winner:
        bet, origen = match_winner
        for value in bet["values"]:
            seleccion = _SELECCION_POR_VALOR.get(value["value"])
            if not seleccion:
                continue
            HistorialCuotas.objects.create(
                partido=partido,
                origen=origen,
                mercado="1X2",
                seleccion=seleccion,
                cuota_back=value["odd"],
            )
            guardados += 1

    doble_oportunidad = _primer_bookmaker_con_mercado(bookmakers, "Double Chance")
    if doble_oportunidad:
        bet, origen = doble_oportunidad
        for value in bet["values"]:
            seleccion = _SELECCION_DOBLE_OPORTUNIDAD_POR_VALOR.get(value["value"])
            if not seleccion:
                continue
            HistorialCuotas.objects.create(
                partido=partido,
                origen=origen,
                mercado="DOBLE_OPORTUNIDAD",
                seleccion=seleccion,
                cuota_back=value["odd"],
            )
            guardados += 1

    goles_totales = _primer_bookmaker_con_mercado(bookmakers, "Goals Over/Under")
    if goles_totales:
        bet, origen = goles_totales
        for value in bet["values"]:
            # Solo líneas .5 (2.5, 3.5, ...): el total de goles siempre es
            # entero, así que nunca hay empate justo en la línea. Se
            # descartan líneas enteras/cuartos (3.0, 2.75) -- esas son
            # apuestas divididas (parte push) que no vale la pena modelar acá.
            texto = value["value"]  # ej. "Over 2.5"
            partes = texto.split()
            if len(partes) != 2 or not partes[1].endswith(".5"):
                continue

            direccion, linea = partes[0], partes[1]
            if linea not in LINEAS_OVER_UNDER_VALIDAS:
                continue
            seleccion = "OVER" if direccion == "Over" else "UNDER" if direccion == "Under" else None
            if not seleccion:
                continue

            HistorialCuotas.objects.create(
                partido=partido,
                origen=origen,
                mercado=f"OVER_UNDER_{linea}",
                seleccion=seleccion,
                cuota_back=value["odd"],
            )
            guardados += 1

    return guardados


@shared_task
def refresh_odds_for_live_window(minutes_ahead: int = 180) -> None:
    """
    Orquestador (usado por Celery beat): refresca cuotas solo de partidos
    inminentes (por defecto, próximas 3 horas) para no quemar la cuota
    diaria de api-football pidiendo cuotas de partidos lejanos que aún no
    tienen movimiento relevante de mercado.
    """
    horizonte = timezone.now() + timedelta(minutes=minutes_ahead)
    partidos = Partido.objects.filter(
        estado=Partido.Estado.PROGRAMADO,
        fecha_hora__lte=horizonte,
        fecha_hora__gte=timezone.now(),
    )
    for partido in partidos:
        fetch_and_store_odds.delay(partido_id=partido.id)


@shared_task
def fetch_all_upcoming_fixtures() -> None:
    """Orquestador (usado por Celery beat): recorre settings.WATCHED_LEAGUES."""
    for league_id in settings.WATCHED_LEAGUES:
        fetch_upcoming_fixtures.delay(league_id=league_id)


@shared_task
def refresh_stats_for_upcoming_matches(hours_ahead: int = 48) -> None:
    """Orquestador (usado por Celery beat): refresca métricas de partidos próximos."""
    horizonte = timezone.now() + timedelta(hours=hours_ahead)
    partidos = Partido.objects.filter(
        estado=Partido.Estado.PROGRAMADO,
        fecha_hora__lte=horizonte,
        fecha_hora__gte=timezone.now(),
    )
    for partido in partidos:
        fetch_match_statistics.delay(partido_id=partido.id)
