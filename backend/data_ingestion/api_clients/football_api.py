"""
Cliente para api-football.com (https://www.api-football.com/).

La versión gratuita tiene límites estrictos: 100 requests/día y ~10/minuto.
Este cliente aplica un throttle simple en memoria de proceso para no quemar
la cuota diaria de golpe; para un despliegue multi-worker real, ese contador
debería vivir en Redis en vez de en memoria local.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any

import requests
from django.conf import settings


class ApiFootballError(Exception):
    """Error de comunicación o de cuota con api-football.com."""


class ApiFootballClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or settings.API_FOOTBALL_KEY
        self.base_url = (base_url or settings.API_FOOTBALL_BASE_URL).rstrip("/")
        self._rate_limit_per_minute = settings.API_FOOTBALL_RATE_LIMIT_PER_MINUTE
        self._request_timestamps: deque[float] = deque()

        if not self.api_key:
            raise ApiFootballError(
                "API_FOOTBALL_KEY no está configurada. Define la variable de "
                "entorno con tu API key de api-football.com."
            )

    def _throttle(self) -> None:
        now = time.monotonic()
        window = 60.0
        while self._request_timestamps and now - self._request_timestamps[0] > window:
            self._request_timestamps.popleft()

        if len(self._request_timestamps) >= self._rate_limit_per_minute:
            sleep_for = window - (now - self._request_timestamps[0])
            if sleep_for > 0:
                time.sleep(sleep_for)

        self._request_timestamps.append(time.monotonic())

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._throttle()

        response = requests.get(
            f"{self.base_url}/{endpoint.lstrip('/')}",
            headers={"x-apisports-key": self.api_key},
            params=params or {},
            timeout=15,
        )

        if response.status_code == 429:
            raise ApiFootballError("Cuota diaria de api-football.com agotada (HTTP 429).")
        response.raise_for_status()

        payload = response.json()
        if payload.get("errors"):
            raise ApiFootballError(str(payload["errors"]))

        return payload

    def get_fixtures(self, league_id: int, date: str) -> list[dict[str, Any]]:
        """
        Partidos de una liga en una fecha dada (YYYY-MM-DD).

        El plan gratuito NO acepta el parámetro `next`, y al combinar `league`
        + `season` solo permite temporadas ya cerradas (no la actual). Lo
        único que sí funciona para partidos en curso/próximos es pedir
        `/fixtures?date=X` sin liga ni temporada -- eso trae TODAS las ligas
        del día -- y filtrar acá por `league_id`. Además, `date` solo acepta
        un rango de +-1 día respecto a hoy en el plan gratuito.
        """
        payload = self._get("fixtures", {"date": date})
        return [f for f in payload.get("response", []) if f["league"]["id"] == league_id]

    def get_fixture_statistics(self, fixture_id: int) -> list[dict[str, Any]]:
        """Estadísticas post/durante partido (posesión, tiros, xG si el plan lo incluye)."""
        return self._get("fixtures/statistics", {"fixture": fixture_id}).get("response", [])

    def get_injuries(self, fixture_id: int) -> list[dict[str, Any]]:
        return self._get("injuries", {"fixture": fixture_id}).get("response", [])

    def get_teams(self, league_id: int, season: int) -> list[dict[str, Any]]:
        """El plan gratuito solo acepta temporadas ya cerradas, no la actual."""
        return self._get("teams", {"league": league_id, "season": season}).get("response", [])

    def get_team_by_id(self, team_id: int) -> dict[str, Any] | None:
        response = self._get("teams", {"id": team_id}).get("response", [])
        return response[0] if response else None

    def search_teams(self, name: str) -> list[dict[str, Any]]:
        """Búsqueda por nombre -- para equipos sin api_football_id confirmado todavía."""
        return self._get("teams", {"search": name}).get("response", [])

    def get_odds(self, fixture_id: int) -> list[dict[str, Any]]:
        """Cuotas de referencia (útil como control cruzado, no como fuente de valor)."""
        return self._get("odds", {"fixture": fixture_id}).get("response", [])

    def get_head_to_head(self, equipo_a_id: int, equipo_b_id: int) -> list[dict[str, Any]]:
        """
        Cruces históricos entre dos equipos, sin exigir `season` -- a diferencia de
        `get_fixtures` (ventana de +-1 día) o `get_teams` (solo temporadas cerradas),
        esta es la única vía conocida para recuperar el `fixture_id` real de partidos
        YA JUGADOS de la temporada en curso en el plan gratuito (ver
        HANDOFF_dataset_contexto.md, Tarea 1) -- necesaria porque los partidos
        importados a mano vía import_historical_dataset nunca pasaron por la API y
        no tienen fixture_id, y sin fixture_id no se puede pedir
        get_fixture_statistics.
        """
        return self._get("fixtures/headtohead", {"h2h": f"{equipo_a_id}-{equipo_b_id}"}).get("response", [])
