"""
Genera las piezas de contenido para X a partir de los datos del sistema.

Cada pieza: {id, categoria, titulo, texto, imagen(bool), datos(dict para la imagen)}.
Categorías: previa | recap | simulacion | tablas
Tono: cercano, chileno, con emojis. Los textos respetan el límite de 280
caracteres de X (los emojis cuentan doble, se deja margen).
"""

from __future__ import annotations

from django.utils import timezone


HASHTAG_LIGA = "#CampeonatoNacional"
HASHTAG_COPA = "#CopaChile"
LIMITE = 270

PICK_TEXTO = {"1X": "{l} o empate", "X2": "{v} o empate", "12": "No hay empate"}
RESULTADO_TEXTO = {"LOCAL": "gana {l}", "EMPATE": "empate", "VISITANTE": "gana {v}"}


def _miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _pct(p: float) -> str:
    return f"{round(p * 100)}%"


def _hashtag(competicion: str) -> str:
    return HASHTAG_COPA if "Copa Chile" in competicion else HASHTAG_LIGA


def _nombre_ronda(competicion: str, etiqueta: str) -> str:
    return etiqueta if competicion == "Liga de Primera" else f"{competicion} · {etiqueta}"


def largo_x(texto: str) -> int:
    """Largo como lo cuenta X: emojis y símbolos fuera del plano básico cuentan 2."""
    return sum(2 if ord(c) > 0x2000 and c not in "—–·" else 1 for c in texto)


def _recortar(texto: str) -> str:
    """Asegura el límite de X quitando líneas de detalle desde el final del bloque central."""
    lineas = texto.split("\n")
    while largo_x("\n".join(lineas)) > LIMITE and len(lineas) > 4:
        # quita la penúltima línea de contenido (conserva cierre y hashtags)
        del lineas[-3]
    return "\n".join(lineas)


def _pick(p: dict, partido: dict) -> str:
    l, v = partido["equipo_local"]["nombre"], partido["equipo_visitante"]["nombre"]
    return PICK_TEXTO.get(p["seleccion"], p["seleccion"]).format(l=l, v=v)


def _rango(fechas) -> str:
    fmt = lambda d: timezone.localtime(d).strftime("%d/%m")  # noqa: E731
    ini, fin = fmt(min(fechas)), fmt(max(fechas))
    return ini if ini == fin else f"{ini} al {fin}"


# --------------------------------------------------------------------------- nombres
_NOMBRES: dict[str, str] = {}


def _cargar_nombres() -> None:
    """Nombre oficial (con tildes, sin abreviar) por nombre normalizado, desde la tabla de ESPN."""
    from data_ingestion.equipos import normalizar
    from db_models.models import TablaCompeticion

    _NOMBRES.clear()
    for t in TablaCompeticion.objects.filter(slug="liga"):
        for g in t.datos.get("grupos", []):
            for f in g.get("filas", []):
                _NOMBRES[normalizar(f["equipo"])] = f["equipo"]


# Correcciones a nombres que la fuente publica sin tilde.
_TILDES = {"Deportes Concepcion": "Deportes Concepción", "Union La Calera": "Unión La Calera"}


def bonito(nombre: str) -> str:
    from data_ingestion.equipos import normalizar

    n = _NOMBRES.get(normalizar(nombre), nombre)
    return _TILDES.get(n, n)


def _bonitos(partido: dict) -> dict:
    """Copia del partido serializado con nombres oficiales para publicar."""
    p = dict(partido)
    for k in ("equipo_local", "equipo_visitante"):
        p[k] = {**partido[k], "nombre": bonito(partido[k]["nombre"])}
    return p


# --------------------------------------------------------------------------- datos base
def _pronosticos_proximos() -> list[dict]:
    from api.views import PartidoSerializer  # serializer compartido con /api/pronosticos/
    from ml_models.predictor import MatchPredictor
    from ml_models.pronosticos import calcular_pronostico, proximos_partidos

    predictor = MatchPredictor()
    salida = []
    for partido in proximos_partidos():
        pron = calcular_pronostico(partido, predictor)
        if pron:
            salida.append({"partido": _bonitos(PartidoSerializer(partido).data), "_fecha": partido.fecha_hora, **pron})
    return salida


def _grupos(pronosticos: list[dict]) -> list[dict]:
    grupos: dict[tuple, dict] = {}
    for x in pronosticos:
        clave = (x["competicion"], x["etiqueta_fecha"])
        grupos.setdefault(clave, {"competicion": clave[0], "etiqueta": clave[1], "partidos": []})["partidos"].append(x)
    return sorted(grupos.values(), key=lambda g: min(p["_fecha"] for p in g["partidos"]))


# --------------------------------------------------------------------------- piezas
def _pieza_previa(grupo: dict) -> dict:
    comp, etiqueta = grupo["competicion"], grupo["etiqueta"]
    top = sorted(grupo["partidos"], key=lambda x: -x["doble_oportunidad"]["probabilidad"])[:4]
    nombre = _nombre_ronda(comp, etiqueta)
    lineas = [f"🔥 Se viene la {nombre} {_hashtag(comp)}" if comp == "Liga de Primera" else f"🔥 Se viene la {nombre}", ""]
    lineas.append("Lo más seguro según nuestro modelo 👇")
    for x in top:
        lineas.append(f"🔒 {_pick(x['doble_oportunidad'], x['partido'])} — {_pct(x['doble_oportunidad']['probabilidad'])}")
    lineas += ["", "¿Con cuál se la juegan? 👀"]
    if comp != "Liga de Primera":
        lineas.append(_hashtag(comp))
    texto = _recortar("\n".join(lineas))
    return {
        "id": f"previa|{comp}|{etiqueta}",
        "categoria": "previa",
        "titulo": f"Previa · {nombre}",
        "texto": texto,
        "imagen": True,
        "datos": {
            "tipo": "previa",
            "titulo": f"PREVIA · {nombre.upper()}",
            "subtitulo": f"{_rango([x['_fecha'] for x in grupo['partidos']])} · lo más seguro según el modelo",
            "filas": [
                {
                    "local": x["partido"]["equipo_local"]["nombre"],
                    "visita": x["partido"]["equipo_visitante"]["nombre"],
                    "pick": _pick(x["doble_oportunidad"], x["partido"]),
                    "prob": x["doble_oportunidad"]["probabilidad"],
                }
                for x in top
            ],
        },
    }


def _pieza_simulacion(x: dict) -> dict:
    p, sim = x["partido"], x["simulacion"]
    l, v = p["equipo_local"]["nombre"], p["equipo_visitante"]["nombre"]
    n = sim["simulaciones"]
    top = sim["marcadores_frecuentes"][0]
    lineas = [
        f"🎲 Simulamos {l} vs {v} {_miles(n)} veces:",
        "",
        f"🏠 {l} ganó {_miles(sim['victorias_local'])}",
        f"🤝 Empate {_miles(sim['empates'])}",
        f"✈️ {v} ganó {_miles(sim['victorias_visitante'])}",
        "",
        f"Marcador más repetido: {top['local']}-{top['visitante']} 🔥",
        f"{_hashtag(x['competicion'])}",
    ]
    return {
        "id": f"sim|{p['id']}",
        "categoria": "simulacion",
        "titulo": f"Simulación · {l} vs {v}",
        "texto": _recortar("\n".join(lineas)),
        "imagen": True,
        "datos": {
            "tipo": "simulacion",
            "competicion": _nombre_ronda(x["competicion"], x["etiqueta_fecha"]),
            "fecha": timezone.localtime(x["_fecha"]).strftime("%d/%m · %H:%M"),
            "local": l,
            "visita": v,
            "sim": sim,
        },
    }


def _pieza_recap(g: dict, temporada: dict) -> dict:
    nombre = _nombre_ronda(g["competicion"], g["etiqueta_fecha"])
    s, n = g["aciertos_seguro"], g["partidos"]
    emoji = "✅" if s / n >= 0.6 else "😬"
    lineas = [f"📊 {nombre}: le achuntamos a {s} de {n} con el pronóstico más seguro {emoji}", ""]
    if temporada.get("partidos"):
        lineas.append(
            f"En la temporada vamos con {_pct(temporada['acierto_seguro'])} de acierto en {temporada['partidos']} partidos 📈"
        )
        lineas.append("")
    lineas += ["Seguimos 💪", _hashtag(g["competicion"])]
    return {
        "id": f"recap|{g['competicion']}|{g['etiqueta_fecha']}|{g['temporada']}",
        "categoria": "recap",
        "titulo": f"Recap · {nombre}",
        "texto": _recortar("\n".join(lineas)),
        "imagen": True,
        "datos": {
            "tipo": "recap",
            "titulo": nombre.upper(),
            "aciertos": s,
            "partidos": n,
            "temporada": temporada,
            "detalle": g["detalle"][:8],
            "reconstruido": g["reconstruido"],
        },
    }


def _pieza_tabla(tabla) -> dict | None:
    filas = (tabla.datos.get("grupos") or [{}])[0].get("filas", [])
    if not filas:
        return None
    campeon = tabla.datos.get("campeon")
    pj_max = max(f["pj"] for f in filas)
    total = 2 * (len(filas) - 1)
    faltan = max(total - pj_max, 0)
    cab = f"🏆 Así va la tabla{f' a falta de {faltan} fechas' if faltan else ''} {HASHTAG_LIGA}"
    lineas = [cab, ""]
    medallas = ["🥇", "🥈", "🥉"]
    for f in filas[:5]:
        marca = medallas[f["pos"] - 1] if f["pos"] <= 3 else f"{f['pos']}."
        extra = " (campeón 🏆)" if f["equipo"] == campeon else ""
        lineas.append(f"{marca} {f['equipo']} {f['pts']} pts{extra}")
    lineas += ["", "⬇️ Abajo: " + " y ".join(f"{f['equipo']} ({f['pts']})" for f in filas[-2:])]
    return {
        "id": "tabla|liga",
        "categoria": "tablas",
        "titulo": "Tabla de posiciones · Liga",
        "texto": _recortar("\n".join(lineas)),
        "imagen": True,
        "datos": {"tipo": "tabla", "titulo": f"LIGA DE PRIMERA {tabla.temporada}", "filas": filas, "campeon": campeon, "faltan": faltan},
    }


def _pieza_racha(tabla) -> dict | None:
    filas = (tabla.datos.get("grupos") or [{}])[0].get("filas", [])
    con_forma = [f for f in filas if f.get("forma")]
    if not con_forma:
        return None

    def puntos(f):
        return sum(3 if r == "G" else 1 if r == "E" else 0 for r in f["forma"])

    mejor = max(con_forma, key=puntos)
    peor = min(con_forma, key=puntos)
    fm = lambda f: "".join({"G": "✅", "E": "➖", "P": "❌"}[r] for r in f["forma"])  # noqa: E731
    lineas = [
        "📈 ¿Quién llega mejor al cierre del torneo?",
        "",
        f"🔥 {mejor['equipo']}: {fm(mejor)} ({puntos(mejor)} de 15 pts)",
        f"🥶 {peor['equipo']}: {fm(peor)} ({puntos(peor)} de 15 pts)",
        "",
        "Últimos 5 partidos 👆",
        HASHTAG_LIGA,
    ]
    return {
        "id": "racha|liga",
        "categoria": "tablas",
        "titulo": "Dato · rachas de los últimos 5",
        "texto": _recortar("\n".join(lineas)),
        "imagen": True,
        "datos": {
            "tipo": "racha",
            "mejor": {"equipo": mejor["equipo"], "forma": mejor["forma"], "pts": puntos(mejor)},
            "peor": {"equipo": peor["equipo"], "forma": peor["forma"], "pts": puntos(peor)},
        },
    }


def _pieza_copa(tabla, pronosticos: list[dict]) -> dict | None:
    llaves = [ll for ll in tabla.datos.get("llaves", []) if not ll.get("ganador")]
    if not llaves:
        return None
    ronda = llaves[0]["ronda"]
    from data_ingestion.equipos import normalizar

    por_cruce = {
        frozenset(normalizar(x["partido"][k]["nombre"]) for k in ("equipo_local", "equipo_visitante")): x
        for x in sorted(pronosticos, key=lambda x: x["_fecha"], reverse=True)
        if x["competicion"] == "Copa Chile"
    }  # queda el partido más próximo (ida) de cada cruce
    lineas = [f"🏆 {ronda} de la {HASHTAG_COPA} 👇", ""]
    cruces = []
    for ll in llaves:
        x = por_cruce.get(frozenset(normalizar(n) for n in (ll["local"], ll["visitante"])))
        if x:
            fav = max(("LOCAL", "VISITANTE"), key=lambda s: x["probabilidades"][s])
            nombre_fav = x["partido"]["equipo_local" if fav == "LOCAL" else "equipo_visitante"]["nombre"]
            lineas.append(
                f"⚔️ {x['partido']['equipo_local']['nombre']} vs {x['partido']['equipo_visitante']['nombre']}"
                f" (ida): {nombre_fav} {_pct(x['probabilidades'][fav])}"
            )
        else:
            lineas.append(f"⚔️ {bonito(ll['local'])} vs {bonito(ll['visitante'])}")
        cruces.append(
            {
                "local": x["partido"]["equipo_local"]["nombre"] if x else bonito(ll["local"]),
                "visita": x["partido"]["equipo_visitante"]["nombre"] if x else bonito(ll["visitante"]),
                "prob": x["probabilidades"] if x else None,
                "fecha": timezone.localtime(x["_fecha"]).strftime("%d/%m") if x else "",
            }
        )
    lineas += ["", "¿Quién llega a la final? 👀"]
    return {
        "id": "copa|chile",
        "categoria": "tablas",
        "titulo": f"Copa Chile · {ronda}",
        "texto": _recortar("\n".join(lineas)),
        "imagen": True,
        "datos": {"tipo": "copa", "titulo": f"COPA CHILE · {ronda.upper()}", "cruces": cruces},
    }


def generar_contenido() -> list[dict]:
    from db_models.models import TablaCompeticion
    from ml_models.pronosticos import historial_por_fecha, resumen_temporada

    _cargar_nombres()
    piezas: list[dict] = []
    pronosticos = _pronosticos_proximos()
    grupos = _grupos(pronosticos)

    for g in grupos[:2]:
        piezas.append(_pieza_previa(g))

    temporada = resumen_temporada(str(timezone.localdate().year))
    historial = historial_por_fecha(limite=6)
    recap = next((g for g in historial if g["competicion"] == "Liga de Primera" and g["partidos"] >= 4), None)
    recap = recap or (historial[0] if historial else None)
    if recap:
        recap["detalle"] = [{**d, "local": bonito(d["local"]), "visitante": bonito(d["visitante"])} for d in recap["detalle"]]
        piezas.append(_pieza_recap(recap, temporada))

    if grupos:
        destacados = sorted(grupos[0]["partidos"], key=lambda x: -max(x["probabilidades"].values()))
        piezas += [_pieza_simulacion(x) for x in destacados]

    liga = TablaCompeticion.objects.filter(slug="liga").first()
    if liga:
        piezas += [p for p in (_pieza_tabla(liga), _pieza_racha(liga)) if p]
    copa = TablaCompeticion.objects.filter(slug="copa_chile").first()
    if copa:
        p = _pieza_copa(copa, pronosticos)
        if p:
            piezas.append(p)
    return piezas
