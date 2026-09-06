# Master Prompt: Dashboard Predictivo de Fútbol (Goles Esperados) — Primera División de Chile

> **Historial**: este documento arrancó como la especificación de un "bot de trading deportivo" que
> ejecutaba apuestas automáticamente. A medida que se construyó, el objetivo cambió: hoy es una
> **herramienta de apoyo a la decisión** — analiza y predice goles esperados (xG) con un modelo
> estadístico propio, y sugiere apuestas de valor para que las revise una persona, pero **no ejecuta
> nada por su cuenta**. Este documento refleja el estado actual real del proyecto, no el plan original.

## 1. Contexto para el Desarrollador

Este es un dashboard de análisis predictivo enfocado en la **Primera División de Chile** (Liga de
Primera). Su función principal es proyectar los **goles esperados (xG)** de cada equipo para sus
próximos partidos, usando un modelo estadístico de ataque/defensa calibrado con resultados reales.
Como función secundaria, también detecta y sugiere "apuestas de valor" (value bets) cuando el
modelo cree que una cuota de mercado está mal calibrada — pero la decisión de apostar, y la
ejecución misma, siempre las toma la persona, nunca el sistema.

No hay ejecución automática de apuestas en ningún lado del código: no hay credenciales de
Betfair conectadas, y aunque existiera la integración, el escáner de valor (`trading_engine/scanner.py`)
está diseñado explícitamente para **solo generar una recomendación**, nunca para llamar a
`exchange_client.place_order()`.

## 2. Los Desafíos del Sistema (Restricciones Core)

### 2.1 El Cuello de Botella de los Datos (Data Quality)

- **El costo de la información**: las APIs gratuitas dan resultados y goles, pero no xG real ni
  lesiones — eso ya está reflejado en las cuotas de mercado y no da ventaja. Confirmamos en la
  práctica que **api-football no tiene xG ni lesiones para esta liga** (ver sección 8). La
  respuesta fue no depender de un proveedor de xG pago, sino **calcular un rating de ataque/defensa
  propio a partir de goles reales** (ver sección 4) — con casi 650 partidos de 3 temporadas
  (2024, 2025, 2026), es una base más confiable que lo que cualquier API gratuita ofrece para esta
  liga específica.
- **La varianza del fútbol**: el modelo puede proyectar 2.3 goles esperados para un equipo y aun
  así perder 0-1 por una tarjeta roja al minuto 5. Por eso el sistema nunca presenta una
  proyección como certeza — ver sección 4.4 sobre por qué se usa regularización estadística
  (shrinkage) en vez de confiar ciegamente en el promedio crudo de pocos partidos.

### 2.2 Desafíos de Arquitectura y Código

- **Latencia**: dejó de ser una restricción crítica de diseño. Como no hay ejecución automática de
  apuestas, no importa si el escaneo tarda unos segundos — el flujo es: el sistema genera una
  recomendación, una persona la revisa y decide, y el partido normalmente empieza horas o días
  después. Sigue existiendo un escaneo periódico (Celery beat, cada 30s) por si se quiere
  reaccionar rápido a movimientos de cuota, pero no es un requisito duro del sistema.
- **Sobreajuste (Overfitting)**: se mitiga con **regularización estadística** (shrinkage hacia el
  promedio de la liga cuando un equipo tiene pocos partidos) en vez de un modelo de ML complejo
  entrenado sobre pocos datos. `ml_models/predictor.py` tiene un *hook* para cargar un modelo
  entrenado (XGBoost, vía `ml_models/weights/model.joblib`) si en el futuro se entrena uno con
  más historial, pero **hoy no hay ningún modelo entrenado cargado** — todo corre sobre el
  modelo de Poisson ataque/defensa (ver sección 4).

### 2.3 Las Reglas de la Industria

- **El Margen (Vig)**: sigue siendo la razón de ser de la sección de Recomendaciones — el sistema
  busca específicamente los casos donde la probabilidad real (según el modelo) supera lo que
  paga la cuota de mercado, no solo "quién gana más seguido" (ver la explicación de value betting
  más abajo, sección 5).
- **El "Banhammer"**: ya no es una preocupación de diseño activa, precisamente porque no hay
  ejecución automática — una persona decidiendo manualmente dónde y cuánto apostar no dispara los
  mismos sistemas de detección que un bot ejecutando órdenes. El código de `exchange_client.py`
  (incluyendo el soporte para Betfair real) se mantiene por si en el futuro se agrega ejecución,
  pero es una capacidad latente, no algo que el sistema use hoy.

## 3. Metodología del Modelo Predictivo

Todo vive en `backend/ml_models/pipelines/team_ratings.py` y `backend/ml_models/predictor.py`.

### 3.1 Rating de ataque/defensa por equipo

Para cada equipo, se calcula el promedio de goles a favor ("ataque") y en contra ("defensa") en
sus últimos partidos reales (hasta 15), usando **goles reales del resultado final**, no una
estimación. La fuente de esos partidos son:

1. Los partidos que api-football va completando día a día (temporada 2026 en curso).
2. Un dataset importado a mano de las fechas 1-21 de la temporada 2026, investigado con
   Claude/Gemini (`data_ingestion/historical_datasets/liga_chile_2026.py`,
   `manage.py import_historical_dataset`).
3. Un dataset Excel con las temporadas 2024 y 2025 completas
   (`data_ingestion/historical_datasets/liga_chile_2024_2025.xlsx`,
   `manage.py import_excel_dataset`) — casi 650 partidos en total entre las tres temporadas.

### 3.2 Regularización (shrinkage)

Un equipo con pocos partidos jugados y una racha marcada en ambos extremos (ataque muy alto +
rival con defensa muy mala) puede disparar la proyección multiplicativa a valores poco creíbles.
`calcular_ratings()` aplica shrinkage tipo James-Stein/Bayes empírico: el rating de cada equipo se
mezcla con el promedio de la liga, ponderado por cuántos partidos tiene jugados
(`K_SHRINKAGE = 8`) — un equipo con muchos partidos se acerca a su promedio real, uno con pocos se
acerca más al promedio general.

### 3.3 Ventaja de localía

Medido con datos reales: los locales en esta liga anotan ~35-38% más goles que los visitantes
(confirmado con ambas muestras, la de 170 y la de 649 partidos — el número no cambió, lo que
valida que es un efecto real y no ruido). El modelo aplica un factor de ajuste global
(`_factor_localia()`) sobre la proyección de ataque según si el equipo juega de local o de visita
— no se separan los ratings de ataque/defensa por localía por equipo individual porque, con el
volumen de datos actual, eso dejaría muestras demasiado chicas por equipo para ser confiables.

### 3.4 Proyección final y probabilidades

`proyectar_xg()` combina ataque del equipo (ajustado por localía) × defensa del rival / promedio
de liga, dando el xG esperado de cada equipo para un partido específico. A partir de esos dos
números, `predictor.py` calcula con un modelo de Poisson independiente:

- La probabilidad de victoria local / empate / victoria visitante (1X2).
- La probabilidad de que el total de goles supere una línea dada (mercado Over/Under).

**Si algún equipo no tiene al menos 3 partidos jugados y cargados, el sistema no inventa un
número** — retorna "sin datos suficientes" explícitamente. Esto fue una corrección deliberada:
la primera versión usaba un prior neutro (45/27/28%) cuando faltaban datos, lo que generaba
"value bets" que eran puro ruido (comparar un número inventado contra una cuota real siempre
"encuentra" edge falso). Ver sección 8 para más antecedentes de decisiones así.

### 3.5 xG "proxy" por tiros (código legacy, sin uso activo)

Antes de tener suficiente historial de goles reales, se había construido un xG aproximado a partir
de estadísticas de tiros (dentro/fuera del área) por partido, con tasas de conversión de
referencia (`calcular_proxy_xg_partido`, `calcular_proxy_xg_equipo`). Esas funciones se mantienen
en el código y `fetch_match_statistics` las sigue calculando y guardando para partidos finalizados
(`metricas_avanzadas["proxy_xg"]`), pero **`calcular_ratings()` ya no las usa** — la señal
principal son los goles reales del resultado, que son más confiables que una aproximación por
tiros. Se dejaron por si en el futuro sirven para afinar el modelo con más granularidad.

## 4. Value Betting: la idea central de las Recomendaciones

Apostar por valor **no es apostar a quién gana más seguido** — es apostar donde el precio de
mercado no refleja bien la probabilidad real. El sistema puede (y suele) recomendar el equipo que
el propio modelo considera *no favorito*, si la cuota que paga el mercado por esa selección es más
generosa de lo que la probabilidad real justificaría. Ejemplo real detectado durante el desarrollo:
un equipo con 50.5% de probabilidad real de ganar (favorito) contra un rival con 29.1%, donde el
mercado pagaba una cuota que implicaba solo 25% para el rival — ahí hay edge en el rival, aunque
siga siendo menos probable que gane. El edge es una propiedad estadística de largo plazo, no una
predicción de que esa apuesta puntual vaya a ganar.

Importante: **cada recomendación es independiente**. Si el sistema sugiere "Equipo A gana" y
"Más de 4.5 goles" en el mismo partido, son dos ideas separadas, no una combinada — apostar ambas
juntas (tipo parlay) tiene una probabilidad real mucho menor que cualquiera de las dos por separado
(la probabilidad conjunta no es la multiplicación ingenua de los edges).

## 5. Flujo de una Recomendación (`db_models.models.Operacion`)

```
RECOMENDADA  -- el escáner encontró un edge, stake sugerido vía Kelly fraccional
    │
    ├── ACEPTADA   (la persona decide apostarla, en la casa/exchange que prefiera)
    │       │
    │       ├── GANADA   (se calcula el PNL automáticamente: stake × (cuota - 1))
    │       └── PERDIDA  (PNL = -stake)
    │
    └── DESCARTADA (la persona decide no tomarla)
```

Estas transiciones se pueden hacer desde botones directos en el dashboard (pestaña
Recomendaciones) o desde `/admin/db_models/operacion/` (acciones en lote). La lógica de cálculo de
PNL vive una sola vez, como métodos del modelo `Operacion` (`aceptar()`, `descartar()`,
`marcar_ganada()`, `marcar_perdida()`), reutilizada tanto por el admin como por la API.

El escáner (`trading_engine/scanner.py`) evalúa el mercado 1X2 y el de goles totales
(Over/Under, líneas 1.5 a 4.5 — las más líquidas), pero **nunca genera más de una recomendación
por "familia" de mercado por partido** (una para 1X2, una para Over/Under): todas las líneas de
Over/Under de un mismo partido están altamente correlacionadas entre sí (son la misma apuesta a
"muchos/pocos goles" repetida), así que se queda solo con la de mayor edge.

## 6. Gestión de Riesgo (Kelly Fraccional)

`trading_engine/risk_manager.py` implementa Kelly fraccional (`KELLY_FRACTION`, default 25% del
Kelly completo) sobre un **bankroll de referencia** configurable (`PAPER_BANKROLL`, en pesos
chilenos — se ajusta a mano en `backend/.env` para que el stake sugerido tenga sentido con la
plata real disponible en la casa/exchange que se use). Hay además un tope duro
(`MAX_STAKE_PER_BET`) y un edge mínimo para considerar algo "recomendable"
(`MIN_EDGE_THRESHOLD`, default 5%).

## 7. Stack Tecnológico

- **Backend**: Python + Django + Django REST Framework
- **Base de datos**: SQLite en desarrollo (`DATABASE_ENGINE=sqlite`), PostgreSQL soportado para
  producción (campos JSONB para métricas variables en `Partido.metricas_avanzadas`)
- **Modelo predictivo**: estadística clásica (Poisson + shrinkage), sin librerías de ML pesadas en
  el camino activo — pandas/scikit-learn/xgboost siguen en `requirements.txt` por si se entrena un
  modelo con más datos en el futuro, pero no hay ningún modelo entrenado cargado hoy
- **Tareas asíncronas**: Celery + Redis, para refrescar fixtures/cuotas/proyecciones
  periódicamente (ver `core/celery.py`) — también hay un comando (`run_pipeline_once`) que corre
  todo el pipeline de forma sincrónica, sin necesitar Redis, para desarrollo local rápido
- **Frontend**: React (Vite), sin TypeScript
- **Fuentes de datos externas**: api-football.com (plan gratuito), Open-Meteo (clima, gratis sin
  API key), y dos datasets históricos importados manualmente (ver sección 3.1)

## 8. Arquitectura de Carpetas del Proyecto (estado real)

```text
/ValueBet
│
├── /backend
│   ├── /core                       # settings.py, urls.py, celery.py (beat schedule)
│   ├── /api                        # Endpoints DRF que consume el frontend
│   │   └── views.py                # ViewSets + acciones (prediccion, ratings, aceptar, marcar-ganada, ...)
│   │
│   ├── /data_ingestion
│   │   ├── api_clients/
│   │   │   └── football_api.py     # Cliente de api-football (throttled, documenta límites reales del free tier)
│   │   ├── scrapers/
│   │   │   └── weather.py          # Clima vía Open-Meteo (gratis, sin API key)
│   │   ├── historical_datasets/    # Datasets importados a mano (no dependen de ninguna API)
│   │   │   ├── liga_chile_2026.py            # Fechas 1-21 2026, investigado con Claude/Gemini
│   │   │   └── liga_chile_2024_2025.xlsx     # Temporadas 2024 y 2025 completas
│   │   ├── management/commands/
│   │   │   ├── import_historical_dataset.py  # Importa liga_chile_2026.py
│   │   │   └── import_excel_dataset.py       # Importa el Excel 2024/2025
│   │   └── tasks.py                # Fixtures, cuotas (1X2 + Over/Under), stats/clima -- tareas Celery
│   │
│   ├── /ml_models
│   │   ├── pipelines/
│   │   │   ├── features.py         # (legacy) features para un futuro modelo entrenado
│   │   │   └── team_ratings.py     # Rating ataque/defensa, shrinkage, ventaja de localía, proyección de xG
│   │   ├── management/commands/
│   │   │   └── print_weekly_prompt.py  # Genera el prompt para investigar con Claude/Gemini (xG manual)
│   │   ├── weights/                 # Vacío hoy -- acá iría model.joblib si se entrena uno
│   │   ├── predictor.py            # MatchPredictor: xG, probabilidades 1X2, probabilidad Over/Under
│   │   └── tasks.py                # project_xg_for_upcoming_matches (tarea Celery)
│   │
│   ├── /trading_engine
│   │   ├── risk_manager.py         # Kelly fraccional
│   │   ├── scanner.py              # Detecta valor y genera Operacion (RECOMENDADA) -- nunca ejecuta
│   │   ├── exchange_client.py      # PaperExchangeClient (activo) + BetfairExchangeClient (sin usar, sin credenciales)
│   │   ├── management/commands/
│   │   │   └── run_pipeline_once.py  # Corre todo el pipeline sin Celery/Redis
│   │   └── tasks.py                # scan_market_odds (tarea Celery)
│   │
│   ├── /db_models
│   │   ├── models.py               # Equipo, Partido, HistorialCuotas, Operacion
│   │   ├── admin.py                # Incluye el form de xG manual y las acciones de Operacion
│   │   └── serializers.py
│   │
│   ├── requirements.txt
│   ├── manage.py
│   ├── .env                        # No versionado -- credenciales y parámetros reales
│   └── .env.example
│
├── /frontend                       # React + Vite, sin TypeScript
│   ├── /src
│   │   ├── /pages
│   │   │   ├── Predicciones.jsx    # Página principal: xG proyectado + favorito por partido
│   │   │   ├── Equipos.jsx         # Ranking de ataque/defensa por equipo
│   │   │   ├── Recomendaciones.jsx # Pestaña secundaria: value bets, PNL, botones de acción
│   │   │   └── Configuracion.jsx   # Estado de fuentes de datos y parámetros de riesgo
│   │   ├── /components             # Card, InfoBox, MatchCard, OperationsTable, StatusBadge, ...
│   │   ├── /services/api.js        # Llamadas Axios a la API de Django
│   │   └── /utils/format.js        # Moneda (CLP), porcentajes, nombres de mercado en español
│   ├── package.json
│   └── vite.config.js              # Proxea /api al backend en dev
│
├── /docker                         # docker-compose.yml + Dockerfiles -- escritos pero nunca probados
│                                    # (no hay Docker instalado en la máquina de desarrollo actual)
│
├── README.md                       # Instrucciones de instalación, variables de entorno, limitaciones de api-football
└── prompt.md                       # Este documento
```

## 9. Limitaciones Conocidas y Decisiones Tomadas

Estas son cosas que se investigaron y decidieron activamente durante el desarrollo — vale la pena
no repetir la investigación si se vuelve a plantear la misma pregunta:

- **api-football (plan gratuito) no tiene xG ni lesiones para esta liga.** Confirmado en vivo,
  sin restricción de plan (la API responde sin error, con 0 resultados) — no es un límite de cuota,
  es que el proveedor no cubre esa liga a ese nivel de detalle. Por eso el modelo usa goles reales
  en vez de xG de proveedor, y no hay ningún ajuste automático por lesiones.
- **api-football tiene reglas no documentadas claramente**: no acepta el parámetro `next`; no
  permite pedir `league` + `season` para la temporada actual (solo temporadas ya cerradas); y
  `/fixtures?date=X` solo acepta fechas dentro de ±1 día de hoy. La solución implementada es
  recorrer día a día (ayer/hoy/mañana) pidiendo por fecha sin liga ni temporada, filtrando la liga
  chilena en el cliente.
- **Se evaluó y se descartó (por ahora) usar LanusStats** (librería de scraping de
  SofaScore/FotMob que sí tiene xG real para esta liga) por el riesgo de scraping no oficial
  (rompe sin aviso, zona gris de ToS) y porque conseguir el dataset histórico real (Excel 2024/2025
  + investigación manual) resultó más valioso y sin ese riesgo.
- **No hay modelo de Machine Learning entrenado** (a pesar de que XGBoost/scikit-learn están en
  `requirements.txt`) — con ~650 partidos y pocas features por partido, un modelo de Poisson
  regularizado es más robusto que entrenar un clasificador que probablemente sobreajuste. El hook
  para cargar un modelo entrenado (`ml_models/weights/model.joblib`) existe por si esto cambia.
- **Docker nunca se probó en la práctica** — los archivos (`docker/docker-compose.yml`,
  Dockerfiles) están escritos siguiendo el plan original, pero no hay Docker instalado en la
  máquina de desarrollo actual, así que el flujo real de desarrollo es sin contenedores (venv +
  `manage.py runserver` + `npm run dev`, ver README).
- **La inferencia manual de xG** (`manage.py print_weekly_prompt` + campo de xG manual en el
  admin) existe porque el desarrollador tiene Claude Pro / Gemini Pro (suscripción de chat), no
  una API key de pago — no hay forma de automatizar una llamada a esos modelos desde el backend
  sin esa key. Si en algún momento se consigue una API key real, esto se podría automatizar con
  una tarea de Celery en vez de depender de copiar/pegar.
