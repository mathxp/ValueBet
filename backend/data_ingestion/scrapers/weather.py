"""
Clima del estadio en la fecha del partido, vía Open-Meteo (gratis, sin API key).
https://open-meteo.com/en/docs

api-football no incluye clima; esta es una de las "métricas profundas" que el
prompt del proyecto identifica como ventaja competitiva sobre lo que ya está
reflejado en la cuota.
"""

from __future__ import annotations

from datetime import date as date_type
from typing import Any

import requests

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_weather_for_match(
    latitude: float, longitude: float, match_date: date_type
) -> dict[str, Any]:
    """Pronóstico/histórico diario de clima para las coordenadas del estadio."""
    response = requests.get(
        OPEN_METEO_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "start_date": match_date.isoformat(),
            "end_date": match_date.isoformat(),
            "daily": "temperature_2m_max,precipitation_sum,wind_speed_10m_max",
            "timezone": "auto",
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    daily = payload.get("daily", {})

    if not daily.get("time"):
        return {}

    return {
        "temperatura_max_c": daily["temperature_2m_max"][0],
        "precipitacion_mm": daily["precipitation_sum"][0],
        "viento_max_kmh": daily["wind_speed_10m_max"][0],
    }
