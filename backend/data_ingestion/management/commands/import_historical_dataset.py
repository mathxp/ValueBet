"""
Importa el dataset histórico armado a mano (investigación con Claude/Gemini +
fuente oficial T13/Deportes13) con resultados reales de la Primera División
de Chile 2026, fechas 1 a 21.

A diferencia del xG "proxy" basado en tiros, esto son GOLES REALES -- la base
más confiable posible para calcular ratings de ataque/defensa por equipo
(ver ml_models/pipelines/team_ratings.py). Es idempotente: correrlo dos veces
no duplica equipos ni partidos.
"""

from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils.timezone import make_aware

from data_ingestion.historical_datasets.liga_chile_2026 import PARTIDOS
from db_models.models import Equipo, Partido

# Mapeo nombre-completo-del-dataset -> api_football_id real (confirmado contra
# GET /teams?name=... de api-football). Usar el id real evita crear un
# Equipo duplicado el día que api-football traiga este mismo equipo en un
# fixture futuro -- ver data_ingestion/tasks.py:_get_or_create_equipo, que
# también hace update_or_create por api_football_id.
API_FOOTBALL_ID_POR_NOMBRE = {
    "Universidad de Chile": 2323,
    "Universidad Catolica": 2994,
    "Universidad de Concepcion": 2324,
    "Colo-Colo": 2315,
    "Coquimbo Unido": 2330,
    "Deportes La Serena": 2341,
    "Deportes Limache": 16730,
    "Deportes Concepcion": 5635,
    "Union La Calera": 2326,
    "Audax Italiano": 2329,
    "Palestino": 2318,
    "Cobresal": 2331,
    "Huachipato": 2328,
    "Nublense": 2337,
    "Everton": 2325,
    "O'Higgins": 2320,
}

_ESTADO_POR_CODIGO = {
    "Jugado": Partido.Estado.FINALIZADO,
    # "NO computa en la tabla" según la fuente -- se guarda pero se excluye
    # de los ratings (team_ratings.py solo mira estado=FINALIZADO).
    "Suspendido": Partido.Estado.CANCELADO,
}


class Command(BaseCommand):
    help = "Importa el dataset histórico de la Primera División de Chile 2026 (fechas 1-21)."

    def handle(self, *args, **options):
        equipos_por_nombre = {}
        for nombre, api_football_id in API_FOOTBALL_ID_POR_NOMBRE.items():
            equipo, creado = Equipo.objects.get_or_create(
                api_football_id=api_football_id, defaults={"nombre": nombre}
            )
            equipos_por_nombre[nombre] = equipo
            if creado:
                self.stdout.write(f"Equipo creado: {nombre} (api_football_id={api_football_id})")

        creados, existentes = 0, 0
        for jornada, fecha_str, hora_str, estadio, local, gl, gv, visita, estado_codigo, obs in PARTIDOS:
            equipo_local = equipos_por_nombre[local]
            equipo_visitante = equipos_por_nombre[visita]
            fecha_hora = make_aware(datetime.strptime(f"{fecha_str} {hora_str}", "%d/%m/%Y %H:%M"))
            estado = _ESTADO_POR_CODIGO[estado_codigo]

            metricas = {"jornada": jornada, "estadio": estadio, "fuente_resultado": "manual_t13_2026"}
            if obs:
                metricas["observacion"] = obs

            _, creado = Partido.objects.get_or_create(
                equipo_local=equipo_local,
                equipo_visitante=equipo_visitante,
                fecha_hora=fecha_hora,
                defaults={
                    "liga": "Primera División",
                    "temporada": "2026",
                    "estado": estado,
                    "resultado": {"local": gl, "visitante": gv},
                    "metricas_avanzadas": metricas,
                },
            )
            creados += int(creado)
            existentes += int(not creado)

        self.stdout.write(
            self.style.SUCCESS(f"Partidos importados: {creados} nuevos, {existentes} ya existían.")
        )
