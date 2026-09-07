"""
Importa el dataset histórico en Excel de la Primera División de Chile,
temporadas 2022 y 2023 completas (hojas Partidos_2022 y Partidos_2023).

Junto con los datasets de 2024-2025 (import_excel_dataset) y 2026
(import_historical_dataset), esto le da al sistema cinco temporadas de goles
reales para calcular los ratings de ataque/defensa
(ml_models/pipelines/team_ratings.py) -- mientras más historial real, menos
ruido en las proyecciones.
"""

from datetime import datetime, timedelta
from pathlib import Path

import openpyxl
from django.core.management.base import BaseCommand
from django.utils.timezone import make_aware

from db_models.models import Equipo, Partido

DATASET_PATH = Path(__file__).resolve().parent.parent.parent / "historical_datasets" / "liga_chile_2022_2023.xlsx"

# api_football_id real de cada equipo (confirmado contra GET /teams?name=...,
# mismo criterio que import_excel_dataset.py) -- evita crear un Equipo
# duplicado el día que api-football traiga a alguno de estos en un fixture
# futuro. Ascensos/descensos hacen que la lista de equipos cambie cada año:
# Curicó Unido, Deportes Antofagasta y Magallanes no estaban en los datasets
# 2024-2026 (ya descendidos), así que no tenían id confirmado todavía -- el
# día que se necesite (por ej. si vuelven a Primera y aparecen en un fixture),
# `manage.py shell` + una consulta a /teams?search=... a api-football completa
# el mapeo; por ahora quedan sin api_football_id (se matchean por nombre).
API_FOOTBALL_ID_POR_NOMBRE = {
    "Audax Italiano": 2329,
    "Cobresal": 2331,
    "Colo-Colo": 2315,
    "Coquimbo Unido": 2330,
    "Deportes Copiapó": 2343,
    "Deportes La Serena": 2341,
    "Everton": 2325,
    "Huachipato": 2328,
    "O'Higgins": 2320,
    "Palestino": 2318,
    "Universidad Católica": 2994,
    "Universidad de Chile": 2323,
    "Unión Española": 2321,
    "Unión La Calera": 2326,
    "Ñublense": 2337,
}

# Estados que no reflejan un resultado jugado en la cancha -- team_ratings.py
# solo mira Partido.Estado.FINALIZADO, así que estos quedan como CANCELADO
# para no contaminar los ratings con un resultado administrativo.
_ESTADO_POR_CODIGO = {
    "Jugado": Partido.Estado.FINALIZADO,
    "Ganado en mesa": Partido.Estado.CANCELADO,
}


class Command(BaseCommand):
    help = "Importa el dataset Excel de la Primera División de Chile, temporadas 2022 y 2023."

    def handle(self, *args, **options):
        if not DATASET_PATH.exists():
            self.stderr.write(f"No se encontró el archivo en {DATASET_PATH}")
            return

        wb = openpyxl.load_workbook(DATASET_PATH, data_only=True)

        creados_22, existentes_22 = self._importar_temporada(
            wb["Partidos_2022"], "2022", datetime(2022, 2, 1, 12, 0)
        )
        creados_23, existentes_23 = self._importar_temporada(
            wb["Partidos_2023"], "2023", datetime(2023, 2, 1, 12, 0)
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Temporada 2022: {creados_22} partidos nuevos, {existentes_22} ya existían.\n"
                f"Temporada 2023: {creados_23} partidos nuevos, {existentes_23} ya existían."
            )
        )

    def _obtener_equipo(self, nombre):
        api_football_id = API_FOOTBALL_ID_POR_NOMBRE.get(nombre)
        if api_football_id is not None:
            equipo, creado = Equipo.objects.get_or_create(
                api_football_id=api_football_id, defaults={"nombre": nombre}
            )
        else:
            equipo, creado = Equipo.objects.get_or_create(nombre=nombre)
        if creado:
            self.stdout.write(f"Equipo creado: {nombre} (api_football_id={api_football_id})")
        return equipo

    def _importar_temporada(self, hoja, temporada, fecha_base):
        # Esta hoja no trae fecha real de cada partido, solo el orden de
        # disputa (id) -- se sintetiza una fecha aproximada (una "ronda" cada
        # 8 partidos, una semana entre rondas, ver mismo criterio en
        # import_excel_dataset.py:_importar_2025) que alcanza para preservar
        # el orden cronológico dentro de la temporada y entre temporadas.
        creados, existentes = 0, 0
        for fila in hoja.iter_rows(min_row=2, values_only=True):
            if fila[0] is None:
                continue
            (
                id_, _temporada, local, goles_local, goles_visita, visita,
                _resultado, _total, _dif, _marcador, estado_texto, _obs,
            ) = fila

            ronda = (id_ - 1) // 8
            fecha_hora = make_aware(fecha_base + timedelta(days=7 * ronda))
            estado = _ESTADO_POR_CODIGO.get(estado_texto, Partido.Estado.CANCELADO)

            equipo_local = self._obtener_equipo(local)
            equipo_visitante = self._obtener_equipo(visita)

            defaults = {
                "liga": "Primera División",
                "temporada": temporada,
                "estado": estado,
                "metricas_avanzadas": {"fuente_resultado": "dataset_excel_2022_2023"},
            }
            if estado == Partido.Estado.FINALIZADO and goles_local is not None and goles_visita is not None:
                defaults["resultado"] = {"local": goles_local, "visitante": goles_visita}

            _, creado = Partido.objects.get_or_create(
                equipo_local=equipo_local,
                equipo_visitante=equipo_visitante,
                fecha_hora=fecha_hora,
                defaults=defaults,
            )
            creados += int(creado)
            existentes += int(not creado)
        return creados, existentes
