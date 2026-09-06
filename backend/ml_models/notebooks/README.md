# Notebooks de entrenamiento

Coloca aquí los notebooks de experimentación y entrenamiento (ej. `01_exploracion.ipynb`,
`02_entrenamiento_xgboost.ipynb`).

Flujo recomendado para evitar overfitting (ver sección 2.2 de `prompt.md`):

1. Extraer histórico de `Partido` + `HistorialCuotas` vía el ORM de Django o `psql`.
2. Construir features con `ml_models.pipelines.features.build_features` — la misma
   función que usa `predictor.py` en producción, para que no haya *train/serving skew*.
3. Split temporal (no aleatorio): entrenar con temporadas pasadas, validar con la más
   reciente. Un split aleatorio filtra información del futuro al pasado.
4. Comparar contra el baseline de Poisson (`predictor.py`) — si XGBoost no le gana
   de forma consistente en el set de validación, no vale la pena el riesgo de overfitting.
5. Guardar el modelo final con `joblib.dump(modelo, "../weights/model.joblib")`.
