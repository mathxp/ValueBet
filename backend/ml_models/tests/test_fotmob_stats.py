from unittest.mock import patch

import pandas as pd
from django.test import SimpleTestCase, TestCase

from db_models.models import Equipo
from ml_models.pipelines.fotmob_stats import (
    FOTMOB_A_EQUIPO,
    _fila_a_pares,
    actualizar_metadata_equipos,
)


def _df_fake_stat(nombre_stat: str, filas: list[tuple[str, float]]) -> pd.DataFrame:
    """
    Reproduce la forma real (con columna 'name' duplicada) que devuelve
    FotMob.get_teams_stats_season() -- ver el docstring de _fila_a_pares.
    """
    columnas = ["id", "teamId", "name", "position", "substatValue", "statValue", "rank", "type", "name", "value"]
    filas_completas = [
        [i, i, nombre, None, {}, {}, i, "teams", nombre_stat, valor]
        for i, (nombre, valor) in enumerate(filas)
    ]
    return pd.DataFrame(filas_completas, columns=columnas)


class FilaAParesTests(SimpleTestCase):
    def test_extrae_nombre_de_equipo_y_valor_pese_a_columna_name_duplicada(self):
        df = _df_fake_stat("possession_percentage_team", [("Colo Colo", 62.0), ("Palestino", 59.2)])
        self.assertEqual(_fila_a_pares(df), [("Colo Colo", 62.0), ("Palestino", 59.2)])


class MapeoEquiposTests(SimpleTestCase):
    def test_todos_los_16_equipos_de_la_temporada_vigente_estan_mapeados(self):
        self.assertEqual(len(FOTMOB_A_EQUIPO), 16)

    def test_mapeo_no_trivial_nublense_sin_enie(self):
        self.assertEqual(FOTMOB_A_EQUIPO["Ñublense"], "Nublense")


class ActualizarMetadataEquiposTests(TestCase):
    def test_guarda_stats_en_metadata_del_equipo_mapeado(self):
        equipo = Equipo.objects.create(nombre="Colo Colo")

        with patch(
            "ml_models.pipelines.fotmob_stats.obtener_stats_temporada",
            return_value={"Colo Colo": {"possession_percentage_team": 62.0}},
        ):
            actualizados = actualizar_metadata_equipos("2025")

        equipo.refresh_from_db()
        self.assertEqual(actualizados, 1)
        self.assertEqual(equipo.metadata["fotmob"]["temporada"], "2025")
        self.assertEqual(equipo.metadata["fotmob"]["possession_percentage_team"], 62.0)
        self.assertIn("actualizado_en", equipo.metadata["fotmob"])

    def test_ignora_nombres_que_no_matchean_ningun_equipo_propio(self):
        Equipo.objects.create(nombre="Colo Colo")

        with patch(
            "ml_models.pipelines.fotmob_stats.obtener_stats_temporada",
            return_value={"Equipo Fantasma": {"possession_percentage_team": 40.0}},
        ):
            actualizados = actualizar_metadata_equipos("2025")

        self.assertEqual(actualizados, 0)
