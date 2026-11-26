from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Corre todo el pipeline una vez de forma sincrónica (sin necesitar Redis "
        "ni un worker de Celery corriendo): sincroniza fixtures, cuotas, proyecta "
        "xG y genera recomendaciones de apuestas de valor (no ejecuta nada, ver "
        "trading_engine/scanner.py). Útil para desarrollo local rápido; en "
        "producción esto lo hace el beat schedule de Celery (ver core/celery.py)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours-ahead",
            type=int,
            default=24,
            help="Ventana de partidos a considerar para cuotas/xG/escaneo (default: 24h).",
        )

    def handle(self, *args, **options):
        # Evita depender de un broker: .delay() se ejecuta en el mismo proceso.
        from core.celery import app as celery_app

        celery_app.conf.task_always_eager = True

        from data_ingestion.tasks import fetch_upcoming_fixtures, refresh_odds_for_live_window
        from ml_models.tasks import project_xg_for_upcoming_matches, reconciliar_analisis
        from trading_engine.tasks import generar_combinadas_pendientes, scan_market_odds

        horas = options["hours_ahead"]

        total_fixtures = 0
        for league_id in settings.WATCHED_LEAGUES:
            total_fixtures += fetch_upcoming_fixtures(league_id=league_id)
        self.stdout.write(f"Fixtures sincronizados: {total_fixtures}")

        refresh_odds_for_live_window(minutes_ahead=horas * 60)
        self.stdout.write("Cuotas actualizadas para partidos dentro de la ventana")

        actualizados = project_xg_for_upcoming_matches(hours_ahead=horas)
        self.stdout.write(f"xG proyectado para {actualizados} partido(s) (0 es normal si aún no hay historial)")

        operaciones = scan_market_odds(minutes_ahead=horas * 60)
        self.stdout.write(self.style.SUCCESS(f"Recomendaciones nuevas generadas: {operaciones}"))

        combinadas = generar_combinadas_pendientes(horas_adelante=horas)
        self.stdout.write(f"Combinadas generadas: {combinadas}")

        resueltos = reconciliar_analisis()
        self.stdout.write(f"Análisis reconciliados con resultado real: {resueltos}")

        from data_ingestion.tablas import actualizar_tablas

        tablas = actualizar_tablas()
        self.stdout.write("Tablas de posiciones: " + ", ".join(f"{k}={v}" for k, v in tablas.items()))
