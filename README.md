# ValueBet — Bot de Trading Deportivo (ML + Kelly)

![ValueBet](frontend/src/assets/logo-full.png)

Bot automatizado que combina modelos predictivos (Machine Learning) y gestión de
riesgo matemática (Criterio de Kelly fraccional) para identificar y ejecutar
"value bets" en exchanges de apuestas deportivas. Ver [prompt.md](prompt.md) para
el contexto completo del diseño y las decisiones de arquitectura.

## Estado actual

Scaffold funcional de punta a punta:

- **Backend Django + DRF** con modelos de datos (`Equipo`, `Partido`,
  `HistorialCuotas`, `Operacion`), API REST, y admin.
- **Ingesta de datos** vía [api-football.com](https://www.api-football.com/)
  (versión gratuita, con throttling) + clima vía Open-Meteo.
- **Modelo predictivo** con fallback de Poisson sobre xG mientras no haya un
  modelo de XGBoost entrenado con datos históricos propios.
- **Motor de trading**: Kelly fraccional (`risk_manager.py`) + cliente de
  exchange con modo *paper trading* simulado (sin necesidad de credenciales de
  Betfair) y una implementación real de Betfair Exchange lista para cuando haya
  cuenta y certificados.
- **Celery + Redis** para tareas periódicas (ingesta de fixtures, escaneo de
  cuotas cada 30s).
- **Dashboard React** (Vite) con PNL acumulado, historial de operaciones y
  panel de configuración de riesgo.

Lo que falta y es el siguiente paso natural: entrenar el modelo de XGBoost con
datos históricos reales (`ml_models/notebooks/`) y, cuando haya cuenta de
Betfair, cargar sus credenciales para pasar de modo *paper* a ejecución real.

## Requisitos

- Python 3.12+
- Node.js 20+
- Docker + Docker Compose (para el despliegue completo con Postgres/Redis)
- Una API key gratuita de [api-football.com](https://www.api-football.com/)

## Desarrollo local (sin Docker)

### Backend

```bash
cd backend
python -m venv venv
./venv/Scripts/activate        # Windows
# source venv/bin/activate     # Linux/Mac
pip install -r requirements.txt

cp .env.example .env
# Edita .env: como mínimo agrega tu API_FOOTBALL_KEY.
# Para no depender de Postgres/Redis localmente, deja DATABASE_ENGINE=sqlite.

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

La API queda en `http://localhost:8000/api/` y el admin en `/admin/`.

Para las tareas asíncronas (ingesta, escaneo de cuotas) necesitas Redis
corriendo y, en otra terminal:

```bash
celery -A core worker --loglevel=info      # en Windows agregar --pool=solo (ver nota abajo)
celery -A core beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

Con esto corriendo (Redis + worker + beat), el pipeline queda automatizado según
el `beat_schedule` de `core/celery.py` -- ya no hace falta correr
`run_pipeline_once` a mano.

#### Redis en Windows (sin Docker)

Windows no tiene un build oficial de Redis. La forma más simple es correrlo
dentro de WSL2:

```bash
wsl --install -d Ubuntu     # una sola vez, si no tenés ya una distro Linux
wsl -d Ubuntu
sudo apt-get update && sudo apt-get install -y redis-server
sudo service redis-server start
```

WSL2 expone `127.0.0.1` de la distro al Windows host automáticamente, así que
`REDIS_URL=redis://localhost:6379/0` en `backend/.env` funciona sin cambios.
El servicio queda habilitado (`systemctl enable`) para arrancar solo la
próxima vez que reinicies esa distro, pero **WSL2 no arranca solo al prender
Windows** -- necesitás abrir esa distro (`wsl -d Ubuntu`, aunque sea sin
hacer nada más) antes de levantar el worker/beat.

En Windows, el pool por default de Celery (`prefork`) no funciona porque
depende de `fork()`. Usá `--pool=solo` (o `--pool=threads`) para el worker.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

El dashboard queda en `http://localhost:5173/` y proxea `/api` hacia
`http://localhost:8000` (configurado en `vite.config.js`).

### Tests automatizados

```bash
cd backend
python manage.py test
```

Cubre la lógica de negocio más sensible: Kelly fraccional (`trading_engine/tests`),
el modelo de Poisson y los ratings de ataque/defensa con shrinkage y ventaja de
localía (`ml_models/tests`), el ciclo de vida de una recomendación y la
reconciliación de resultados reales (`db_models/tests`), y los endpoints de la
API (`api/tests`). No necesita Redis ni credenciales reales -- usa una base de
datos de prueba aparte que Django crea y destruye solo.

## Acceso desde el celular (misma red Wi-Fi)

Con el backend y el frontend corriendo (ver arriba), para entrar desde el celular:

1. **Encontrá la IP de tu PC en la red** (Windows, PowerShell): `ipconfig` y buscá la
   `Dirección IPv4` del adaptador Wi-Fi conectado (ej. `192.168.1.8`).
2. **Agregá esa IP a `backend/.env`** (ya viene comentado en `.env.example`):
   ```
   DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.8
   CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://192.168.1.8:5173
   ```
   (`vite.config.js` ya tiene `server.host: true`, así que Vite escucha en todas las
   interfaces sin cambios adicionales.)
3. **Levantá Django escuchando en la red, no solo localhost**:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```
4. **Abrí el firewall de Windows** para esos dos puertos -- en una PowerShell **como
   Administrador** (clic derecho → "Ejecutar como administrador"):
   ```powershell
   New-NetFirewallRule -DisplayName "ValueBet Dev - Vite 5173" -Direction Inbound -Protocol TCP -LocalPort 5173 -Action Allow -Profile Any
   New-NetFirewallRule -DisplayName "ValueBet Dev - Django 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Any
   ```
   Si el perfil de tu red Wi-Fi en Windows está como "Público" (`Get-NetConnectionProfile`),
   estas reglas igual dejan pasar el tráfico en esos dos puertos puntuales -- no hace
   falta cambiar el perfil de red a "Privado".
5. **En el celular** (conectado al mismo Wi-Fi), abrí `http://192.168.1.8:5173/` en el
   navegador (Chrome/Safari), usando la IP que sacaste en el paso 1.

### "Instalar" la app en la pantalla de inicio

El dashboard tiene un manifest de PWA (`frontend/public/manifest.json`) con ícono y
nombre propios. En el celular, abrí el menú del navegador y elegí **"Agregar a
pantalla de inicio"** (Chrome/Android) o **"Agregar a inicio"** (Safari/iOS) -- queda
como un ícono más, se abre a pantalla completa sin la barra del navegador.

Esto **no es una instalación real desde una tienda de apps** -- es un atajo del
navegador. El "banner de instalación" automático que ofrecen algunos navegadores
(Chrome en Android) generalmente pide HTTPS, y acá se sirve por HTTP dentro de la red
local -- así que hay que agregarlo a mano desde el menú en vez de esperar el banner,
pero el resultado visual (ícono propio, sin barra de navegador) es el mismo.

## Despliegue con Docker

```bash
cp backend/.env.example backend/.env
# Edita backend/.env con tus credenciales reales.

docker compose -f docker/docker-compose.yml up --build
```

Esto levanta: Postgres, Redis, el backend Django (con gunicorn), el worker y
el beat de Celery, y el frontend servido por Nginx (que proxea `/api` al
backend). El frontend queda en `http://localhost:5173/` y el backend en
`http://localhost:8000/`.

## Variables de entorno (`backend/.env`)

| Variable | Descripción |
|---|---|
| `DJANGO_SECRET_KEY` | Clave secreta de Django (generar una real en producción) |
| `DJANGO_DEBUG` | `True`/`False` |
| `DATABASE_ENGINE` | `postgresql` (default) o `sqlite` para dev rápido sin Postgres |
| `POSTGRES_*` | Credenciales de la base de datos |
| `REDIS_URL` | URL de Redis para Celery |
| `API_FOOTBALL_KEY` | API key de api-football.com (plan gratuito) |
| `WATCHED_LEAGUES` | IDs de ligas a monitorear, ej. `265` (Primera División de Chile). El plan gratuito de api-football no permite pedir fixtures por `season`, solo por fecha (ver nota abajo) |
| `BETFAIR_APP_KEY`, `BETFAIR_USERNAME`, `BETFAIR_PASSWORD`, `BETFAIR_CERT_PATH` | Credenciales de Betfair Exchange. Mientras estén vacías, el bot opera en modo *paper trading* simulado |
| `PAPER_BANKROLL`, `KELLY_FRACTION`, `MAX_STAKE_PER_BET`, `MIN_EDGE_THRESHOLD` | Valores **iniciales** de gestión de riesgo -- solo se usan para sembrar la fila de configuración la primera vez (`ConfiguracionRiesgo.actual()`). Una vez creada esa fila, se editan desde el dashboard (pestaña **Configuración**) y estas variables de `.env` dejan de tener efecto |

## xG: no existe un proveedor gratis para la liga chilena

Investigamos las fuentes obvias: Understat y FBref (las gratuitas más conocidas)
solo cubren las 5-6 ligas top de Europa; FootyStats sí tiene xG para la Primera
División de Chile pero es pago (~£30/mes, sin plan gratuito permanente); y
api-football no calcula xG para esta liga ni siquiera en sus stats detalladas
(confirmado contra un partido ya jugado).

En vez de depender de un proveedor pago o de un prior inventado, `ml_models/pipelines/team_ratings.py`
construye un **xG "proxy"** con datos que api-football sí entrega gratis (tiros
dentro/fuera del área por partido), usando tasas de conversión promedio de
referencia, y arma un rating de ataque/defensa por equipo (mismo principio que
un modelo de Poisson tipo Dixon-Coles) para proyectar el xG esperado de los
próximos partidos. `ml_models/tasks.py:project_xg_for_upcoming_matches` corre
cada hora y deja `xg_local`/`xg_visitante` en `Partido.metricas_avanzadas` para
que `predictor.py` los use.

Esto **necesita historial real jugado** para tener señal: un equipo necesita
al menos `MIN_PARTIDOS_PARA_RATING` (3) partidos finalizados y capturados antes
de que su proyección se use; hasta entonces, `predictor.py` sigue cayendo al
prior neutro (45/27/28%). No hay atajo para esto — hay que dejar correr el bot
en modo *paper trading* varias semanas para que el rating tenga base real antes
de confiar en las señales que genere.

## Investigación manual con Claude/Gemini (sin API de pago)

Si no tenés una API key de pago de Anthropic/Google (la suscripción de chat de
Claude Pro o Gemini Pro **no** incluye acceso de API para automatizar nada),
y como los partidos de esta liga son semanales, el flujo pensado es manual:

```bash
python manage.py print_weekly_prompt
```

Esto arma un prompt con los próximos partidos ya cargados en tu base y te
pide pegarlo en Claude.ai o Gemini (usando su búsqueda web) para que investigue
lesiones, forma reciente y xG de cada equipo. El resultado se carga en
**Admin -> Partidos -> (el partido) -> "xG local / xG visitante (investigación
manual)"**. Un valor cargado así queda marcado internamente como fuente
`"manual"` y `project_xg_for_upcoming_matches` (la proyección automática por
estadísticas, ver más abajo) nunca lo pisa.

Si en el futuro conseguís una API key real (console.anthropic.com o Google AI
Studio), esto se puede automatizar con una tarea de Celery que llame al modelo
directamente en vez de depender de copiar/pegar.

## Limitaciones reales del plan gratuito de api-football

Verificado en vivo contra la API (no es solo lo que dice la documentación):

- El parámetro `next` (traer los próximos N partidos) **no está disponible**.
- Combinar `league` + `season` **solo funciona con temporadas ya cerradas**
  (no la actual, ej. 2026).
- Consultar `/fixtures?date=X` (sin liga ni temporada) sí funciona, pero
  **solo dentro de una ventana de ±1 día respecto a hoy**.

Por eso `fetch_upcoming_fixtures` pide fixtures de **hoy y mañana para todas
las ligas** y filtra la liga chilena (`WATCHED_LEAGUES`) en el cliente, en vez
de pedir "los próximos N partidos" directamente. Esto corre todos los días
(ver `celery.py`), así que el calendario se va completando día a día. Si en
algún momento migras a un plan pago, `get_fixtures` puede volver a extenderse
para traer rangos de fechas más amplios de una sola vez.

## Estructura del proyecto

Ver [prompt.md](prompt.md) sección 4 para el detalle completo de la
arquitectura de carpetas.
