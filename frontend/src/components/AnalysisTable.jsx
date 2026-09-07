import { useState } from "react";

import AnalisisDetalle from "./AnalisisDetalle";
import Modal from "./Modal";
import { formatDateTime, formatMercado, formatPercent, formatSeleccion, nivelConfianza } from "../utils/format";
import "./AnalysisTable.css";

function ScorePill({ label, valor }) {
  const tono = valor >= 70 ? "good" : valor >= 40 ? "warning" : "critical";
  return (
    <span className={`score-pill score-pill--${tono}`} title={label}>
      {label} {valor}
    </span>
  );
}

function ConfianzaPill({ valor }) {
  const nivel = nivelConfianza(valor);
  return (
    <span className="score-pill score-pill--confianza" title={`Confianza: ${nivel.label} (${valor}/100)`}>
      {nivel.emoji} Confianza {valor}
    </span>
  );
}

export default function AnalysisTable({ analisis }) {
  const [seleccionado, setSeleccionado] = useState(null);

  if (!analisis.length) {
    return <p className="operations-table__empty">No hay análisis registrados todavía.</p>;
  }

  return (
    <div className="operations-table__scroll">
      <table className="operations-table">
        <thead>
          <tr>
            <th>Partido</th>
            <th>Mercado analizado</th>
            <th>Edge</th>
            <th>EV</th>
            <th>Scores</th>
            <th>Resultado</th>
            <th>Fecha</th>
          </tr>
        </thead>
        <tbody>
          {analisis.map((a) => (
            <tr
              key={a.id}
              className="analysis-table__fila"
              onClick={() => setSeleccionado(a)}
              title="Ver por qué (o por qué no) esta apuesta"
            >
              <td>
                {a.partido?.equipo_local?.nombre} vs {a.partido?.equipo_visitante?.nombre}
              </td>
              <td>
                <div className="operations-table__apuesta">
                  <span>
                    {a.mercado === "GENERAL"
                      ? "Sin datos para analizar"
                      : formatSeleccion(a.mercado, a.seleccion_evaluada)}
                  </span>
                  {a.mercado !== "GENERAL" && (
                    <span className="operations-table__mercado">{formatMercado(a.mercado)}</span>
                  )}
                </div>
              </td>
              <td>{a.edge != null ? formatPercent(a.edge) : "-"}</td>
              <td className={a.ev >= 0 ? "is-positive" : "is-negative"}>
                {a.ev != null ? formatPercent(a.ev) : "-"}
              </td>
              <td>
                <div className="analysis-table__scores">
                  <ScorePill label="Calidad" valor={a.data_quality_score} />
                  <ConfianzaPill valor={a.confidence_score} />
                  <ScorePill label="Valor" valor={a.value_score} />
                </div>
              </td>
              <td>
                {a.recomendacion === "VALUE_BET" && (
                  <span className="analysis-table__badge analysis-table__badge--value">
                    🟢 VALUE BET
                  </span>
                )}
                {a.recomendacion === "ANOMALIA" && (
                  <span className="analysis-table__badge analysis-table__badge--anomalia" title={a.motivo_no_bet}>
                    ⚠️ ANOMALÍA
                  </span>
                )}
                {a.recomendacion === "NO_BET" && (
                  <span className="analysis-table__badge analysis-table__badge--no-bet" title={a.motivo_no_bet}>
                    ⚪ NO BET
                  </span>
                )}
              </td>
              <td>{formatDateTime(a.fecha_analisis)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {seleccionado && (
        <Modal
          title={`¿Por qué esta apuesta? -- ${seleccionado.partido?.equipo_local?.nombre} vs ${seleccionado.partido?.equipo_visitante?.nombre}`}
          onClose={() => setSeleccionado(null)}
        >
          <AnalisisDetalle analisis={seleccionado} />
        </Modal>
      )}
    </div>
  );
}
