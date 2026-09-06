# PROMPT DE ACTUALIZACIÓN — MEJORAS PRIORITARIAS

## Instrucción principal

Utiliza el `prompt.md` actual del proyecto como fuente principal.

**NO reemplaces ni reconstruyas el proyecto completo.**

**NO elimines funcionalidades existentes que ya funcionan.**

**NO cambies la arquitectura actual sin necesidad.**

El objetivo de esta actualización es implementar únicamente las mejoras indicadas a continuación, manteniendo el modelo y funcionalidades actuales que ya están operativas.

---

# 1. Implementar historial de predicciones

Actualmente el sistema genera predicciones, pero necesitamos poder evaluar posteriormente si esas predicciones fueron correctas.

Agregar un sistema de **registro histórico de predicciones**.

Cada predicción debe almacenarse antes de conocer el resultado real del partido.

Debe guardar, como mínimo:

- Partido.
- Fecha.
- Equipo local.
- Equipo visitante.
- Goles esperados proyectados.
- Probabilidad de Local.
- Probabilidad de Empate.
- Probabilidad de Visitante.
- Mercado analizado.
- Cuota utilizada.
- Cuota justa.
- Edge.
- EV.
- Confidence Score.
- Data Quality Score.
- Value Score.
- Recomendación.
- Stake sugerido.
- Fecha/hora del análisis.
- Modelo utilizado.

Una vez finalizado el partido, debe poder registrarse:

- Resultado real.
- Resultado de la predicción.
- Resultado de la recomendación.

El objetivo es poder responder:

> "¿Qué tan bueno ha sido realmente nuestro modelo?"

---

# 2. Implementar Data Quality Score y NO BET

El sistema debe evaluar la calidad de los datos utilizados para cada análisis.

Crear un:

```text
Data Quality Score: 0 - 100
```

Debe considerar principalmente:

- Cantidad de partidos disponibles.
- Antigüedad de los datos.
- Datos faltantes.
- Completitud.
- Consistencia.
- Calidad de la fuente.

Ejemplo:

```text
Data Quality: 94/100
Estado: ALTA
```

o:

```text
Data Quality: 43/100
Estado: BAJA
```

## Regla NO BET

Agregar `NO BET` como resultado válido del sistema.

El sistema **NO debe sentirse obligado a recomendar una apuesta**.

Debe devolver `NO BET` cuando:

- Existan datos insuficientes.
- La calidad de datos sea demasiado baja.
- El Edge no alcance el mínimo configurado.
- El EV sea negativo.
- La confianza sea demasiado baja.
- Exista demasiada incertidumbre.

Ejemplo:

```text
NO BET

Motivo:
Datos insuficientes.
```

o:

```text
NO BET

Motivo:
Edge inferior al umbral mínimo.
```

Esta funcionalidad es prioritaria.

---

# 3. Fortalecer el análisis de valor: Edge + EV

Mantener el modelo predictivo actual.

No reemplazar el modelo Poisson + ratings + shrinkage solamente por esta actualización.

Agregar/asegurar el flujo:

```text
Probabilidad del modelo
        ↓
Cuota del mercado
        ↓
Cuota justa
        ↓
Probabilidad implícita
        ↓
Edge
        ↓
EV
```

El sistema debe diferenciar claramente:

### Probabilidad

¿Qué tan probable considera el modelo que ocurra el resultado?

### Edge

¿Cuánto difiere nuestra estimación respecto al mercado?

### EV

¿La cuota disponible representa valor según nuestra probabilidad?

No considerar una apuesta como `VALUE BET` solamente porque sea el resultado más probable.

---

# 4. Implementar Confidence Score

Crear un:

```text
Confidence Score: 0 - 100
```

Este indicador debe representar **qué tan confiable es el análisis**, no la probabilidad de ganar.

Debe considerar factores como:

- Calidad de los datos.
- Cantidad de partidos.
- Estabilidad de los ratings.
- Disponibilidad de información.
- Consistencia del modelo.
- Incertidumbre.

Ejemplo:

```text
Confidence: 86/100
```

El sistema debe poder diferenciar:

```text
Edge alto
+
Confidence alta
=
Oportunidad fuerte
```

de:

```text
Edge alto
+
Confidence baja
=
Oportunidad riesgosa / posible NO BET
```

---

# 5. Implementar historial de cuotas y CLV

Cuando la fuente de datos lo permita, almacenar:

- Cuota inicial.
- Cuota actual.
- Cuota al momento del análisis.
- Cuota de cierre.
- Fecha/hora.
- Movimiento de cuota.

Agregar posteriormente el cálculo de:

```text
CLV
```

El objetivo es poder analizar si el sistema está detectando precios favorables antes de que el mercado se mueva.

Ejemplo:

```text
Cuota al analizar: 2.50
Cuota de cierre:   2.15

CLV: positivo
```

El CLV debe utilizarse como **métrica de evaluación del sistema**, no como garantía de ganancia.

---

# 6. Comparar el modelo contra un baseline

Agregar una comparación entre el modelo actual y una referencia simple.

El objetivo es determinar si nuestro modelo realmente aporta valor.

El sistema debe poder mostrar posteriormente algo similar a:

```text
                    MODELO     BASELINE

Accuracy             57.8%       54.2%
Brier Score          0.181       0.194
Log Loss              0.91        0.98
ROI                    +7.2%       +2.1%
CLV                    +4.6%       +1.3%
```

No inventar valores.

Estas métricas deben calcularse únicamente a partir de resultados históricos reales registrados por el sistema.

---

# 7. Orden correcto de decisión

La lógica del sistema debe quedar conceptualmente así:

```text
DATOS
  ↓
CALIDAD DE DATOS
  ↓
MODELO
  ↓
PROBABILIDADES
  ↓
CUOTAS
  ↓
EDGE
  ↓
EV
  ↓
CONFIDENCE
  ↓
VALUE SCORE
  ↓
VALUE BET / NO BET
  ↓
KELLY
```

### Importante sobre Kelly

Kelly **NO debe decidir si existe valor**.

Kelly solamente debe utilizarse después de determinar que existe una oportunidad válida, como herramienta de referencia para calcular el stake.

Mantener el esquema actual de:

```text
Fractional Kelly = 25%
```

y mantener:

```text
MAX_STAKE_PER_BET
```

como límite de seguridad.

---

# 8. Resultado esperado en el Dashboard

La información principal de una oportunidad debería terminar viéndose aproximadamente así:

```text
┌──────────────────────────────────────────────┐
│        COLO-COLO vs EVERTON                  │
├──────────────────────────────────────────────┤
│                                              │
│ PROBABILIDAD DEL MODELO                      │
│ Local:       52%                             │
│ Empate:      27%                             │
│ Visitante:   21%                             │
│                                              │
│ CUOTA MERCADO:       2.40                    │
│ CUOTA JUSTA:         2.08                    │
│ EDGE:                +15.4%                  │
│ EV:                  +15.2%                  │
│                                              │
│ DATA QUALITY:        94/100                  │
│ CONFIDENCE:          86/100                  │
│ VALUE SCORE:         87/100                  │
│                                              │
│ 🟢 VALUE BET                                 │
│                                              │
│ Kelly 1/4:           2.8%                    │
└──────────────────────────────────────────────┘
```

Cuando no exista suficiente evidencia:

```text
┌──────────────────────────────────────────────┐
│        PARTIDO ANALIZADO                     │
├──────────────────────────────────────────────┤
│                                              │
│ DATA QUALITY:        42/100                  │
│ CONFIDENCE:          35/100                  │
│ EDGE:                +4.1%                   │
│                                              │
│ 🔴 NO BET                                    │
│                                              │
│ Motivo:                                      │
│ Datos insuficientes y Edge inferior          │
│ al umbral configurado.                       │
└──────────────────────────────────────────────┘
```

---

# 9. Prioridad de implementación

Implementar las mejoras en este orden:

### PRIORIDAD 1 — Fundamental

1. Historial de predicciones.
2. Data Quality Score.
3. NO BET.
4. Edge + EV correctamente integrados.

### PRIORIDAD 2 — Evaluación

5. Confidence Score.
6. Historial de cuotas.
7. CLV.
8. Comparación contra baseline.

### PRIORIDAD 3 — Presentación

9. Mostrar toda esta información claramente en el Dashboard.

---

# 10. Restricciones

Durante esta actualización:

- No implementar apuestas automáticas.
- No implementar ejecución de órdenes.
- No administrar fondos reales.
- No agregar complejidad innecesaria.
- No reemplazar el modelo actual sin evidencia.
- No incorporar XGBoost, Deep Learning u otros modelos solamente por agregar tecnología.
- No inventar datos.
- No inventar métricas históricas.
- No presentar predicciones como certezas.
- No eliminar funcionalidades actuales que ya funcionan.
- No modificar componentes que no sean necesarios para estas mejoras.

---

# 11. Criterio final

La actualización será considerada correcta cuando el sistema pueda hacer lo siguiente:

```text
Analizar partido
      ↓
Generar probabilidades
      ↓
Evaluar calidad de datos
      ↓
Comparar contra cuotas
      ↓
Calcular Edge
      ↓
Calcular EV
      ↓
Determinar Confidence
      ↓
Determinar Value
      ↓
VALUE BET o NO BET
      ↓
Calcular Kelly como referencia
      ↓
Guardar predicción
      ↓
Esperar resultado real
      ↓
Evaluar posteriormente el modelo
```

El objetivo final es convertir el sistema en una herramienta que **no solamente entregue recomendaciones**, sino que pueda demostrar mediante datos históricos **qué tan buenas son sus propias predicciones y qué tan consistentemente identifica valor**.