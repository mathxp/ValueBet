import { useEffect, useState } from "react";

import Card from "./Card";
import { getRendimientoModelo } from "../services/api";
import { formatCurrency, formatPercent } from "../utils/format";

export default function RendimientoModelo() {
  const [datos, setDatos] = useState(null);

  useEffect(() => {
    getRendimientoModelo().then(setDatos).catch(() => setDatos(null));
  }, []);

  if (!datos) return null;

  if (!datos.datos_suficientes) {
    return (
      <Card title="Rendimiento del modelo">
        <p className="page-status">
          {datos.motivo} ({datos.predicciones_resueltas} de {datos.minimo_requerido} análisis
          resueltos necesarios). Esto se completa solo con el tiempo, a medida que se juegan y
          resuelven más partidos.
        </p>
      </Card>
    );
  }

  return (
    <Card title="Rendimiento del modelo (vs. confiar directamente en la cuota de mercado)">
      <div className="rendimiento-table">
        <div className="rendimiento-table__row rendimiento-table__row--header">
          <span></span>
          <span>Modelo</span>
          <span>Baseline (mercado)</span>
        </div>
        <div className="rendimiento-table__row">
          <span>Accuracy</span>
          <span>{formatPercent(datos.modelo.accuracy)}</span>
          <span>{formatPercent(datos.baseline_mercado.accuracy)}</span>
        </div>
        <div className="rendimiento-table__row">
          <span>Brier score (más bajo = mejor)</span>
          <span>{datos.modelo.brier_score}</span>
          <span>{datos.baseline_mercado.brier_score}</span>
        </div>
      </div>
      {datos.roi_value_bets != null && (
        <p className="config-hint">
          ROI teórico de las recomendaciones (si se hubieran aceptado todas al stake sugerido):{" "}
          <strong>{formatPercent(datos.roi_value_bets)}</strong> sobre{" "}
          {formatCurrency(datos.stake_total_teorico)} apostados en total.
        </p>
      )}
      <p className="config-hint">Basado en {datos.predicciones_resueltas} análisis ya resueltos.</p>
    </Card>
  );
}
