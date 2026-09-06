"""
Importa el dataset histórico en Excel de la Primera División de Chile,
temporadas 2024 y 2025 completas (hojas Partidos_2024 y Partidos_2025).

Junto con el dataset de fechas 1-21 de 2026 (import_historical_dataset), esto
le da al sistema tres temporadas de goles reales para calcular los ratings de
ataque/defensa (ml_models/pipelines/team_ratings.py) -- mientras más
historial real, menos ruido en las proyecciones, sobre todo para equipos que
recién empiezan a acumular partidos en la temporada actual.
"""

import re
from datetime import datetime, timedelta
from pathlib import Path

import openpyxl
from django.core.management.base import BaseCommand
from django.utils.timezone import make_aware

from db_models.models import Equipo, Partido

DATASET_PATH = Path(__file__).resolve().parent.parent.parent / "historical_datasets" / "liga_chile_2024_2025.xlsx"

# api_football_id real de cada equipo (confirmado contra GET /teams?name=...),
# igual que en import_historical_dataset.py -- evita crear un Equipo
# duplicado el día que api-football traiga a alguno de estos en un fixture
# futuro (ascensos/descensos hacen que la lista de equipos cambie cada año).
API_FOOTBALL_ID_POR_NOMBRE = {
    "Audax Italiano": 2329,
    "Cobreloa": 2332,
    "Cobresal": 2331,
    "Colo-Colo": 2315,
    "Coquimbo Unido": 2330,
    "Deportes Copiapó": 2343,
    "Deportes Iquique": 2319,
    "Deportes La Serena": 2341,
    "Deportes Limache": 16730,
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

FECHA_PATRON = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


class Command(BaseCommand):
    help = "Importa el dataset Excel de la Primera División de Chile, temporadas 2024 y 2025."

    def handle(self, *args, **options):
        if not DATASET_PATH.exists():
            self.stderr.write(f"No se encontró el archivo en {DATASET_PATH}")
            return

        equipos = {}
        for nombre, api_id in API_FOOTBALL_ID_POR_NOMBRE.items():
            equipo, creado = Equipo.objects.get_or_create(
                api_football_id=api_id, defaults={"nombre": nombre}
            )
            equipos[nombre] = equipo
            if creado:
                self.stdout.write(f"Equipo creado: {nombre} (api_football_id={api_id})")

        wb = openpyxl.load_workbook(DATASET_PATH, data_only=True)

        creados_24, existentes_24 = self._importar_2024(wb["Partidos_2024"], equipos)
        creados_25, existentes_25 = self._importar_2025(wb["Partidos_2025"], equipos)

        self.stdout.write(
            self.style.SUCCESS(
                f"Temporada 2024: {creados_24} partidos nuevos, {existentes_24} ya existían.\n"
                f"Temporada 2025: {creados_25} partidos nuevos, {existentes_25} ya existían."
            )
        )

    def _parsear_fecha(self, texto, respaldo):
        """
        La columna fecha del dataset 2024 no siempre trae un DD/MM/YYYY limpio
        (hay valores como "Semana 21/07/2024" o "09-10/11/2024" para fechas
        con partidos repartidos en varios días) -- se busca el primer patrón
        DD/MM/YYYY dentro del texto en vez de exigir un formato exacto.
        """
        match = FECHA_PATRON.search(str(texto)) if texto else None
        if not match:
            return respaldo
        dia, mes, anio = (int(x) for x in match.groups())
        return make_aware(datetime(anio, mes, dia, 12, 0))

    def _importar_2024(self, hoja, equipos):
        creados, existentes = 0, 0
        for fila in hoja.iter_rows(min_row=2, values_only=True):
            if fila[0] is None:
                continue
            (
                _id, jornada, _rueda, fecha_texto, _hora, local, goles_local, goles_visita,
                visita, _resultado, _total, _dif, _marcador, estado_texto, obs,
            ) = fila

            fecha_hora = self._parsear_fecha(fecha_texto, make_aware(datetime(2024, 6, 1, 12, 0)))
            creado = self._guardar_partido(
                equipos[local], equipos[visita], fecha_hora, "2024",
                goles_local, goles_visita, estado_texto,
                metricas={"jornada": jornada, **({"observacion": obs} if obs else {})},
            )
            creados += int(creado)
            existentes += int(not creado)
        return creados, existentes

    def _importar_2025(self, hoja, equipos):
        creados, existentes = 0, 0
        for fila in hoja.iter_rows(min_row=2, values_only=True):
            if fila[0] is None:
                continue
            (id_, local, goles_local, goles_visita, visita, _resultado, _total, _dif, _marcador, estado_texto) = fila

            # Esta hoja no trae fecha real -- se sintetiza una fecha
            # aproximada (una "ronda" cada ~8 partidos, una semana entre
            # rondas) que preserva el orden cronológico dentro de la
            # temporada y cae siempre después de 2024 y antes de 2026, que es
            # lo único que importa para el orden "más reciente primero" que
            # usa team_ratings.py.
            ronda = (id_ - 1) // 8
            fecha_hora = make_aware(datetime(2025, 2, 1, 12, 0) + timedelta(days=7 * ronda))

            creado = self._guardar_partido(
                equipos[local], equipos[visita], fecha_hora, "2025",
                goles_local, goles_visita, estado_texto,
                metricas={"fecha_aproximada": True},
            )
            creados += int(creado)
            existentes += int(not creado)
        return creados, existentes

    def _guardar_partido(self, equipo_local, equipo_visitante, fecha_hora, temporada, goles_local, goles_visita, estado_texto, metricas):
        estado = Partido.Estado.FINALIZADO if estado_texto == "Jugado" else Partido.Estado.CANCELADO

        defaults = {
            "liga": "Primera División",
            "temporada": temporada,
            "estado": estado,
            "metricas_avanzadas": {"fuente_resultado": "dataset_excel_2024_2025", **metricas},
        }
        if estado == Partido.Estado.FINALIZADO and goles_local is not None and goles_visita is not None:
            defaults["resultado"] = {"local": goles_local, "visitante": goles_visita}

        _, creado = Partido.objects.get_or_create(
            equipo_local=equipo_local,
            equipo_visitante=equipo_visitante,
            fecha_hora=fecha_hora,
            defaults=defaults,
        )
        return creado
