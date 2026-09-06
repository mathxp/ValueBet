"""
Ingeniería de features: convierte un Partido (con sus métricas_avanzadas
JSONB) en un vector de features plano, usado tanto para entrenar (notebooks/)
como para inferencia en vivo (predictor.py). Mantener esta función como la
ÚNICA fuente de verdad para features evita el skew entre entrenamiento y
producción.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

FEATURE_COLUMNS = [
    "xg_local",
    "xg_visitante",
    "bajas_local_count",
    "bajas_visitante_count",
    "carga_fisica_local_dias",
    "carga_fisica_visitante_dias",
    "precipitacion_mm",
    "viento_max_kmh",
]


def build_features(metricas_avanzadas: dict[str, Any]) -> dict[str, float]:
    clima = metricas_avanzadas.get("clima", {})
    lesiones_local = metricas_avanzadas.get("lesiones_local", [])
    lesiones_visitante = metricas_avanzadas.get("lesiones_visitante", [])

    return {
        "xg_local": float(metricas_avanzadas.get("xg_local", 0.0) or 0.0),
        "xg_visitante": float(metricas_avanzadas.get("xg_visitante", 0.0) or 0.0),
        "bajas_local_count": float(len(lesiones_local)),
        "bajas_visitante_count": float(len(lesiones_visitante)),
        "carga_fisica_local_dias": float(
            metricas_avanzadas.get("carga_fisica_local_dias", 7) or 7
        ),
        "carga_fisica_visitante_dias": float(
            metricas_avanzadas.get("carga_fisica_visitante_dias", 7) or 7
        ),
        "precipitacion_mm": float(clima.get("precipitacion_mm", 0.0) or 0.0),
        "viento_max_kmh": float(clima.get("viento_max_kmh", 0.0) or 0.0),
    }


def features_to_dataframe(rows: list[dict[str, float]]) -> pd.DataFrame:
    """Para uso en notebooks/entrenamiento: lista de features -> DataFrame ordenado."""
    return pd.DataFrame(rows, columns=FEATURE_COLUMNS)
