"""
Imágenes 1200x675 (formato recomendado para el timeline de X) dibujadas con
Pillow en el servidor: los escudos vienen de dominios externos y en el
navegador "ensuciarían" el canvas al exportar. Paleta Midnight Royal de la app.
"""

from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1200, 675
FUENTES = Path(__file__).resolve().parent.parent / "contenido_assets" / "fonts"

FONDO = (7, 11, 22)
SUPERFICIE = (15, 23, 42)
SUPERFICIE_2 = (24, 34, 56)
TEXTO = (241, 245, 249)
TEXTO_2 = (165, 180, 204)
TEXTO_3 = (100, 116, 139)
INDIGO = (99, 102, 241)
VIOLETA = (139, 92, 246)
CIAN = (34, 211, 238)
ORO = (245, 184, 61)
VERDE = (52, 211, 153)
ROJO = (251, 113, 133)
GRIS = (71, 85, 105)


def _f(nombre: str, tam: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FUENTES / f"{nombre}.ttf"), tam)


def titulo_f(t):
    return _f("Manrope-ExtraBold", t)


def negrita(t):
    return _f("Inter-ExtraBold", t)


def semi(t):
    return _f("Inter-SemiBold", t)


def normal(t):
    return _f("Inter-Regular", t)


# --------------------------------------------------------------------------- utilidades
def _lienzo() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), FONDO)
    # resplandores de marca (índigo arriba-izquierda, violeta arriba-derecha)
    glow = Image.new("RGB", (W, H), FONDO)
    g = ImageDraw.Draw(glow)
    g.ellipse((-250, -330, 650, 330), fill=(32, 30, 90))
    g.ellipse((700, -300, 1500, 260), fill=(48, 26, 92))
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(120)), 0.9)
    return img, ImageDraw.Draw(img)


def _degradado(tam: tuple[int, int], c1=INDIGO, c2=VIOLETA) -> Image.Image:
    w, h = tam
    base = Image.new("RGB", (w, h), c1)
    top = Image.new("RGB", (w, h), c2)
    mask = Image.linear_gradient("L").rotate(90).resize((w, h))
    return Image.composite(top, base, mask)


def _caja(img: Image.Image, xy, radio=22, fill=SUPERFICIE, borde=(36, 48, 74)):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(xy, radio, fill=fill, outline=borde, width=2)


def _pegar_degradado(img: Image.Image, xy, radio=22):
    x0, y0, x1, y1 = xy
    grad = _degradado((x1 - x0, y1 - y0))
    mask = Image.new("L", grad.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *grad.size), radio, fill=255)
    img.paste(grad, (x0, y0), mask)


def _texto_ajustado(d: ImageDraw.ImageDraw, texto: str, fuente, ancho_max: int) -> str:
    if d.textlength(texto, font=fuente) <= ancho_max:
        return texto
    while texto and d.textlength(texto + "…", font=fuente) > ancho_max:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def _iniciales(nombre: str) -> str:
    partes = [p for p in nombre.replace(".", " ").split() if p]
    return (partes[0][0] + partes[-1][0]).upper() if len(partes) > 1 else nombre[:2].upper()


@lru_cache(maxsize=128)
def _bajar_escudo(url: str) -> Image.Image | None:
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "ValueBet-content/1.0"})
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception:  # noqa: BLE001
        return None


def _escudo(img: Image.Image, nombre: str, centro: tuple[int, int], tam: int, logos: dict):
    url = logos.get(nombre, "")
    esc = _bajar_escudo(url) if url else None
    cx, cy = centro
    if esc:
        e = esc.copy()
        e.thumbnail((tam, tam), Image.LANCZOS)
        img.paste(e, (cx - e.width // 2, cy - e.height // 2), e)
        return
    d = ImageDraw.Draw(img)
    d.ellipse((cx - tam // 2, cy - tam // 2, cx + tam // 2, cy + tam // 2), fill=INDIGO)
    f = negrita(int(tam * 0.36))
    d.text((cx, cy), _iniciales(nombre), font=f, fill=TEXTO, anchor="mm")


def _logos(nombres: list[str]) -> dict:
    from data_ingestion.equipos import Resolver

    r = Resolver()
    return {n: r.logo(n) for n in nombres}


def _cabecera(img, d, titulo: str, subtitulo: str = ""):
    d.text((60, 52), "VALUEBET", font=negrita(20), fill=TEXTO_2)
    ancho = d.textlength("VALUEBET", font=negrita(20))
    d.ellipse((60 + ancho + 12, 59, 60 + ancho + 20, 67), fill=VIOLETA)
    d.text((60, 82), titulo, font=titulo_f(46), fill=TEXTO)
    if subtitulo:
        d.text((60, 140), subtitulo, font=semi(22), fill=TEXTO_2)


def _pie(d, texto="Modelo Dixon-Coles · calibrado con resultados reales · 10.000 simulaciones por partido"):
    d.text((60, H - 44), texto, font=normal(17), fill=TEXTO_3)


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


# --------------------------------------------------------------------------- plantillas
def _previa(datos: dict) -> Image.Image:
    img, d = _lienzo()
    _cabecera(img, d, datos["titulo"], datos["subtitulo"])
    filas = datos["filas"][:4]
    logos = _logos([f["local"] for f in filas] + [f["visita"] for f in filas])
    y = 200
    alto = 92
    for f in filas:
        _caja(img, (60, y, W - 60, y + alto - 12))
        _escudo(img, f["local"], (112, y + 40), 50, logos)
        _escudo(img, f["visita"], (172, y + 40), 50, logos)
        d.text((220, y + 14), _texto_ajustado(d, f["pick"], negrita(28), 640), font=negrita(28), fill=TEXTO)
        d.text(
            (220, y + 50),
            _texto_ajustado(d, f"{f['local']} vs {f['visita']}", semi(19), 640),
            font=semi(19),
            fill=TEXTO_3,
        )
        pct = f"{round(f['prob'] * 100)}%"
        _pegar_degradado(img, (W - 250, y + 16, W - 84, y + 64), radio=24)
        d.text((W - 167, y + 40), pct, font=titulo_f(32), fill=TEXTO, anchor="mm")
        y += alto
    _pie(d)
    return img


def _simulacion(datos: dict) -> Image.Image:
    img, d = _lienzo()
    sim, l, v = datos["sim"], datos["local"], datos["visita"]
    n = sim["simulaciones"]
    d.text((60, 52), "VALUEBET", font=negrita(20), fill=TEXTO_2)
    d.text((W - 60, 52), f"{datos['competicion']} · {datos['fecha']}", font=semi(20), fill=TEXTO_2, anchor="ra")
    d.text((W // 2, 120), f"SIMULAMOS EL PARTIDO {n:,} VECES".replace(",", "."), font=titulo_f(40), fill=TEXTO, anchor="mm")

    logos = _logos([l, v])
    _escudo(img, l, (230, 255), 120, logos)
    _escudo(img, v, (W - 230, 255), 120, logos)
    d.text((230, 335), _texto_ajustado(d, l, negrita(26), 340), font=negrita(26), fill=TEXTO, anchor="mm")
    d.text((W - 230, 335), _texto_ajustado(d, v, negrita(26), 340), font=negrita(26), fill=TEXTO, anchor="mm")
    d.text((W // 2, 255), "VS", font=titulo_f(36), fill=TEXTO_3, anchor="mm")

    # barra L/E/V
    x0, x1, yb = 120, W - 120, 385
    total = x1 - x0
    partes = [(sim["victorias_local"], INDIGO), (sim["empates"], GRIS), (sim["victorias_visitante"], CIAN)]
    x = x0
    for i, (veces, color) in enumerate(partes):
        ancho = round(total * veces / n) if i < 2 else x1 - x
        d.rounded_rectangle((x, yb, x + ancho, yb + 54), 14, fill=color)
        if ancho > 90:
            d.text((x + ancho / 2, yb + 27), f"{round(veces / n * 100)}%", font=titulo_f(26), fill=TEXTO, anchor="mm")
        x += ancho
    etiquetas = [(x0, f"Gana {l}: {sim['victorias_local']:,}".replace(",", "."), "la"),
                 (W // 2, f"Empate: {sim['empates']:,}".replace(",", "."), "ma"),
                 (x1, f"Gana {v}: {sim['victorias_visitante']:,}".replace(",", "."), "ra")]
    for xx, t, anchor in etiquetas:
        d.text((xx, yb + 66), _texto_ajustado(d, t, semi(19), 320), font=semi(19), fill=TEXTO_2, anchor=anchor)

    d.text((60, 505), "MARCADORES MÁS REPETIDOS", font=negrita(18), fill=TEXTO_3)
    xm = 60
    for m in sim["marcadores_frecuentes"][:4]:
        _caja(img, (xm, 535, xm + 150, 605), radio=18, fill=SUPERFICIE_2)
        d.text((xm + 75, 558), f"{m['local']}-{m['visitante']}", font=titulo_f(30), fill=TEXTO, anchor="mm")
        d.text((xm + 75, 590), f"{m['veces'] / n * 100:.1f}%", font=semi(17), fill=TEXTO_2, anchor="mm")
        xm += 170
    extra = [
        f"Ambos anotan {round(sim['ambos_anotan'] / n * 100)}%",
        f"+2.5 goles {round(sim['mas_de_2_5'] / n * 100)}%",
    ]
    d.text((W - 60, 552), extra[0], font=negrita(24), fill=TEXTO, anchor="ra")
    d.text((W - 60, 588), extra[1], font=negrita(24), fill=TEXTO, anchor="ra")
    _pie(d)
    return img


def _recap(datos: dict) -> Image.Image:
    img, d = _lienzo()
    _cabecera(img, d, f"¿CÓMO NOS FUE? · {datos['titulo']}")
    s, n = datos["aciertos"], datos["partidos"]
    _pegar_degradado(img, (60, 180, 420, 560), radio=28)
    d.text((240, 300), f"{s}/{n}", font=titulo_f(120), fill=TEXTO, anchor="mm")
    d.text((240, 390), "aciertos en el", font=semi(24), fill=TEXTO, anchor="mm")
    d.text((240, 422), "pronóstico más seguro", font=semi(24), fill=TEXTO, anchor="mm")
    t = datos.get("temporada") or {}
    if t.get("partidos"):
        d.text((240, 495), f"Temporada: {round(t['acierto_seguro'] * 100)}%", font=negrita(26), fill=TEXTO, anchor="mm")
        d.text((240, 527), f"en {t['partidos']} partidos", font=semi(19), fill=TEXTO, anchor="mm")

    y = 180
    for item in datos["detalle"][:8]:
        ok = item["acierto_seguro"]
        color = VERDE if ok else ROJO
        d.ellipse((460, y + 9, 484, y + 33), fill=color)
        d.text((472, y + 21), "✓" if ok else "×", font=negrita(17), fill=FONDO, anchor="mm")
        texto = f"{item['local']} {item['marcador']} {item['visitante']}"
        d.text((500, y + 6), _texto_ajustado(d, texto, semi(22), 640), font=semi(22), fill=TEXTO)
        y += 47
    if datos.get("reconstruido"):
        _pie(d, "Pronósticos calculados solo con partidos anteriores a cada uno (sin datos del futuro) · ValueBet")
    else:
        _pie(d, "Pronósticos publicados antes de cada partido · ValueBet")
    return img


def _tabla(datos: dict) -> Image.Image:
    img, d = _lienzo()
    sub = f"A falta de {datos['faltan']} fechas" if datos.get("faltan") else "Tabla final"
    _cabecera(img, d, f"TABLA · {datos['titulo']}", sub)
    filas = datos["filas"]
    logos = _logos([f["equipo"] for f in filas])
    mitad = (len(filas) + 1) // 2
    for col, grupo in enumerate((filas[:mitad], filas[mitad:])):
        x0 = 60 + col * 555
        y = 190
        for f in grupo:
            campeon = f["equipo"] == datos.get("campeon")
            descenso = f["pos"] > len(filas) - 2
            fondo = (58, 46, 20) if campeon else (60, 22, 36) if descenso else SUPERFICIE
            _caja(img, (x0, y, x0 + 525, y + 48), radio=12, fill=fondo, borde=fondo)
            color_pos = ORO if campeon else ROJO if descenso else TEXTO_2
            d.text((x0 + 30, y + 24), str(f["pos"]), font=negrita(20), fill=color_pos, anchor="mm")
            _escudo(img, f["equipo"], (x0 + 74, y + 24), 32, logos)
            d.text((x0 + 104, y + 24), _texto_ajustado(d, f["equipo"], semi(21), 290), font=semi(21), fill=TEXTO, anchor="lm")
            d.text((x0 + 440, y + 24), f"{f['dif']:+d}" if f["dif"] else "0", font=semi(18), fill=TEXTO_3, anchor="rm")
            d.text((x0 + 505, y + 24), str(f["pts"]), font=negrita(24), fill=ORO if campeon else TEXTO, anchor="rm")
            y += 54
    _pie(d, "Pts · diferencia de gol · Fuente: ESPN · ValueBet")
    return img


def _racha(datos: dict) -> Image.Image:
    img, d = _lienzo()
    _cabecera(img, d, "¿QUIÉN LLEGA MEJOR AL CIERRE?", "Últimos 5 partidos de liga")
    equipos = [datos["mejor"], datos["peor"]]
    logos = _logos([e["equipo"] for e in equipos])
    for i, (e, etiqueta, color) in enumerate(zip(equipos, ("EN RACHA", "EN CRISIS"), (VERDE, ROJO))):
        x0 = 60 + i * 555
        _caja(img, (x0, 200, x0 + 525, 590), radio=26)
        d.text((x0 + 262, 240), etiqueta, font=negrita(22), fill=color, anchor="mm")
        _escudo(img, e["equipo"], (x0 + 262, 335), 120, logos)
        d.text((x0 + 262, 425), _texto_ajustado(d, e["equipo"], titulo_f(32), 470), font=titulo_f(32), fill=TEXTO, anchor="mm")
        xr = x0 + 262 - (len(e["forma"]) * 66 - 10) // 2
        for r in e["forma"]:
            c = {"G": VERDE, "E": GRIS, "P": ROJO}[r]
            d.rounded_rectangle((xr, 470, xr + 56, 526), 12, fill=c)
            d.text((xr + 28, 498), r, font=titulo_f(28), fill=TEXTO, anchor="mm")
            xr += 66
        d.text((x0 + 262, 556), f"{e['pts']} de 15 puntos", font=semi(20), fill=TEXTO_2, anchor="mm")
    _pie(d, "G = ganó · E = empató · P = perdió · ValueBet")
    return img


def _copa(datos: dict) -> Image.Image:
    img, d = _lienzo()
    _cabecera(img, d, datos["titulo"], "¿Quién llega a la final?")
    cruces = datos["cruces"][:2]
    logos = _logos([c["local"] for c in cruces] + [c["visita"] for c in cruces])
    for i, c in enumerate(cruces):
        x0 = 60 + i * 555
        _caja(img, (x0, 200, x0 + 525, 590), radio=26)
        _escudo(img, c["local"], (x0 + 140, 300), 110, logos)
        _escudo(img, c["visita"], (x0 + 385, 300), 110, logos)
        d.text((x0 + 262, 300), "VS", font=titulo_f(30), fill=TEXTO_3, anchor="mm")
        d.text((x0 + 140, 380), _texto_ajustado(d, c["local"], negrita(20), 235), font=negrita(20), fill=TEXTO, anchor="mm")
        d.text((x0 + 385, 380), _texto_ajustado(d, c["visita"], negrita(20), 235), font=negrita(20), fill=TEXTO, anchor="mm")
        if c.get("prob"):
            p = c["prob"]
            d.text((x0 + 262, 440), f"Partido de ida · {c.get('fecha', '')}", font=semi(19), fill=TEXTO_2, anchor="mm")
            xb, ancho = x0 + 40, 445
            x = xb
            for j, (k, color) in enumerate((("LOCAL", INDIGO), ("EMPATE", GRIS), ("VISITANTE", CIAN))):
                a = round(ancho * p[k]) if j < 2 else xb + ancho - x
                d.rounded_rectangle((x, 470, x + a, 520), 12, fill=color)
                if a > 60:
                    d.text((x + a / 2, 495), f"{round(p[k] * 100)}%", font=negrita(22), fill=TEXTO, anchor="mm")
                x += a
            d.text((xb, 535), "Local", font=semi(16), fill=TEXTO_3)
            d.text((xb + ancho / 2, 535), "Empate", font=semi(16), fill=TEXTO_3, anchor="ma")
            d.text((xb + ancho, 535), "Visita", font=semi(16), fill=TEXTO_3, anchor="ra")
    _pie(d)
    return img


PLANTILLAS = {
    "previa": _previa,
    "simulacion": _simulacion,
    "recap": _recap,
    "tabla": _tabla,
    "racha": _racha,
    "copa": _copa,
}


def render(datos: dict) -> bytes:
    return _png(PLANTILLAS[datos["tipo"]](datos))
