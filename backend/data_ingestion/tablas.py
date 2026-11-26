"""
Tablas de posiciones de la Liga de Primera, Copa Chile y Copa de la Liga.

Fuentes (gratis, sin API key):
- Liga:   API pública de ESPN (standings de chi.1) -- se actualiza minutos
          después de cada partido.
- Copas:  Wikipedia en español (fase de grupos + llaves). api-football no
          entrega tablas de la temporada en curso en el plan gratuito y ESPN
          no cubre la Copa de la Liga.

Todo se guarda en TablaCompeticion.datos (JSON) y solo se muestra en la
página "Tablas" del frontend; no alimenta al modelo de predicción.
"""

from __future__ import annotations

import logging
import re

import requests
from bs4 import BeautifulSoup
from django.utils import timezone

from db_models.models import TablaCompeticion

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "ValueBet-standings/1.0 (personal, non-commercial)"}
TIMEOUT = 20

ESPN_STANDINGS = "https://site.api.espn.com/apis/v2/sports/soccer/{slug}/standings"
WIKI_API = "https://es.wikipedia.org/w/api.php"
WIKI_PAGE = "https://es.wikipedia.org/wiki/{page}"

COMPETICIONES = [
    {"slug": "liga", "nombre": "Liga de Primera", "orden": 1, "espn": "chi.1"},
    {"slug": "copa_chile", "nombre": "Copa Chile", "orden": 2, "wiki": "Copa_Chile_{year}"},
    {"slug": "copa_liga", "nombre": "Copa de la Liga", "orden": 3, "wiki": "Copa_de_la_Liga_de_Chile_{year}"},
]


# --------------------------------------------------------------------------- ESPN
def tabla_espn(slug: str) -> tuple[dict, str, str]:
    """Devuelve (datos, temporada, url_fuente) de los standings de ESPN."""
    resp = requests.get(ESPN_STANDINGS.format(slug=slug), headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    grupos = []
    temporada = ""
    for child in data.get("children") or [data]:
        standings = child.get("standings", {})
        temporada = str(standings.get("season") or temporada)
        filas = []
        for entry in standings.get("entries", []):
            s = {x["name"]: x.get("value") for x in entry.get("stats", [])}
            filas.append(
                {
                    "pos": int(s.get("rank") or 0),
                    "equipo": entry["team"]["displayName"],
                    "pts": int(s.get("points") or 0),
                    "pj": int(s.get("gamesPlayed") or 0),
                    "g": int(s.get("wins") or 0),
                    "e": int(s.get("ties") or 0),
                    "p": int(s.get("losses") or 0),
                    "gf": int(s.get("pointsFor") or 0),
                    "gc": int(s.get("pointsAgainst") or 0),
                    "dif": int(s.get("pointDifferential") or 0),
                    "nota": (entry.get("note") or {}).get("description", ""),
                    "logo_espn": ((entry["team"].get("logos") or [{}])[0]).get("href", ""),
                }
            )
        filas.sort(key=lambda f: f["pos"])
        nombre = child.get("name", "") if data.get("children") and len(data["children"]) > 1 else ""
        grupos.append({"nombre": nombre, "filas": filas})

    datos = {"grupos": grupos, "llaves": [], "campeon": campeon_matematico(grupos)}
    return datos, temporada, f"https://www.espn.cl/futbol/posiciones/_/liga/{slug}"


def campeon_matematico(grupos: list[dict]) -> str | None:
    """
    Liga todos contra todos a dos ruedas: el líder es campeón si ni siquiera
    ganando todo lo que le queda el segundo puede alcanzarlo.
    """
    if len(grupos) != 1 or len(grupos[0]["filas"]) < 2:
        return None
    filas = grupos[0]["filas"]
    partidos_totales = 2 * (len(filas) - 1)
    lider, segundo = filas[0], filas[1]
    maximo_segundo = segundo["pts"] + 3 * max(partidos_totales - segundo["pj"], 0)
    return lider["equipo"] if lider["pts"] > maximo_segundo else None


# ---------------------------------------------------------------------- Wikipedia
_NUM = re.compile(r"^[+\-−–]?\d+$")


def _texto(celda) -> str:
    for sup in celda.find_all("sup"):
        sup.decompose()
    return celda.get_text(" ", strip=True).replace("\xa0", " ")


def _entero(valor: str) -> int:
    valor = valor.replace("−", "-").replace("–", "-").replace("+", "").strip()
    try:
        return int(valor)
    except ValueError:
        return 0


def _es_tabla_posiciones(cabecera: list[str]) -> bool:
    return "Pos." in cabecera and "Pts." in cabecera and "Equipo" in cabecera


def _parsear_grupo(tabla, cabecera: list[str]) -> list[dict]:
    idx = {nombre: i for i, nombre in enumerate(cabecera)}
    filas = []
    for tr in tabla.find_all("tr")[1:]:
        celdas = [_texto(c) for c in tr.find_all(["th", "td"])]
        if len(celdas) < 10 or not _NUM.match(celdas[idx["Pos."]]):
            continue

        def col(nombre):
            i = idx.get(nombre)
            return celdas[i] if i is not None and i < len(celdas) else ""

        nota = col("Clasificación") if len(celdas) == len(cabecera) else ""
        filas.append(
            {
                "pos": _entero(col("Pos.")),
                "equipo": re.sub(r"\s*\([A-Z]\)$", "", col("Equipo")),
                "pts": _entero(col("Pts.")),
                "pj": _entero(col("PJ")),
                "g": _entero(col("G")),
                "e": _entero(col("E")),
                "p": _entero(col("P")),
                "gf": _entero(col("GF")),
                "gc": _entero(col("GC")),
                "dif": _entero(col("Dif.")),
                "nota": nota,
            }
        )
    return filas


def _nombre_ronda(texto: str) -> str:
    t = texto.replace(" ", "").lower()
    if t.startswith("16"):
        return "Dieciseisavos de final"
    if t.startswith("8"):
        return "Octavos de final"
    if t.startswith("4"):
        return "Cuartos de final"
    return texto.strip()


def _fila_llave(celdas: list[str]) -> dict | None:
    """['12', 'Coquimbo Unido', '2', '2', '4'] -> equipo + marcadores."""
    for i, c in enumerate(celdas):
        if c and not _NUM.match(c) and not re.match(r"^\(\d+\)$", c):
            resto = " ".join(celdas[i + 1:])
            penales = re.findall(r"\((\d+)\)", resto)
            goles = [int(x) for x in re.findall(r"(?<!\()\b\d+\b(?!\))", resto)]
            return {"equipo": c, "goles": goles, "penales": int(penales[-1]) if penales else None}
    return None


def _parsear_llaves(tabla) -> list[dict]:
    filas = tabla.find_all("tr")
    rondas = [_nombre_ronda(_texto(c)) for c in filas[0].find_all(["th", "td"]) if _texto(c)]

    equipos = []
    for tr in filas[1:]:
        celdas = [_texto(c) for c in tr.find_all(["th", "td"])]
        fila = _fila_llave([c for c in celdas if c])
        if fila:
            equipos.append(fila)

    cruces = [equipos[i:i + 2] for i in range(0, len(equipos) - 1, 2)]
    apariciones: dict[str, int] = {}
    for a, b in cruces:
        apariciones[a["equipo"]] = apariciones.get(a["equipo"], 0) + 1
        apariciones[b["equipo"]] = apariciones.get(b["equipo"], 0) + 1

    llaves = []
    for a, b in cruces:
        # Todos arrancan en la primera ronda del cuadro, así que el eliminado
        # jugó exactamente hasta la ronda de este cruce: ronda = min(apariciones).
        # (El orden de las filas en Wikipedia no sigue las rondas.)
        n = min(apariciones[a["equipo"]], apariciones[b["equipo"]])
        ronda = rondas[n - 1] if 0 < n <= len(rondas) else f"Ronda {n}"
        jugado = bool(a["goles"]) and bool(b["goles"])
        ganador = None
        if jugado:
            ga, gb = a["goles"][-1], b["goles"][-1]
            if ga != gb:
                ganador = a["equipo"] if ga > gb else b["equipo"]
            elif a["penales"] is not None and b["penales"] is not None:
                ganador = a["equipo"] if a["penales"] > b["penales"] else b["equipo"]
        detalle = ""
        if len(a["goles"]) > 1:
            detalle = ", ".join(f"{x}-{y}" for x, y in zip(a["goles"][:-1], b["goles"][:-1]))
        if a["penales"] is not None and b["penales"] is not None:
            detalle = (detalle + f" (pen. {a['penales']}-{b['penales']})").strip()
        llaves.append(
            {
                "ronda": ronda,
                "orden_ronda": n,
                "local": a["equipo"],
                "visitante": b["equipo"],
                "global_local": a["goles"][-1] if jugado else None,
                "global_visitante": b["goles"][-1] if jugado else None,
                "detalle": detalle,
                "ganador": ganador,
            }
        )
    llaves.sort(key=lambda ll: ll["orden_ronda"], reverse=True)
    return llaves


def tabla_wikipedia(pagina: str) -> tuple[dict, str]:
    resp = requests.get(
        WIKI_API,
        params={"action": "parse", "page": pagina, "prop": "text", "format": "json", "formatversion": 2},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "error" in payload:
        raise ValueError(f"Wikipedia: {payload['error'].get('info')}")

    sopa = BeautifulSoup(payload["parse"]["text"], "html.parser")
    grupos, llaves = [], []
    for tabla in sopa.find_all("table"):
        if tabla.find("table"):  # contenedor de otra tabla (el cuadro viene anidado)
            continue
        primera = tabla.find("tr")
        if not primera:
            continue
        cabecera = [_texto(c) for c in primera.find_all(["th", "td"])]
        if _es_tabla_posiciones(cabecera):
            titulo = tabla.find_previous(["h3", "h2"])
            grupos.append({"nombre": _texto(titulo) if titulo else "", "filas": _parsear_grupo(tabla, cabecera)})
        elif "Final" in cabecera and not llaves:
            llaves = _parsear_llaves(tabla)

    final = next((ll for ll in llaves if ll["ronda"] == "Final"), None)
    datos = {"grupos": grupos, "llaves": llaves, "campeon": final["ganador"] if final else None}
    return datos, WIKI_PAGE.format(page=pagina)


# ----------------------------------------------------------------------- orquestador
def _forma(equipo, temporada: str) -> list[str]:
    """Últimos 5 resultados de liga (más reciente al final): G / E / P."""
    from django.db.models import Q

    from db_models.models import Partido

    partidos = (
        Partido.objects.filter(
            Q(equipo_local=equipo) | Q(equipo_visitante=equipo),
            temporada=temporada,
            estado=Partido.Estado.FINALIZADO,
        )
        .order_by("-fecha_hora")[:5]
    )
    forma = []
    for p in reversed(list(partidos)):
        gl, gv = p.resultado.get("local"), p.resultado.get("visitante")
        if gl is None or gv is None:
            continue
        propios, rivales = (gl, gv) if p.equipo_local_id == equipo.id else (gv, gl)
        forma.append("G" if propios > rivales else "E" if propios == rivales else "P")
    return forma


def _enriquecer(datos: dict, temporada: str, es_liga: bool) -> None:
    """Guarda escudos nuevos, busca los que faltan y agrega la forma (solo liga)."""
    from data_ingestion.equipos import Resolver

    resolver = Resolver()
    nombres = []
    for grupo in datos["grupos"]:
        for fila in grupo["filas"]:
            resolver.guardar_logo(fila["equipo"], fila.pop("logo_espn", ""))
            nombres.append(fila["equipo"])
    for llave in datos["llaves"]:
        nombres += [llave["local"], llave["visitante"]]
    resolver.buscar_logos_faltantes(nombres)

    if es_liga:
        for grupo in datos["grupos"]:
            for fila in grupo["filas"]:
                equipo = resolver.equipo(fila["equipo"])
                fila["forma"] = _forma(equipo, temporada) if equipo else []


def actualizar_tablas() -> dict[str, str]:
    """Refresca las 3 competiciones. Si una fuente falla, deja la última versión guardada."""
    year = timezone.localdate().year
    resultado = {}
    for comp in COMPETICIONES:
        try:
            if "espn" in comp:
                datos, temporada, fuente = tabla_espn(comp["espn"])
            else:
                datos, fuente = tabla_wikipedia(comp["wiki"].format(year=year))
                temporada = str(year)
            if not datos["grupos"] and not datos["llaves"]:
                raise ValueError("la fuente no trajo tablas")
            _enriquecer(datos, temporada or str(year), es_liga="espn" in comp)
            TablaCompeticion.objects.update_or_create(
                slug=comp["slug"],
                defaults={
                    "nombre": comp["nombre"],
                    "temporada": temporada or str(year),
                    "orden": comp["orden"],
                    "datos": datos,
                    "fuente": fuente,
                },
            )
            resultado[comp["slug"]] = "ok"
        except Exception as exc:  # noqa: BLE001 -- una fuente caída no debe romper el pipeline
            logger.warning("No se pudo actualizar %s: %s", comp["slug"], exc)
            resultado[comp["slug"]] = f"error: {exc}"
    return resultado
