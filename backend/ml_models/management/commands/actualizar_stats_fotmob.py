"""
Trae estadísticas complementarias de equipo desde FotMob (posesión, grandes
ocasiones, tiros al arco, corners) y las guarda en Equipo.metadata["fotmob"]
para mostrarlas en la pestaña Equipos -- ver el docstring de
ml_models/pipelines/fotmob_stats.py para por qué esto NO incluye xG ni se
usa todavía en el cálculo de ratings/probabilidades.

Requiere el paquete opcional `lanusstats` (pip install -r
requirements-scraping.txt) y Chrome instalado. Se corre a mano, de vez en
cuando (las estadísticas de temporada no cambian partido a partido) -- no
está enganchado a la tarea automática por hora.
"""

from datetime import date

from django.core.management.base import BaseCommand

from ml_models.pipelines.fotmob_stats import actualizar_metadata_equipos


class Command(BaseCommand):
    help = "Actualiza Equipo.metadata['fotmob'] con estadísticas de temporada desde FotMob (vía LanusStats)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--temporada",
            default=str(date.today().year),
            help="Temporada FotMob a consultar (ej. 2025). Por defecto, el año actual.",
        )

    def handle(self, *args, **options):
        temporada = options["temporada"]
        try:
            actualizados = actualizar_metadata_equipos(temporada)
        except ImportError:
            self.stderr.write(self.style.ERROR(
                "Falta el paquete 'lanusstats'. Instalalo con: "
                "pip install -r requirements-scraping.txt"
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            f"Equipos actualizados con estadísticas FotMob {temporada}: {actualizados}"
        ))
