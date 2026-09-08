import { useEffect, useState } from "react";

import Card from "./Card";
import { getBacktest } from "../services/api";
import { formatMercado, formatPercent } from "../utils/format";

const LINEAS_VIGENTES = new Set(["1X2", "OVER_UNDER_1.5", "OVER_UNDER_2.5", "OVER_UNDER_3.5"]);

export default function RendimientoBacktest() {
  const [datos, setDatos] = useState(null);

  useEffect(() => {
    getBacktest().then(setDatos).catch(() => setDatos(null));
  }, []);

  if (!datos) return null;

  if (!datos.datos_disponibles) {
    return (
      <Card title="Backtest histórico (Accuracy, Brier, Log Loss, Calibración)">
        <p className="page-status">{datos.motivo}</p>
      </Card>
    );
  }

  return (
    <Card title="Backtest histórico (Accuracy, Brier, Log Loss, Calibración)">
      <p className="config-hint">
        Walk-forward sobre partidos ya jugados: para cada uno, el rating de cada equipo se
        calcula sólo con partidos anteriores a esa fecha (sin usar información del futuro). Con
        muchos más casos que las recomendaciones en vivo, es la evidencia más sólida que hay hoy
        de qué tan bien calibrado está el modelo.
      </p>
      <div className="rendimiento-table rendimiento-table--backtest">
        <div className="rendimiento-table__row rendimiento-table__row--header">
          <span>Mercado</span>
          <span>Muestra</span>
          <span>Accuracy</span>
          <span>Brier</span>
          <span>Log Loss</span>
        </div>
        {datos.mercados.map((m) => (
          <div className="rendimiento-table__row" key={m.mercado}>
            <span>
              {formatMercado(m.mercado)}
              {!LINEAS_VIGENTES.has(m.mercado) && (
                <>
                  {" "}
                  <span className="config-hint">(diagnóstico, no se recomienda en vivo)</span>
                </>
              )}
            </span>
            <span>{m.n}</span>
            <span>
              {m.accuracy != null ? formatPercent(m.accuracy) : "-"}
              {m.accuracy_baseline != null && (
                <span className="config-hint"> (baseline {formatPercent(m.accuracy_baseline)})</span>
              )}
            </span>
            <span>
              {m.brier_score}
              {m.brier_score_baseline != null && (
                <span className="config-hint"> (baseline {m.brier_score_baseline})</span>
              )}
            </span>
            <span>
              {m.log_loss}
              {m.log_loss_baseline != null && (
                <span className="config-hint"> (baseline {m.log_loss_baseline})</span>
              )}
            </span>
          </div>
        ))}
      </div>
      <p className="config-hint">
        Calibración: en cada mercado, la probabilidad promedio que dijo el modelo debería
        parecerse a la frecuencia real con la que ocurrió. Ver &ldquo;Ver análisis&rdquo; de una
        recomendación puntual, o correr <code>manage.py backtest_modelo</code> para el detalle
        bucket por bucket.
      </p>
      <p className="config-hint">
        Actualizado el {new Date(datos.actualizado_en).toLocaleString("es-CL")}.
      </p>
    </Card>
  );
}
