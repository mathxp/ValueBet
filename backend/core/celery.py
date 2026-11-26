import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("sports_bot")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "scan-odds-every-30-seconds": {
        "task": "trading_engine.tasks.scan_market_odds",
        "schedule": 30.0,
    },
    "refresh-fixtures-daily": {
        "task": "data_ingestion.tasks.fetch_all_upcoming_fixtures",
        "schedule": crontab(hour=6, minute=0),
    },
    "refresh-match-stats-hourly": {
        "task": "data_ingestion.tasks.refresh_stats_for_upcoming_matches",
        "schedule": crontab(minute=0),
    },
    "refresh-odds-for-live-window": {
        "task": "data_ingestion.tasks.refresh_odds_for_live_window",
        "schedule": crontab(minute="*/15"),
    },
    "project-xg-hourly": {
        "task": "ml_models.tasks.project_xg_for_upcoming_matches",
        "schedule": crontab(minute=30),
    },
    "reconciliar-analisis-hourly": {
        "task": "ml_models.tasks.reconciliar_analisis",
        "schedule": crontab(minute=45),
    },
    "generar-combinadas-cada-15-minutos": {
        "task": "trading_engine.tasks.generar_combinadas_pendientes",
        "schedule": crontab(minute="10,25,40,55"),
    },
}
