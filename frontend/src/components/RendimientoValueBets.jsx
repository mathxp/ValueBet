import { useEffect, useState } from "react";

import Card from "./Card";
import { getRendimientoValueBets } from "../services/api";
import { formatCurrency, formatPercent } from "../utils/format";

export default function RendimientoValueBets() {
  const [datos, setDatos] = useState(null);

  useEffect(() => {
    getRendimientoValueBets().then(setDatos).catch(() => setDatos(null));
  }, []);

  if (!datos) return null;

  return (
    <Card title="Rendimiento de las value bets (todas, no solo las que aceptaste)">
      <p className="config-hint" style={{ margin: "0 0 12px" }}>
        {datos.total_value_bets} value bet(s) generadas en total · edge promedio{" "}
        {datos.edge_promedio != null ? formatPercent(datos.edge_promedio) : "-"} · EV promedio{" "}
        {datos.ev_promedio != null ? formatPercent(datos.ev_promedio) : "-"}
      </p>

      {!datos.datos_suficientes ? (
        <p className="page-status">
          {datos.motivo} ({datos.resueltas} de {datos.minimo_requerido} value bets resueltas
          necesarias). Esto se completa solo con el tiempo, a medida que se juegan y resuelven más
          partidos.
        </p>
      ) : (
        <div className="rendimiento-table">
          <div className="rendimiento-table__row rendimiento-table__row--header">
            <span>Win rate</span>
            <span>ROI teórico</span>
            <span>Stake teórico total</span>
          </div>
          <div className="rendimiento-table__row">
            <span>{formatPercent(datos.win_rate)}</span>
            <span className={datos.roi_teorico >= 0 ? "is-positive" : "is-negative"}>
              {datos.roi_teorico != null ? formatPercent(datos.roi_teorico) : "-"}
            </span>
            <span>{formatCurrency(datos.stake_teorico_total)}</span>
          </div>
        </div>
      )}
      <p className="config-hint">
        Teórico = si se hubieran aceptado <strong>todas</strong> las value bets al stake sugerido,
        no solo las que aceptaste de verdad (eso es <strong>Rendimiento del usuario</strong>, más
        arriba).
      </p>
    </Card>
  );
}
