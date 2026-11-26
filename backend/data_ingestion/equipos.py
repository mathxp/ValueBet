"""
Resolución de nombres de equipos entre fuentes (base de datos / api-football,
ESPN y Wikipedia), que escriben el mismo club de formas distintas:
"Colo Colo" / "Colo-Colo", "U. Catolica" / "Universidad Católica", etc.
"""

from __future__ import annotations

import logging
import unicodedata

from db_models.models import Equipo, LogoEquipo

logger = logging.getLogger(__name__)

# nombre normalizado de la fuente -> nombre normalizado canónico (el de Equipo).
ALIAS = {
    "audax italiano": "a italiano",
    "universidad catolica": "u catolica",
    "everton": "everton de vina",
    "everton cd": "everton de vina",
    "la serena": "d la serena",
    "deportes la serena": "d la serena",
    "deportes concepcion": "concepcion",
    "antofagasta": "deportes antofagasta",
    "puerto montt": "deportes puerto montt",
    "santa cruz": "deportes santa cruz",
}


def normalizar(nombre: str) -> str:
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    s = s.replace("-", " ").replace(".", "").replace("'", "")
    s = " ".join(s.split())
    return ALIAS.get(s, s)


class Resolver:
    """Índice en memoria de equipos y escudos (una consulta a la base por uso)."""

    def __init__(self):
        self.equipos = {normalizar(e.nombre): e for e in Equipo.objects.all()}
        self.logos = {
            l.nombre: l.logo_url for l in LogoEquipo.objects.all()
        }

    def equipo(self, nombre: str) -> Equipo | None:
        return self.equipos.get(normalizar(nombre))

    def logo(self, nombre: str) -> str:
        n = normalizar(nombre)
        equipo = self.equipos.get(n)
        if equipo and equipo.logo_url:
            return equipo.logo_url
        return self.logos.get(n, "")

    def guardar_logo(self, nombre: str, url: str) -> None:
        n = normalizar(nombre)
        if url and self.logos.get(n) != url:
            LogoEquipo.objects.update_or_create(nombre=n, defaults={"logo_url": url})
            self.logos[n] = url
        equipo = self.equipos.get(n)
        if url and equipo and not equipo.logo_url:
            equipo.logo_url = url
            equipo.save(update_fields=["logo_url", "actualizado_en"])

    def buscar_logos_faltantes(self, nombres: list[str], max_busquedas: int = 15) -> int:
        """Busca en api-football (1 request c/u) los escudos que nunca se buscaron."""
        from data_ingestion.api_clients.football_api import ApiFootballClient, ApiFootballError

        pendientes = [n for n in dict.fromkeys(nombres) if not self.logo(n) and normalizar(n) not in self.logos]
        if not pendientes:
            return 0
        try:
            client = ApiFootballClient()
        except ApiFootballError:
            return 0
        encontrados = 0
        for nombre in pendientes[:max_busquedas]:
            url = ""
            try:
                # La búsqueda solo acepta letras/espacios y >= 3 caracteres.
                termino = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
                termino = "".join(ch for ch in termino if ch.isalnum() or ch == " ").strip()
                terminos = [termino]
                for prefijo in ("Deportes ", "Club ", "CD "):
                    if termino.startswith(prefijo):
                        terminos.append(termino[len(prefijo):])
                for t in terminos:
                    url = next(
                        (r["team"].get("logo", "") for r in client.search_teams(t) if r["team"].get("country") == "Chile"),
                        "",
                    )
                    if url:
                        break
            except Exception as exc:  # noqa: BLE001
                logger.warning("Búsqueda de escudo falló para %s: %s", nombre, exc)
                continue
            n = normalizar(nombre)
            LogoEquipo.objects.update_or_create(nombre=n, defaults={"logo_url": url})
            self.logos[n] = url
            encontrados += bool(url)
        return encontrados
