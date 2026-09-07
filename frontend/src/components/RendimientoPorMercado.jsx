import { useEffect, useState } from "react";

import Card from "./Card";
import { getRendimientoPorMercado } from "../services/api";
import { formatMercado, formatPercent } from "../utils/format";

export default function RendimientoPorMercado() {
  const [filas, setFilas] = useState(null);

  useEffect(() => {
    getRendimientoPorMercado()
      .then(setFilas)
      .catch(() => setFilas(null));
  }, []);

  if (!filas || filas.length === 0) return null;

  return (
    <Card title="Rendimiento por mercado (nunca se mezclan entre sí)">
      <div className="rendimiento-table">
        <div className="rendimiento-table__row rendimiento-table__row--header">
          <span>Mercado</span>
          <span>Accuracy</span>
          <span>Brier / ROI teórico</span>
        </div>
        {filas.map((fila) => (
          <div className="rendimiento-table__row" key={fila.mercado}>
            <span>{fila.mercado === "1X2" ? "Resultado (1X2)" : formatMercado(fila.mercado)}</span>
            {fila.datos_suficientes ? (
              <>
                <span>{formatPercent(fila.accuracy)}</span>
                <span>
                  {fila.brier_score}
                  {fila.roi_teorico != null && (
                    <>
                      {" "}
                      / <span className={fila.roi_teorico >= 0 ? "is-positive" : "is-negative"}>
                        {formatPercent(fila.roi_teorico)}
                      </span>
                    </>
                  )}
                </span>
              </>
            ) : (
              <span className="page-status" style={{ gridColumn: "span 2" }}>
                {fila.predicciones_resueltas}/{fila.minimo_requerido} casos -- insuficiente todavía
              </span>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
