"""
Ratings de ataque/defensa por equipo y proyección de xG para el próximo
partido -- el mismo principio que un modelo de Poisson ataque/defensa
clásico (Dixon-Coles).

La señal principal son los GOLES REALES de cada partido finalizado
(Partido.resultado), no una estimación: es la base más confiable que
tenemos, sobre todo ahora que hay casi cinco temporadas de historial
importado (2022-2026, ver `manage.py import_excel_dataset_2022_2023`,
`import_excel_dataset` e `import_historical_dataset`) además de los
partidos que va completando api-football día a día.

Aislamiento de varianza: cuando además hay un "proxy" de xG por tiros
(`proxy_xg`, calculado por `data_ingestion.tasks.fetch_match_statistics` y
guardado en `Partido.metricas_avanzadas["proxy_xg"]`), calcular_ratings()
mezcla ese proxy con el gol real (ver `_valor_ataque_defensa`) para no
dejar que un partido dominado pero empatado/perdido por varianza pese igual
que un partido realmente parejo. Esto solo aplica a los partidos que
api-football ingiere en vivo -- los datasets históricos importados desde
Excel no traen estadísticas de tiros, así que para ellos (la gran mayoría
del historial hoy) se sigue usando el gol real sin mezcla, que es la
alternativa más confiable cuando no hay proxy disponible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from db_models.models import Partido

# Conversión promedio de tiro a gol según zona (valores de referencia de
# análisis públicos de fútbol, no medidos por nosotros). Ajustables si en el
# futuro se calibran contra resultados reales de la liga.
TASA_CONVERSION_DENTRO_AREA = 0.11
TASA_CONVERSION_FUERA_AREA = 0.03

MIN_PARTIDOS_PARA_RATING = 3
MAX_PARTIDOS_POR_EQUIPO = 15

# Peso del proxy de xG (por tiros) frente al gol real cuando ambos están
# disponibles para un partido -- 0.5 pondera parejo: ni ignora la varianza
# del resultado real (por eso no es 1.0) ni confía ciegamente en un proxy
# calibrado con tasas de conversión genéricas, no medidas en esta liga (por
# eso no es más alto). Ver el docstring del módulo.
PESO_XG_PROXY = 0.5

# Shrinkage (regularización estadística, tipo James-Stein/Bayes empírico):
# sin esto, un equipo con pocos partidos y forma marcada en ambos extremos
# (ataque muy alto + rival con defensa muy mala) puede disparar la
# proyección multiplicativa a valores poco creíbles (ej. 3.9 goles
# esperados). K_SHRINKAGE es el "peso" en partidos que se le da al promedio
# de la liga -- un equipo con muchos partidos jugados se acerca a su
# promedio real; uno con pocos se acerca más al promedio de la liga.
K_SHRINKAGE = 8

# Los ratings se ajustan con todos los partidos salvo copas (pocos partidos,
# alineaciones alternativas); los partidos de copa se predicen con esos ratings.
COPAS = ("Copa Chile", "Copa de la Liga")
LIGA_MODELO = ""  # "" = todas las competiciones salvo COPAS


def extraer_stats_equipo(stats_equipo: list[dict]) -> dict[str, float]:
    """Convierte el formato [{"type": .., "value": ..}] de api-football a un dict plano."""
    resultado = {}
    for stat in stats_equipo:
        valor = stat.get("value")
        if valor is None:
            valor = 0
        elif isinstance(valor, str) and valor.endswith("%"):
            valor = float(valor.rstrip("%"))
        resultado[stat["type"]] = valor
    return resultado


def calcular_proxy_xg_equipo(stats: dict[str, float]) -> float:
    dentro = float(stats.get("Shots insidebox", 0) or 0)
    fuera = float(stats.get("Shots outsidebox", 0) or 0)
    return round(dentro * TASA_CONVERSION_DENTRO_AREA + fuera * TASA_CONVERSION_FUERA_AREA, 3)


def calcular_proxy_xg_partido(estadisticas_api_football: list[dict]) -> dict[str, float] | None:
    """
    A partir de `metricas_avanzadas["estadisticas_api_football"]` (guardado por
    data_ingestion.tasks.fetch_match_statistics), calcula el proxy de xG de
    ambos equipos. Requiere que el partido ya haya terminado (si no, los
    tiros todavía no reflejan el partido completo).
    """
    if len(estadisticas_api_football) != 2:
        return None

    equipo_a, equipo_b = estadisticas_api_football
    return {
        str(equipo_a["team"]["id"]): calcular_proxy_xg_equipo(
            extraer_stats_equipo(equipo_a["statistics"])
        ),
        str(equipo_b["team"]["id"]): calcular_proxy_xg_equipo(
            extraer_stats_equipo(equipo_b["statistics"])
        ),
    }


@dataclass
class RatingEquipo:
    ataque: float  # goles a favor, promedio de sus últimos partidos
    defensa: float  # goles en contra, promedio de sus últimos partidos
    partidos: int
    ultimo_partido: datetime | None = None  # fecha del partido contado más reciente (Data Quality Score)


def _valor_ataque_defensa(partido: Partido, es_local: bool) -> tuple[float, float]:
    """
    (goles a favor, goles en contra) del equipo local o visitante en este
    partido, mezclados con el proxy de xG por tiros cuando está disponible
    para ambos equipos (ver docstring del módulo) -- si no está disponible,
    retorna el gol real sin modificar.
    """
    goles_local = partido.resultado.get("local")
    goles_visitante = partido.resultado.get("visitante")
    goles_favor = goles_local if es_local else goles_visitante
    goles_contra = goles_visitante if es_local else goles_local

    proxy_xg = partido.metricas_avanzadas.get("proxy_xg")
    if not proxy_xg:
        return float(goles_favor), float(goles_contra)

    equipo_id = partido.equipo_local.api_football_id if es_local else partido.equipo_visitante.api_football_id
    rival_id = partido.equipo_visitante.api_football_id if es_local else partido.equipo_local.api_football_id
    xg_favor = proxy_xg.get(str(equipo_id))
    xg_contra = proxy_xg.get(str(rival_id))
    if xg_favor is None or xg_contra is None:
        return float(goles_favor), float(goles_contra)

    valor_favor = PESO_XG_PROXY * xg_favor + (1 - PESO_XG_PROXY) * goles_favor
    valor_contra = PESO_XG_PROXY * xg_contra + (1 - PESO_XG_PROXY) * goles_contra
    return valor_favor, valor_contra


# Historial precargado en memoria (ver `historial_precargado`): el backtest
# evalúa ~1.200 partidos y, sin esto, descargaba el historial completo de la
# base en cada uno (~3 s por partido contra Neon => ~1 hora).
_precargado: list[Partido] | None = None


class historial_precargado:
    """Context manager: carga una vez los partidos finalizados y filtra en memoria."""

    def __enter__(self):
        global _precargado
        _precargado = list(
            Partido.objects.filter(estado=Partido.Estado.FINALIZADO)
            .select_related("equipo_local", "equipo_visitante")
            .order_by("-fecha_hora")
        )
        return self

    def __exit__(self, *exc):
        global _precargado
        _precargado = None


def _historial_finalizados(liga: str = "", hasta_fecha: datetime | None = None) -> list[Partido]:
    """
    `hasta_fecha`: si se da, solo considera partidos anteriores a esa fecha
    (estrictamente) -- lo usa el backtesting (ml_models/management/commands/
    backtest_modelo.py) para calcular el rating "como se veía" antes de un
    partido histórico específico, sin usar información que en ese momento
    todavía no existía (data leakage). En producción (hasta_fecha=None) se
    usa todo el historial disponible, que es lo que ya hacía esta función.
    """
    if _precargado is not None:
        return [
            p
            for p in _precargado
            if (p.liga == liga if liga else p.liga not in COPAS)
            and (hasta_fecha is None or p.fecha_hora < hasta_fecha)
        ]
    qs = Partido.objects.filter(estado=Partido.Estado.FINALIZADO).order_by("-fecha_hora")
    if liga:
        qs = qs.filter(liga=liga)
    else:
        qs = qs.exclude(liga__in=COPAS)
    if hasta_fecha is not None:
        qs = qs.filter(fecha_hora__lt=hasta_fecha)
    # Sin tope: calcular_ratings() ya se autolimita por equipo (MAX_PARTIDOS_POR_EQUIPO),
    # pero factor_localia() promedia sobre TODO lo que devuelva esta función -- un
    # tope acá (antes [:1000], sin ningún comentario que explicara el número) le
    # cortaba en silencio las temporadas más viejas a medida que la liga acumulaba
    # historial, sesgando la ventaja de local hacia solo las últimas temporadas sin
    # que nada lo avisara (ver HANDOFF_dataset_contexto.md, sección 2.1: con el tope
    # daba ~28.1%, sin tope y con las 5 temporadas completas da ~28.9%, más parecido
    # a la medición independiente del handoff que a las cifras de prompt.md 3.3).
    return list(qs.select_related("equipo_local", "equipo_visitante"))


def calcular_ratings(liga: str = "", hasta_fecha: datetime | None = None) -> dict[int, RatingEquipo]:
    """Rating de ataque/defensa por equipo (pk de Equipo) a partir de goles reales."""
    partidos = _historial_finalizados(liga, hasta_fecha)

    por_equipo: dict[int, list[tuple[float, float]]] = {}
    ultimo_partido_por_equipo: dict[int, datetime] = {}
    for partido in partidos:
        goles_local = partido.resultado.get("local")
        goles_visitante = partido.resultado.get("visitante")
        if goles_local is None or goles_visitante is None:
            continue

        # Clave = pk de Equipo, NO api_football_id: hay equipos sin id de
        # api-football (importados de datasets o ESPN) y todos compartían la
        # clave None, mezclando sus ratings.
        local_id = partido.equipo_local_id
        visitante_id = partido.equipo_visitante_id

        por_equipo.setdefault(local_id, [])
        por_equipo.setdefault(visitante_id, [])
        if len(por_equipo[local_id]) < MAX_PARTIDOS_POR_EQUIPO:
            por_equipo[local_id].append(_valor_ataque_defensa(partido, es_local=True))
            ultimo_partido_por_equipo.setdefault(local_id, partido.fecha_hora)
        if len(por_equipo[visitante_id]) < MAX_PARTIDOS_POR_EQUIPO:
            por_equipo[visitante_id].append(_valor_ataque_defensa(partido, es_local=False))
            ultimo_partido_por_equipo.setdefault(visitante_id, partido.fecha_hora)

    if not por_equipo:
        return {}

    crudos = {
        equipo_id: (
            sum(f for f, _ in partidos) / len(partidos),
            sum(c for _, c in partidos) / len(partidos),
            len(partidos),
        )
        for equipo_id, partidos in por_equipo.items()
    }
    promedio_liga_ataque = sum(ataque for ataque, _, _ in crudos.values()) / len(crudos)
    promedio_liga_defensa = sum(defensa for _, defensa, _ in crudos.values()) / len(crudos)

    ratings = {}
    for equipo_id, (ataque_crudo, defensa_cruda, n) in crudos.items():
        peso = n / (n + K_SHRINKAGE)
        ratings[equipo_id] = RatingEquipo(
            ataque=peso * ataque_crudo + (1 - peso) * promedio_liga_ataque,
            defensa=peso * defensa_cruda + (1 - peso) * promedio_liga_defensa,
            partidos=n,
            ultimo_partido=ultimo_partido_por_equipo.get(equipo_id),
        )
    return ratings


def factor_localia(liga: str = "", hasta_fecha: datetime | None = None) -> tuple[float, float]:
    """
    Ventaja de local medida con goles reales: en esta liga, los locales
    anotan ~35% más que los visitantes (1.64 vs 1.22 goles/partido en el
    historial cargado). Los ratings de ataque/defensa mezclan local y
    visita en un solo promedio por equipo (partirlos por separado dejaría
    muy pocos partidos por equipo para que el shrinkage funcione bien), así
    que esta ventaja se aplica como un ajuste global aparte, no por equipo.

    Retorna (factor_local, factor_visita) relativos al promedio general de
    goles por equipo por partido -- factor_local > 1, factor_visita < 1.
    """
    partidos = _historial_finalizados(liga, hasta_fecha)
    goles_local = [p.resultado["local"] for p in partidos if "local" in p.resultado]
    goles_visita = [p.resultado["visitante"] for p in partidos if "visitante" in p.resultado]

    if not goles_local or not goles_visita:
        return 1.0, 1.0

    promedio_local = sum(goles_local) / len(goles_local)
    promedio_visita = sum(goles_visita) / len(goles_visita)
    promedio_general = (promedio_local + promedio_visita) / 2
    if promedio_general <= 0:
        return 1.0, 1.0

    return promedio_local / promedio_general, promedio_visita / promedio_general


# --------------------------------------------------------------------------
# Modelo Dixon-Coles (en producción desde nov-2026)
#
# Backtest cronológico sin leakage, 689 partidos de 2024-2026:
#                          log loss 1X2   Brier    RPS     log loss O/U 2.5
#   promedios últimos 15      1.0284      0.6170  0.2236        0.7027
#   Dixon-Coles (este)        1.0192      0.6109  0.2212        0.6906
# Mejoras respecto al promedio simple:
#   * ataque/defensa ajustados por la calidad del rival (máxima verosimilitud
#     Poisson): golear al último no vale lo mismo que golear al líder;
#   * pesos por recencia (vida media de 180 días) en vez de un corte duro de
#     15 partidos;
#   * corrección rho de Dixon-Coles para marcadores bajos (0-0, 1-0, 0-1, 1-1).
# Probado y descartado: covariable de viaje largo del visitante y sumar
# incertidumbre del rating (binomial negativa) -- ambas empeoraron el backtest.
# --------------------------------------------------------------------------
VIDA_MEDIA_DIAS = 180
PRIOR_PARTIDOS = 12  # pseudo-partidos que tiran cada rating hacia el promedio (shrinkage)
ITERACIONES_AJUSTE = 40
_cache_modelo: dict = {}


@dataclass
class ModeloDixonColes:
    indice: dict
    ataque: object  # np.ndarray
    defensa: object
    partidos: object
    localia: float
    mu: float
    rho: float

    def xg(self, local_id: int, visitante_id: int) -> tuple[float, float] | None:
        i, j = self.indice.get(local_id), self.indice.get(visitante_id)
        if i is None or j is None:
            return None
        if self.partidos[i] < MIN_PARTIDOS_PARA_RATING or self.partidos[j] < MIN_PARTIDOS_PARA_RATING:
            return None
        xg_local = self.mu * self.localia * self.ataque[i] * self.defensa[j]
        xg_visitante = self.mu * self.ataque[j] * self.defensa[i]
        return float(xg_local), float(xg_visitante)


def _ajustar_rho(lam_h, lam_a, goles_h, goles_a, pesos) -> float:
    """rho de Dixon-Coles por máxima verosimilitud (solo afecta marcadores <= 1-1)."""
    import numpy as np

    bajos = (goles_h <= 1) & (goles_a <= 1)
    lh, la, gh, ga, w = lam_h[bajos], lam_a[bajos], goles_h[bajos], goles_a[bajos], pesos[bajos]
    mejor_rho, mejor_ll = 0.0, -float("inf")
    for rho in np.arange(-0.25, 0.2501, 0.01):
        tau = np.where(
            (gh == 0) & (ga == 0),
            1 - lh * la * rho,
            np.where((gh == 0) & (ga == 1), 1 + lh * rho, np.where((gh == 1) & (ga == 0), 1 + la * rho, 1 - rho)),
        )
        if np.any(tau <= 0):
            continue
        ll = float(np.sum(w * np.log(tau)))
        if ll > mejor_ll:
            mejor_ll, mejor_rho = ll, round(float(rho), 2)
    return mejor_rho


def ajustar_modelo(liga: str = "", hasta_fecha: datetime | None = None) -> ModeloDixonColes | None:
    """
    Ajusta ataque/defensa/localía por máxima verosimilitud Poisson con pesos
    por recencia (actualizaciones multiplicativas alternadas) y luego rho.
    Se cachea por (liga, día, huella de los datos) para no reajustar en cada
    partido del pipeline ni del backtest.
    """
    import numpy as np
    from django.utils import timezone

    partidos = [p for p in _historial_finalizados(liga, hasta_fecha) if p.resultado.get("local") is not None]
    if len(partidos) < 6:
        return None
    referencia = hasta_fecha or timezone.now()
    # Huella de los datos (no solo la cantidad): si se corrige un resultado o
    # cambia el conjunto de partidos con el mismo largo, el modelo se reajusta.
    huella = hash(
        tuple((p.pk, p.equipo_local_id, p.equipo_visitante_id, p.resultado.get("local"), p.resultado.get("visitante")) for p in partidos)
    )
    clave = (liga, referencia.date(), huella)
    if clave in _cache_modelo:
        return _cache_modelo[clave]

    equipos = sorted({p.equipo_local_id for p in partidos} | {p.equipo_visitante_id for p in partidos})
    indice = {e: k for k, e in enumerate(equipos)}
    n = len(equipos)
    H = np.array([indice[p.equipo_local_id] for p in partidos])
    A = np.array([indice[p.equipo_visitante_id] for p in partidos])
    valores = [_valor_ataque_defensa(p, es_local=True) for p in partidos]
    GH = np.array([v[0] for v in valores], float)
    GA = np.array([v[1] for v in valores], float)
    dias = np.array([(referencia - p.fecha_hora).total_seconds() / 86400 for p in partidos])
    W = np.exp(-np.log(2) / VIDA_MEDIA_DIAS * np.maximum(dias, 0))

    ataque, defensa, localia = np.ones(n), np.ones(n), 1.3
    mu = float(np.sum(W * (GH + GA)) / np.sum(W)) / 2
    for _ in range(ITERACIONES_AJUSTE):
        lam_h = mu * localia * ataque[H] * defensa[A]
        lam_a = mu * ataque[A] * defensa[H]
        ataque = (np.bincount(H, W * GH, n) + np.bincount(A, W * GA, n) + PRIOR_PARTIDOS) / (
            np.bincount(H, W * lam_h / ataque[H], n) + np.bincount(A, W * lam_a / ataque[A], n) + PRIOR_PARTIDOS
        )
        lam_h = mu * localia * ataque[H] * defensa[A]
        lam_a = mu * ataque[A] * defensa[H]
        defensa = (np.bincount(A, W * GH, n) + np.bincount(H, W * GA, n) + PRIOR_PARTIDOS) / (
            np.bincount(A, W * lam_h / defensa[A], n) + np.bincount(H, W * lam_a / defensa[H], n) + PRIOR_PARTIDOS
        )
        lam_h = mu * localia * ataque[H] * defensa[A]
        localia *= float(np.sum(W * GH) / np.sum(W * lam_h))
        ataque /= np.exp(np.mean(np.log(ataque)))
        defensa /= np.exp(np.mean(np.log(defensa)))
        lam_h = mu * localia * ataque[H] * defensa[A]
        lam_a = mu * ataque[A] * defensa[H]
        mu *= float(np.sum(W * (GH + GA)) / np.sum(W * (lam_h + lam_a)))

    lam_h = mu * localia * ataque[H] * defensa[A]
    lam_a = mu * ataque[A] * defensa[H]
    rho = _ajustar_rho(lam_h, lam_a, np.round(GH), np.round(GA), W)
    partidos_por_equipo = np.bincount(H, minlength=n) + np.bincount(A, minlength=n)

    modelo = ModeloDixonColes(indice, ataque, defensa, partidos_por_equipo, localia, mu, rho)
    if len(_cache_modelo) > 256:
        _cache_modelo.clear()
    _cache_modelo[clave] = modelo
    return modelo


def proyectar_xg(
    equipo_local_id: int, equipo_visitante_id: int, liga: str = "", hasta_fecha: datetime | None = None
) -> tuple[float, float] | None:
    """
    Goles esperados (local, visitante) según el modelo Dixon-Coles. Los ids
    son pk de Equipo. Retorna None si a alguno le falta historial suficiente
    -- el predictor se abstiene en vez de inventar un número.

    `hasta_fecha`: ver `_historial_finalizados` -- para backtesting.
    """
    modelo = ajustar_modelo(liga, hasta_fecha)
    if modelo is None:
        return None
    xg = modelo.xg(equipo_local_id, equipo_visitante_id)
    if xg is None:
        return None
    return round(xg[0], 3), round(xg[1], 3)


def rho_dixon_coles(liga: str = "", hasta_fecha: datetime | None = None) -> float:
    """Corrección de marcadores bajos del modelo vigente (0.0 si no hay modelo)."""
    modelo = ajustar_modelo(liga, hasta_fecha)
    return modelo.rho if modelo else 0.0
