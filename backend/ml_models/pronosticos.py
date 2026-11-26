"""
Pronóstico "para humanos" de cada partido: lo más probable en resultado,
doble oportunidad y goles, más la simulación Monte Carlo. Lo usan la API
(/api/pronosticos/), el registro histórico de aciertos (PronosticoRegistrado)
y las notificaciones automáticas (trading_engine/notificaciones.py).
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from db_models.models import Partido, PronosticoRegistrado
from ml_models.predictor import MatchPredictor, probabilidades_1x2_por_poisson, simular_partido

VENTANA_DIAS = 21
SELECCIONES = ("LOCAL", "EMPATE", "VISITANTE")
COMPETICION_POR_LIGA = {"Primera División": "Liga de Primera"}


def nombre_competicion(partido: Partido) -> str:
    return COMPETICION_POR_LIGA.get(partido.liga, partido.liga or "Liga de Primera")


def etiqueta_fecha(partido: Partido) -> str:
    """'Fecha 29' en la liga (por partidos ya disputados de cada equipo); la ronda en copas."""
    ronda = partido.metricas_avanzadas.get("ronda")
    if ronda:
        return ronda
    if partido.liga and partido.liga != "Primera División":
        return partido.liga
    previos = []
    for equipo_id in (partido.equipo_local_id, partido.equipo_visitante_id):
        previos.append(
            Partido.objects.filter(
                Q(equipo_local_id=equipo_id) | Q(equipo_visitante_id=equipo_id),
                liga=partido.liga,
                temporada=partido.temporada,
                fecha_hora__lt=partido.fecha_hora,
            )
            .exclude(estado=Partido.Estado.CANCELADO)
            .count()
        )
    return f"Fecha {max(previos) + 1}"


def _probabilidades(predictor: MatchPredictor, partido: Partido, xg: tuple[float, float], rho: float):
    """1X2 calibrado (renormalizado) y mezclado 50/50 con el mercado si hay cuotas."""
    crudas = probabilidades_1x2_por_poisson(xg[0], xg[1], rho)
    modelo = {s: predictor._calibrar("1X2", crudas[s]) for s in SELECCIONES}
    total = sum(modelo.values()) or 1.0
    modelo = {s: p / total for s, p in modelo.items()}
    mercado = predictor.probabilidades_1x2_mercado(partido)
    if mercado is None:
        return modelo, False
    w = predictor.PESO_MODELO_VS_MERCADO
    return {s: w * modelo[s] + (1 - w) * mercado[s] for s in SELECCIONES}, True


def _prob_over(predictor: MatchPredictor, xg, rho) -> float:
    from ml_models.predictor import distribucion_goles_totales, probabilidad_over

    cruda = probabilidad_over(distribucion_goles_totales(xg[0], xg[1], rho), 2.5)
    return predictor._calibrar("OVER_UNDER_2.5", cruda)


def calcular_pronostico(
    partido: Partido, predictor: MatchPredictor, xg=None, rho=None, con_simulacion: bool = True
) -> dict | None:
    """None si no hay goles esperados (equipo sin historial suficiente)."""
    if xg is None:
        xg = predictor.predecir_goles(partido)
    if xg is None:
        return None
    if rho is None:
        rho = partido.metricas_avanzadas.get("dc_rho", 0.0)

    p1x2, usa_mercado = _probabilidades(predictor, partido, xg, rho)
    dobles = {
        "1X": p1x2["LOCAL"] + p1x2["EMPATE"],
        "X2": p1x2["EMPATE"] + p1x2["VISITANTE"],
        "12": p1x2["LOCAL"] + p1x2["VISITANTE"],
    }
    ganador = max(p1x2, key=p1x2.get)
    # Doble oportunidad que cubre al favorito ("gana o empata"), no "12".
    doble = {"LOCAL": "1X", "VISITANTE": "X2"}.get(ganador) or max(("1X", "X2"), key=dobles.get)
    p_over = _prob_over(predictor, xg, rho)

    resultado = {
        "competicion": nombre_competicion(partido),
        "etiqueta_fecha": etiqueta_fecha(partido),
        "xg_local": round(xg[0], 2),
        "xg_visitante": round(xg[1], 2),
        "probabilidades": {k: round(v, 4) for k, v in p1x2.items()},
        "fuente": "modelo+mercado" if usa_mercado else "modelo",
        "pronostico": {"mercado": "1X2", "seleccion": ganador, "probabilidad": round(p1x2[ganador], 4)},
        "doble_oportunidad": {"mercado": "DOBLE_OPORTUNIDAD", "seleccion": doble, "probabilidad": round(dobles[doble], 4)},
        "goles": {
            "mercado": "OVER_UNDER_2.5",
            "seleccion": "OVER" if p_over >= 0.5 else "UNDER",
            "probabilidad": round(max(p_over, 1 - p_over), 4),
        },
    }
    if con_simulacion:
        resultado["simulacion"] = simular_partido(xg[0], xg[1], rho=rho, semilla=partido.id)
    return resultado


def proximos_partidos(dias: int = VENTANA_DIAS):
    ahora = timezone.now()
    return (
        Partido.objects.filter(
            estado=Partido.Estado.PROGRAMADO, fecha_hora__gte=ahora, fecha_hora__lte=ahora + timedelta(days=dias)
        )
        .select_related("equipo_local", "equipo_visitante")
        .order_by("fecha_hora")
    )


# ------------------------------------------------------------- registro histórico
def _guardar(partido: Partido, pron: dict, reconstruido: bool) -> PronosticoRegistrado:
    p = pron["probabilidades"]
    obj, _ = PronosticoRegistrado.objects.update_or_create(
        partido=partido,
        defaults={
            "competicion": pron["competicion"],
            "etiqueta_fecha": pron["etiqueta_fecha"],
            "prob_local": p["LOCAL"],
            "prob_empate": p["EMPATE"],
            "prob_visitante": p["VISITANTE"],
            "pick_1x2": pron["pronostico"]["seleccion"],
            "pick_seguro": pron["doble_oportunidad"]["seleccion"],
            "prob_seguro": pron["doble_oportunidad"]["probabilidad"],
            "pick_goles": pron["goles"]["seleccion"],
            "prob_goles": pron["goles"]["probabilidad"],
            "fuente": pron["fuente"],
            "reconstruido": reconstruido,
        },
    )
    return obj


def registrar_proximos() -> int:
    """Actualiza la foto de cada partido que todavía no empieza (se congela al empezar)."""
    predictor = MatchPredictor()
    n = 0
    for partido in proximos_partidos():
        pron = calcular_pronostico(partido, predictor, con_simulacion=False)
        if pron:
            _guardar(partido, pron, reconstruido=False)
            n += 1
    return n


def _resultado(partido: Partido) -> str | None:
    gl, gv = partido.resultado.get("local"), partido.resultado.get("visitante")
    if gl is None or gv is None:
        return None
    return "LOCAL" if gl > gv else "VISITANTE" if gv > gl else "EMPATE"


def evaluar_registrados() -> int:
    """Marca acierto/fallo en los pronósticos cuyos partidos ya terminaron."""
    n = 0
    pendientes = PronosticoRegistrado.objects.filter(
        acierto_1x2__isnull=True, partido__estado=Partido.Estado.FINALIZADO
    ).select_related("partido")
    for reg in pendientes:
        real = _resultado(reg.partido)
        if real is None:
            continue
        total = reg.partido.resultado["local"] + reg.partido.resultado["visitante"]
        cubre = {"1X": ("LOCAL", "EMPATE"), "X2": ("EMPATE", "VISITANTE"), "12": ("LOCAL", "VISITANTE")}
        reg.acierto_1x2 = reg.pick_1x2 == real
        reg.acierto_seguro = real in cubre.get(reg.pick_seguro, ())
        reg.acierto_goles = (total > 2.5) == (reg.pick_goles == "OVER") if reg.pick_goles else None
        reg.save(update_fields=["acierto_1x2", "acierto_seguro", "acierto_goles", "actualizado_en"])
        n += 1
    return n


def reconstruir_temporada(temporada: str) -> int:
    """
    Pronósticos de partidos YA jugados, calculados con el modelo ajustado solo
    con partidos anteriores a cada uno (hasta_fecha) -- sin datos del futuro.
    Quedan marcados reconstruido=True. No pisa fotos reales tomadas en vivo.
    """
    from ml_models.pipelines.team_ratings import LIGA_MODELO, historial_precargado, proyectar_xg, rho_dixon_coles

    predictor = MatchPredictor()
    n = 0
    partidos = (
        Partido.objects.filter(estado=Partido.Estado.FINALIZADO, temporada=temporada)
        .exclude(pronostico_registrado__reconstruido=False)
        .select_related("equipo_local", "equipo_visitante")
        .order_by("fecha_hora")
    )
    with historial_precargado():
        for partido in partidos:
            xg = proyectar_xg(partido.equipo_local_id, partido.equipo_visitante_id, LIGA_MODELO, hasta_fecha=partido.fecha_hora)
            if xg is None:
                continue
            rho = rho_dixon_coles(LIGA_MODELO, hasta_fecha=partido.fecha_hora)
            pron = calcular_pronostico(partido, predictor, xg=xg, rho=rho, con_simulacion=False)
            if pron:
                _guardar(partido, pron, reconstruido=True)
                PronosticoRegistrado.objects.filter(partido=partido).update(
                    acierto_1x2=None, acierto_seguro=None, acierto_goles=None
                )
                n += 1
    evaluar_registrados()
    return n


def historial_por_fecha(limite: int = 8) -> list[dict]:
    """Aciertos agrupados por fecha/ronda, de la más reciente a la más antigua."""
    regs = (
        PronosticoRegistrado.objects.filter(acierto_1x2__isnull=False)
        .select_related("partido", "partido__equipo_local", "partido__equipo_visitante")
        .order_by("-partido__fecha_hora")
    )
    grupos: dict[tuple, dict] = {}
    for r in regs:
        clave = (r.competicion, r.etiqueta_fecha, r.partido.temporada)
        g = grupos.setdefault(
            clave,
            {
                "competicion": r.competicion,
                "etiqueta_fecha": r.etiqueta_fecha,
                "temporada": r.partido.temporada,
                "ultima_fecha": r.partido.fecha_hora,
                "partidos": 0,
                "aciertos_1x2": 0,
                "aciertos_seguro": 0,
                "aciertos_goles": 0,
                "reconstruido": False,
                "detalle": [],
            },
        )
        g["partidos"] += 1
        g["aciertos_1x2"] += int(bool(r.acierto_1x2))
        g["aciertos_seguro"] += int(bool(r.acierto_seguro))
        g["aciertos_goles"] += int(bool(r.acierto_goles))
        g["reconstruido"] = g["reconstruido"] or r.reconstruido
        g["detalle"].append(
            {
                "local": r.partido.equipo_local.nombre,
                "visitante": r.partido.equipo_visitante.nombre,
                "marcador": f'{r.partido.resultado.get("local")}-{r.partido.resultado.get("visitante")}',
                "pick_1x2": r.pick_1x2,
                "pick_seguro": r.pick_seguro,
                "acierto_1x2": r.acierto_1x2,
                "acierto_seguro": r.acierto_seguro,
            }
        )
        if len(grupos) > limite:
            grupos.pop(clave)
            break
    return list(grupos.values())


def resumen_temporada(temporada: str) -> dict:
    regs = PronosticoRegistrado.objects.filter(acierto_1x2__isnull=False, partido__temporada=temporada)
    n = regs.count()
    if not n:
        return {"partidos": 0}
    return {
        "partidos": n,
        "acierto_1x2": regs.filter(acierto_1x2=True).count() / n,
        "acierto_seguro": regs.filter(acierto_seguro=True).count() / n,
        "acierto_goles": regs.filter(acierto_goles=True).count() / n,
    }
