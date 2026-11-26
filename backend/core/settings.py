"""
Django settings for the sports_bot project (core).
"""

from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Security -----------------------------------------------------------
SECRET_KEY = config("DJANGO_SECRET_KEY", default="dev-insecure-secret-key-change-me")
DEBUG = config("DJANGO_DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

# --- Applications ---------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 3rd party
    "rest_framework",
    "django_filters",
    "corsheaders",
    "django_celery_beat",
    # local apps
    "db_models",
    "api",
    "data_ingestion",
    "ml_models",
    "trading_engine",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"
ASGI_APPLICATION = "core.asgi.application"

# --- Database -------------------------------------------------------------
# Defaults match the "db" service in docker/docker-compose.yml.
# Set DATABASE_ENGINE=sqlite for quick local development without Postgres.
if config("DATABASE_ENGINE", default="postgresql") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("POSTGRES_DB", default="sports_bot"),
            "USER": config("POSTGRES_USER", default="sports_bot"),
            "PASSWORD": config("POSTGRES_PASSWORD", default="sports_bot"),
            "HOST": config("POSTGRES_HOST", default="localhost"),
            "PORT": config("POSTGRES_PORT", default="5432"),
        }
    }

# --- Password validation ---------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internationalization ---------------------------------------------------
LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

# --- Static files -----------------------------------------------------------
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- CORS (React dev server) -------------------------------------------------
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173,http://127.0.0.1:5173",
    cast=Csv(),
)

# --- Django REST Framework ---------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
}

# --- Celery -------------------------------------------------------------------
CELERY_BROKER_URL = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# --- Project specific settings ------------------------------------------------
# api-football.com (free tier: https://www.api-football.com/)
API_FOOTBALL_KEY = config("API_FOOTBALL_KEY", default="")
API_FOOTBALL_BASE_URL = config(
    "API_FOOTBALL_BASE_URL", default="https://v3.football.api-sports.io"
)
# Free tier is rate limited (100 req/day, 10 req/min) -- clients must throttle.
API_FOOTBALL_RATE_LIMIT_PER_MINUTE = config(
    "API_FOOTBALL_RATE_LIMIT_PER_MINUTE", default=10, cast=int
)
# Ligas a monitorear: lista de league_id, ej. "265,140".
# 265 = Primera División de Chile en api-football (id confirmado vía /leagues?country=Chile).
# No se pide temporada: el plan gratuito solo permite consultar fixtures por
# fecha (ver data_ingestion/api_clients/football_api.py), no por season+league.
WATCHED_LEAGUES = [
    int(league_id) for league_id in config("WATCHED_LEAGUES", default="265", cast=Csv()) if league_id
]

# Betfair Exchange API (left blank until credentials are available).
BETFAIR_APP_KEY = config("BETFAIR_APP_KEY", default="")
BETFAIR_USERNAME = config("BETFAIR_USERNAME", default="")
BETFAIR_PASSWORD = config("BETFAIR_PASSWORD", default="")
BETFAIR_CERT_PATH = config("BETFAIR_CERT_PATH", default="")

# Bankroll de referencia para calcular el stake sugerido (Kelly). Es solo una
# cifra de referencia -- el sistema no toca plata real, es lo que le decís
# que tenés disponible en tu casa/exchange para que el stake sugerido tenga
# sentido con tu billetera real, no con un monto de prueba inventado.
PAPER_BANKROLL = config("PAPER_BANKROLL", default=5000.0, cast=float)

# Risk management defaults (Kelly Criterion).
KELLY_FRACTION = config("KELLY_FRACTION", default=0.25, cast=float)  # quarter-Kelly
MAX_STAKE_PER_BET = config("MAX_STAKE_PER_BET", default=500.0, cast=float)
MIN_EDGE_THRESHOLD = config("MIN_EDGE_THRESHOLD", default=0.05, cast=float)  # 5%

# Un edge positivo no alcanza por sí solo para que una recomendación individual
# "se sienta bien": un pick con 25-30% de probabilidad va a perder la mayoría
# de las veces aunque tenga valor a largo plazo, y eso no es lo que se pidió
# ("tratando de acertar", no maximizar EV puro). Este piso no descarta el edge
# -- si el mismo partido tiene una versión más seguro de la misma señal (ej.
# Doble Oportunidad en vez de 1X2 a secas), esa sigue recomendándose normal.
PROBABILIDAD_MINIMA_SELECCION = config("PROBABILIDAD_MINIMA_SELECCION", default=0.40, cast=float)  # 40%
