"""
Tarea 1 del handoff (ver HANDOFF_dataset_contexto.md en la raíz del repo): recupera
el fixture_id real de los 168 partidos de 2026 importados a mano vía
import_historical_dataset, que nunca pasaron por la API y por eso no tienen
fixture_id -- sin fixture_id no se puede pedir get_fixture_statistics (Tarea 2,
el backfill de remates).

Vía: GET /fixtures/headtohead?h2h=A-B trae los cruces históricos entre dos equipos
sin exigir `season`, a diferencia de get_fixtures (ventana +-1 día respecto a hoy)
o get_teams (solo temporadas ya cerradas) -- es la única vía conocida en el plan
gratuito para partidos YA JUGADOS de la temporada en curso. Confirmado con una
llamada de prueba (Colo Colo-U. de Chile) antes de gastar cuota en las ~120
combinaciones: responde sin error, trae 2026, y trae fechas tempranas (marzo)
además de recientes (agosto) -- no solo lo más reciente.

Ojo: headtohead devuelve TODAS las competencias entre el par (Copa Chile, Súper
Copa además de la liga) -- se filtra por league_id=265 (ver WATCHED_LEAGUES).

Cuota: 100 req/día en el plan gratuito, compartida con el pipeline en vivo
(fetch_upcoming_fixtures/fetch_and_store_odds corren cada hora). Con 16 equipos
son C(16,2)=120 pares -- no entra en un día. --limit corta cuántos pares
consultar en esta corrida; correrlo de nuevo al otro día retoma solo los pares
que todavía tengan algún Partido 2026 sin fixture_id (no vuelve a gastar cuota
en pares ya resueltos, ni pisa un fixture_id que ya se haya guardado).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from data_ingestion.api_clients.football_api import ApiFootballClient, ApiFootballError
from data_ingestion.management.commands.import_historical_dataset import API_FOOTBALL_ID_POR_NOMBRE
from db_models.models import Equipo, Partido

LEAGUE_ID = 265
TEMPORADA = "2026"


class Command(BaseCommand):
    help = "Backfillea el fixture_id real de los partidos 2026 importados a mano (Tarea 1 del handoff)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=80,
            help=(
                "Máximo de pares (= llamadas a la API) a consultar en esta corrida -- "
                "respeta la cuota diaria compartida con el pipeline en vivo."
            ),
        )

    def handle(self, *args, **options):
        ids_validos = [
            api_id
            for api_id in set(API_FOOTBALL_ID_POR_NOMBRE.values())
            if Equipo.objects.filter(api_football_id=api_id).exists()
        ]
        faltantes = set(API_FOOTBALL_ID_POR_NOMBRE.values()) - set(ids_validos)
        if faltantes:
            self.stderr.write(f"Sin Equipo para api_football_id: {sorted(faltantes)}")

        pares_pendientes = self._pares_con_partidos_pendientes(ids_validos)
        self.stdout.write(f"Pares con partidos 2026 sin fixture_id: {len(pares_pendientes)}")

        client = ApiFootballClient()
        limite = options["limit"]
        consultados = 0
        actualizados = 0
        ambiguos = 0
        marcador_distinto = 0

        for id_a, id_b in pares_pendientes:
            if consultados >= limite:
                self.stdout.write(f"Límite de {limite} pares alcanzado -- volvé a correrlo para seguir con el resto.")
                break

            try:
                fixtures = client.get_head_to_head(id_a, id_b)
            except ApiFootballError as e:
                self.stderr.write(f"Fallo en par ({id_a}, {id_b}): {e}")
                consultados += 1
                continue
            consultados += 1

            fixtures_liga_2026 = [
                f
                for f in fixtures
                if f["league"]["id"] == LEAGUE_ID and str(f["league"]["season"]) == TEMPORADA
            ]
            for f in fixtures_liga_2026:
                resultado = self._actualizar_partido(f)
                if resultado == "actualizado":
                    actualizados += 1
                elif resultado == "ambiguo":
                    ambiguos += 1
                elif resultado == "marcador_distinto":
                    marcador_distinto += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Pares consultados: {consultados}  "
                f"Partidos con fixture_id nuevo: {actualizados}  "
                f"Ambiguos (mas de un candidato, no se tocaron): {ambiguos}  "
                f"Marcador no coincide (no se tocaron): {marcador_distinto}"
            )
        )
        self.stdout.write(
            f"Quedan sin fixture_id: {Partido.objects.filter(temporada=TEMPORADA, api_football_id__isnull=True).count()}"
        )

    def _pares_con_partidos_pendientes(self, ids_validos: list[int]) -> list[tuple[int, int]]:
        filas = (
            Partido.objects.filter(
                temporada=TEMPORADA,
                api_football_id__isnull=True,
                equipo_local__api_football_id__in=ids_validos,
                equipo_visitante__api_football_id__in=ids_validos,
            )
            .values_list("equipo_local__api_football_id", "equipo_visitante__api_football_id")
            .distinct()
        )
        pares = {tuple(sorted((local_id, visita_id))) for local_id, visita_id in filas}
        return sorted(pares)

    def _actualizar_partido(self, fixture: dict) -> str:
        home_id = fixture["teams"]["home"]["id"]
        away_id = fixture["teams"]["away"]["id"]
        goles_local = fixture["goals"]["home"]
        goles_visita = fixture["goals"]["away"]
        fixture_id = fixture["fixture"]["id"]

        candidatos = Partido.objects.filter(
            temporada=TEMPORADA,
            equipo_local__api_football_id=home_id,
            equipo_visitante__api_football_id=away_id,
            api_football_id__isnull=True,
        )
        cantidad = candidatos.count()
        if cantidad == 0:
            return "ya_resuelto_o_no_existe"
        if cantidad > 1:
            self.stderr.write(
                f"Ambiguo: {cantidad} partidos sin resolver entre equipo {home_id} (local) y "
                f"{away_id} (visita) -- fixture {fixture_id} no se asignó."
            )
            return "ambiguo"

        candidato = candidatos.first()
        if candidato.resultado.get("local") != goles_local or candidato.resultado.get("visitante") != goles_visita:
            self.stderr.write(
                f"Marcador no coincide para fixture {fixture_id} (partido_id {candidato.id}): "
                f"API {goles_local}-{goles_visita} vs base {candidato.resultado}"
            )
            return "marcador_distinto"

        candidato.api_football_id = fixture_id
        candidato.save(update_fields=["api_football_id"])
        return "actualizado"
