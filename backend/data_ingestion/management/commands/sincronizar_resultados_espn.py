from datetime import date

from django.core.management.base import BaseCommand

from data_ingestion.espn import sincronizar_liga


class Command(BaseCommand):
    help = "Rellena/actualiza resultados y fixtures de la Liga de Primera desde ESPN (toda la temporada por defecto)."

    def add_arguments(self, parser):
        parser.add_argument("--desde", type=date.fromisoformat, help="YYYY-MM-DD")
        parser.add_argument("--hasta", type=date.fromisoformat, help="YYYY-MM-DD")

    def handle(self, *args, **opts):
        stats = sincronizar_liga(desde=opts.get("desde"), hasta=opts.get("hasta"))
        self.stdout.write(self.style.SUCCESS(str(stats)))
