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
  propio a partir de goles reales** (ver sección 4) — con más de 1100 partidos de 5 temporadas
  (2022-2026), es una base más confiable que lo que cualquier API gratuita ofrece para esta
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
   `manage.py import_excel_dataset`).
4. Un dataset Excel con las temporadas 2022 y 2023 completas
   (`data_ingestion/historical_datasets/liga_chile_2022_2023.xlsx`,
   `manage.py import_excel_dataset_2022_2023`) — más de 1130 partidos en total entre las cinco
   temporadas (2022-2026).

   De los tres equipos ya descendidos que en su momento quedaron sin `api_football_id`
   confirmado, dos ya lo tienen (Curicó Unido, Magallanes) -- solo **Deportes Antofagasta sigue
   pendiente**. Si vuelve a Primera y aparece en un fixture en vivo,
   `data_ingestion/tasks.py:_get_or_create_equipo` matchea estrictamente por `api_football_id`
   (no por nombre), así que crearía un `Equipo` duplicado en vez de reusar el existente. Conviene
   completar su id real (`GET /teams?search=...`) antes de que eso pase.

   Aparte, `data_ingestion/historical_datasets/liga_chile_contexto_2022_2026.xlsx`
   (`manage.py importar_contexto_partidos`) agrega sede/ciudad/altitud por club
   (`Equipo.metadata["sede"]`) y contexto por partido -- distancia de viaje, derbi, altitud,
   descanso -- (`Partido.metricas_avanzadas["contexto_2022_2026"]`, 1122/1128 partidos cargados).
   Es **contexto informativo únicamente**: no toca `calcular_ratings()` ni `proyectar_xg()` hasta
   que alguno de esos factores pase por la auditoría de la sección 10 (ver
   `HANDOFF_dataset_contexto.md` en la raíz del repo para el detalle completo, incluidas
   correlaciones crudas de viaje y altura que todavía no se validaron contra backtest).

### 3.2 Regularización (shrinkage)

Un equipo con pocos partidos jugados y una racha marcada en ambos extremos (ataque muy alto +
rival con defensa muy mala) puede disparar la proyección multiplicativa a valores poco creíbles.
`calcular_ratings()` aplica shrinkage tipo James-Stein/Bayes empírico: el rating de cada equipo se
mezcla con el promedio de la liga, ponderado por cuántos partidos tiene jugados
(`K_SHRINKAGE = 8`) — un equipo con muchos partidos se acerca a su promedio real, uno con pocos se
acerca más al promedio general.

### 3.3 Ventaja de localía

Medido con datos reales sobre las cinco temporadas completas (2022-2026, 1137 partidos): los
locales anotan en promedio **28,9% más goles** que los visitantes -- no el 35-38% que decía esta
sección antes. Esa cifra vieja salió de mirar solo 2025 y 2026 (dos temporadas altas, 41,4% y
34,9%), y la lectura de "no cambió entre dos muestras" fue un artefacto de comparar dos
temporadas parecidas entre sí, no evidencia real de estabilidad. Con las cinco:

| Temporada | GF local | GF visita | Ventaja |
|---|---|---|---|
| 2022 | 1,488 | 1,079 | +37,8% |
| 2023 | 1,425 | 1,300 | +9,6% |
| 2024 | 1,540 | 1,222 | +26,0% |
| 2025 | 1,550 | 1,096 | +41,4% |
| 2026 (parcial) | 1,652 | 1,225 | +34,9% |
| **Global** | 1,524 | 1,182 | **+28,9%** |

Se mueve entre +9,6% y +41,4% de una temporada a otra -- **la variancia año a año es en sí misma
el hallazgo**, no ruido a ignorar. `_factor_localia()` no tiene este número escrito a mano en
ningún lado: lo recalcula de `Partido.resultado` real cada vez que se llama, así que ya refleja
las cinco temporadas automáticamente. Sí tenía un bug real hasta hace poco -- `_historial_finalizados()`
cortaba en los 1000 partidos finalizados más recientes sin avisar (contradecía su propio
docstring, que decía "se usa todo el historial disponible"), lo que iba a sesgar este número hacia
las temporadas más nuevas a medida que la liga acumulara más historial. Ya se sacó el tope (ver
`ml_models/pipelines/team_ratings.py`, con test de regresión en `test_team_ratings.py`).

El modelo aplica esto como un factor de ajuste global (`_factor_localia()`) sobre la proyección de
ataque según si el equipo juega de local o de visita -- no se separan los ratings de ataque/defensa
por localía por equipo individual porque, con el volumen de datos actual, eso dejaría muestras
demasiado chicas por equipo para ser confiables. Detalle completo de esta medición, y otras
correlaciones crudas todavía sin validar (distancia de viaje, altura, descanso), en
`HANDOFF_dataset_contexto.md`.

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
    │       ├── PERDIDA  (PNL = -stake)
    │       └── ANULADA  (push -- se devuelve el stake, PNL = 0)
    │
    └── DESCARTADA (la persona decide no tomarla)
```

Estas transiciones se pueden hacer desde botones directos en el dashboard (pestaña
Recomendaciones) o desde `/admin/db_models/operacion/` (acciones en lote). La lógica de cálculo de
PNL vive una sola vez, como métodos del modelo `Operacion` (`aceptar()`, `descartar()`,
`marcar_ganada()`, `marcar_perdida()`, `marcar_anulada()`), reutilizada tanto por el admin como por
la API. **ANULADA** (push) es siempre una decisión manual de la persona -- por ejemplo, un partido
suspendido después de aceptar la recomendación, o un mercado que la casa/exchange anula -- nunca
algo que el sistema infiera solo; en los mercados 1X2 y Over/Under que soporta hoy, un empate en
1X2 se resuelve como **PERDIDA** para las selecciones LOCAL/VISITANTE (nunca como push).

`operaciones/resumen/` (usado por el dashboard para el PNL agregado) suma el campo `pnl` de todas
las operaciones automáticamente, así que un cambio de estado se refleja ahí sin lógica adicional;
el *win rate* solo considera GANADA/PERDIDA (una ANULADA no cuenta ni como acierto ni como error).

El escáner (`trading_engine/scanner.py`) evalúa el mercado 1X2 y el de goles totales
(Over/Under, líneas 1.5 a 3.5 — ver `data_ingestion/tasks.py:LINEAS_OVER_UNDER_VALIDAS`), pero
**nunca genera más de una recomendación por "familia" de mercado por partido** (una para 1X2, una
para Over/Under): todas las líneas de Over/Under de un mismo partido están altamente
correlacionadas entre sí (son la misma apuesta a "muchos/pocos goles" repetida). Para 1X2 se queda
con la de mayor EV (LOCAL/EMPATE/VISITANTE son alternativas mutuamente excluyentes reales). **Para
Over/Under se queda con la línea más cercana a su propia proyección de goles, no con la de mayor
EV** -- se detectó en la práctica que cuando el modelo proyecta más goles que el mercado, el EV
aparente crece línea tras línea hacia la más extrema (más cuota), así que "mayor EV" terminaba
recomendando siempre la línea más extrema disponible (la más sensible a la cola de la
distribución, la menos confiable), descartando líneas más centrales que también tenían edge real.
Ver `_distancia_a_proyeccion` en `scanner.py`.

**La línea 4.5 se sacó por completo** (antes era válida) tras verificar en la práctica que
`proyectar_xg()` puede llegar a un total combinado alto multiplicando dos DEFENSAS flojas entre sí
sin que ninguno de los dos equipos tenga un ataque realmente destacado (ej. Limache 1.76 de ataque
vs Cobresal 1.41, promedio de liga 1.44, proyectaron 4.13 goles combinados) -- requerir 5+ goles ya
es un evento de cola incluso para el promedio real de la liga (2.7 goles/partido), y las 5
recomendaciones de Over/Under que generó el sistema en su historia fueron las 5 en esa línea,
las 5 perdedoras. El escáner además ignora cualquier cuota de 4.5 que ya estuviera capturada en
`HistorialCuotas` de antes de este cambio.

## 6. Gestión de Riesgo (Kelly Fraccional)

`trading_engine/risk_manager.py` implementa Kelly fraccional (`KELLY_FRACTION`, default 25% del
Kelly completo) sobre un **bankroll de referencia** (en pesos chilenos, para que el stake sugerido
tenga sentido con la plata real disponible en la casa/exchange que se use). Hay además un tope duro
(`MAX_STAKE_PER_BET`) y un edge mínimo para considerar algo "recomendable" (`MIN_EDGE_THRESHOLD`,
default 5%). Estos cuatro valores viven en `ConfiguracionRiesgo` (fila única en la base, sembrada
la primera vez con los defaults de `backend/.env`) y se editan desde el dashboard, pestaña
**Configuración** — `.env` deja de tener efecto una vez creada esa fila.

**Alerta de edge extremo**: un edge mucho más alto de lo razonable (`EDGE_MAXIMO_CONFIABLE`, 35%)
nunca se acepta como una gran oportunidad -- estadísticamente es más probable que sea un error
(cuota estancada, o el modelo sobreestimando la probabilidad, típicamente en la cola de la
distribución de Poisson) que una ventaja real. `evaluar_apuesta()` marca `edge_extremo=True` y
fuerza `es_apuesta_de_valor=False` en ese caso; el escáner lo registra como NO BET con un motivo
explícito en vez de recomendarlo. Ver sección 10 para la evidencia real detrás de este número.

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
- **LanusStats (https://github.com/federicorabanos/LanusStats, MIT) se integró, pero NO para xG.**
  Se verificó en vivo (no solo la documentación) que ni FBref ni FotMob calculan un modelo de xG
  para la Primera División de Chile: FBref solo expone conteo de tiros en esta liga, y el catálogo
  real de estadísticas de FotMob para esta liga (`leagueseasondeepstats`) no incluye
  `expected_goals_team` pese a que la librería lo ofrezca como parámetro válido en general. Lo que
  sí se usa: posesión/grandes ocasiones/tiros al arco/corners de FotMob, guardados en
  `Equipo.metadata["fotmob"]` (ver `ml_models/pipelines/fotmob_stats.py`) y mostrados en la pestaña
  Equipos como contexto informativo — **deliberadamente sin mezclarlos en `calcular_ratings()` /
  `proyectar_xg()`**, porque son promedios de temporada sin calibrar contra resultados reales de
  esta liga (a diferencia del resto del modelo, que sí pasó por el proceso de auditoría/calibración
  de la sección 10 antes de influir en una recomendación). Requiere el paquete opcional
  `lanusstats` (`requirements-scraping.txt`, no en `requirements.txt`) porque lanza un Chrome real
  (`nodriver`) para esquivar el anti-bot de FotMob — por eso se corre a mano con
  `manage.py actualizar_stats_fotmob`, nunca desde la tarea automática por hora.
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

## 10. Auditoría y Calibración del Modelo (Distribución de Poisson)

Tres scripts en `ml_models/management/commands/` para auditar el modelo actual con datos reales,
sin reemplazarlo por algo más complejo:

- **`manage.py auditar_predicciones [--partido-id N]`**: para cada partido programado, imprime los
  números crudos detrás de la proyección (rating ataque/defensa de cada equipo, factor de localía,
  xG local/visitante/total) y la distribución de Poisson resultante agrupada en 0/1/2/3/4/5+ goles
  -- para detectar a simple vista un xG total poco creíble antes de que se convierta en una
  recomendación. Marca con `<-- alto para el promedio de la liga` cualquier xG total > 4.0 (el
  promedio real de la liga es 2.7 goles/partido).
- **`manage.py calibrar_modelo`**: Brier score, Log Loss y tabla de calibración (probabilidad
  predicha vs. frecuencia real, en buckets de 20 puntos) por mercado (`1X2`,
  `OVER_UNDER_1.5/2.5/3.5/4.5`), usando `AnalisisPartido` ya resuelto. La línea 4.5 se audita a
  propósito aunque ya no se recomiende (ver sección 6 y `LINEAS_OVER_UNDER_VALIDAS`). Con menos de
  20 casos resueltos por mercado, reporta "datos insuficientes" en vez de inventar un número (hoy
  es el caso para casi todos los mercados -- muy pocos análisis tienen resultado real todavía).
- **`manage.py backtest_modelo [--guardar-calibracion]`**: walk-forward sobre TODO el historial
  (~1130 partidos evaluables), calculando el rating de cada equipo únicamente con partidos
  anteriores a la fecha de cada partido evaluado (`hasta_fecha` en `team_ratings.py`) -- sin data
  leakage. Compara accuracy/Brier/log loss del modelo contra un baseline honesto (el prior neutro
  45/27/28% que describe la sección 3.4, el mismo que este proyecto dejó de usar) y calcula ROI
  simulado solo sobre partidos con cuota real capturada de antes (hoy, con 1 sola cuota histórica
  disponible, ese número no significa nada todavía -- se necesitan más semanas de escaneo en vivo).
  Con `--guardar-calibracion`, además persiste la curva de calibración medida (`CalibracionMercado`,
  ver más abajo) para las líneas de Over/Under vigentes.

### Probabilidades calibradas (cierra el pipeline: Poisson → calibración → edge/EV)

`ml_models.pipelines.calibracion.construir_curva_calibracion` convierte los buckets del backtest
(con muestra mínima por punto, `MIN_N_POR_PUNTO_CALIBRACION=10`) en una curva (probabilidad
predicha → frecuencia real) por mercado, guardada en el modelo `CalibracionMercado`.
`MatchPredictor.predecir_probabilidad_over()` la usa para corregir la probabilidad cruda del
Poisson por interpolación lineal (extrapolando con el último tramo fuera del rango medido) **antes**
de que el escáner calcule edge/EV -- si no hay curva guardada para un mercado, se usa la
probabilidad cruda sin tocar (nunca se inventa una corrección sin evidencia real detrás).

Efecto real verificado (2026-09): para Deportes Limache vs Cobresal, "Más de 3.5 goles" tenía una
probabilidad cruda de 59.2% (EV +33.2% con cuota real 2.25) -- después de aplicar la curva medida
contra ~1071 partidos reales, la probabilidad corregida bajó a 36.3% (EV -18.2%), y la
recomendación pasó de VALUE BET a NO BET. La recomendación vieja (ya generada con el número sin
calibrar) se descartó a mano con una nota explicando por qué.

**Esto hay que volver a correr** (`manage.py backtest_modelo --guardar-calibracion`) cada tanto a
medida que se acumule más historial real -- la curva actual es de ~1071 partidos y 3 puntos por
línea; con más partidos jugados, va a poder afinarse más.

**Resultado del primer backtest completo** (2026-09, 1071 partidos evaluables de ~1130 con
historial suficiente):

- **Accuracy**: modelo 47.9% vs. baseline 45.2% -- el modelo le gana al baseline, pero por poco.
- **Brier/Log loss**: modelo 0.2139/0.6194 vs. baseline 0.2150/0.6204 -- prácticamente empatados.
- **Calibración del favorito (1X2)**: bien calibrado en el rango 40-60% (predicho 48.5%, real
  47.7%), pero **sobreconfiado en el rango 60-80%** (predicho 66.6%, real solo 50.0%, con 152
  casos -- muestra grande, no ruido). Cuando el modelo dice "60-80% de confianza", en la práctica
  acierta como si fuera una moneda.
- **Over/Under 4.5 tenía el Brier score más bajo de las 4 líneas (0.1211)** -- pero eso es
  engañoso: "más de 4.5" es un evento poco frecuente (promedio de liga 2.7 goles/partido), así que
  un Brier bajo ahí puede ser solo la base rate, no buena calibración real. Es la confirmación con
  datos de por qué se sacó esa línea (ver sección 6).
- **Over/Under 3.5 mostró la miscalibración más clara con muestra grande**: en el rango 0-20% de
  probabilidad predicha (n=126), la frecuencia real de "más de 3.5" fue 31.7%, casi el doble de lo
  predicho (16.3%) -- el modelo subestima este mercado específicamente cuando dice que es poco
  probable.

Conclusión práctica: el modelo de Poisson le gana al azar, pero por un margen chico, y tiene una
zona de sobreconfianza real y medible (60-80% de probabilidad predicha en 1X2). Esto es evidencia
a favor de mantener `EDGE_MAXIMO_CONFIABLE` con margen conservador y de no confiar ciegamente en
ninguna probabilidad por sí sola sin mirar también el edge, el data quality y el confidence score
juntos (sección 4 y `ml_models/pipelines/quality.py`) -- exactamente el diseño que ya existía,
ahora con evidencia cuantitativa detrás.
