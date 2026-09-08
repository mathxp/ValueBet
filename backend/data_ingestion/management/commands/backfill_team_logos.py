"""
Rellena Equipo.logo_url para equipos que quedaron sin escudo -- típicamente
equipos creados por los comandos de importación histórica (import_excel_
dataset_2022_2023.py y compañía), que solo insertan nombre/id sin tocar
logo_url. Ver también data_ingestion/tasks.py:_get_or_create_equipo, que es
el único lugar que puebla logo_url automáticamente (solo corre cuando el
equipo aparece en un fixture en vivo de api-football).

Con api_football_id conocido, un solo GET /teams?id=X trae el escudo.
Sin api_football_id (equipos ya descendidos que nunca llegaron a los
datasets 2024+, ver comentario en import_excel_dataset_2022_2023.py), se
intenta un GET /teams?search=<nombre> y solo se aplica si hay un único
candidato chileno cuyo nombre calza -- para no asignarle a un equipo el
escudo de un homónimo de otro país.
"""

from django.core.management.base import BaseCommand

from data_ingestion.api_clients.football_api import ApiFootballClient, ApiFootballError
from db_models.models import Equipo


class Command(BaseCommand):
    help = "Backfill de Equipo.logo_url para equipos sin escudo."

    def handle(self, *args, **options):
        client = ApiFootballClient()
        equipos = Equipo.objects.filter(logo_url="")

        if not equipos.exists():
            self.stdout.write(self.style.SUCCESS("Todos los equipos ya tienen logo_url."))
            return

        actualizados = 0
        for equipo in equipos:
            try:
                if equipo.api_football_id:
                    actualizados += self._backfill_por_id(equipo, client)
                else:
                    actualizados += self._backfill_por_nombre(equipo, client)
            except ApiFootballError as exc:
                self.stderr.write(f"  {equipo.nombre}: error de api-football ({exc})")

        self.stdout.write(self.style.SUCCESS(f"{actualizados} equipo(s) actualizados."))

    def _backfill_por_id(self, equipo: Equipo, client: ApiFootballClient) -> bool:
        payload = client.get_team_by_id(equipo.api_football_id)
        logo = (payload or {}).get("team", {}).get("logo")
        if not logo:
            self.stdout.write(f"  {equipo.nombre}: sin logo en la respuesta de api-football.")
            return False

        equipo.logo_url = logo
        equipo.save(update_fields=["logo_url"])
        self.stdout.write(f"  {equipo.nombre}: logo actualizado (id={equipo.api_football_id}).")
        return True

    def _backfill_por_nombre(self, equipo: Equipo, client: ApiFootballClient) -> bool:
        candidatos = [
            c for c in client.search_teams(equipo.nombre) if c.get("team", {}).get("country") == "Chile"
        ]
        if len(candidatos) != 1:
            self.stdout.write(
                f"  {equipo.nombre}: {len(candidatos)} candidato(s) chilenos en la búsqueda -- "
                "se deja sin resolver, requiere revisión manual."
            )
            return False

        team = candidatos[0]["team"]
        equipo.logo_url = team.get("logo", "")
        equipo.api_football_id = team["id"]
        equipo.save(update_fields=["logo_url", "api_football_id"])
        self.stdout.write(
            f"  {equipo.nombre}: logo y api_football_id={team['id']} asignados vía búsqueda por nombre."
        )
        return bool(equipo.logo_url)
