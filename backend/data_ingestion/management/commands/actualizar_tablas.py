from django.core.management.base import BaseCommand

from data_ingestion.tablas import actualizar_tablas


class Command(BaseCommand):
    help = "Actualiza las tablas de posiciones de Liga, Copa Chile y Copa de la Liga (ESPN + Wikipedia)."

    def handle(self, *args, **options):
        for slug, estado in actualizar_tablas().items():
            self.stdout.write(f"{slug}: {estado}")
