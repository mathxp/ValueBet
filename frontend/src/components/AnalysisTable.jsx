import { formatDateTime, formatMercado, formatPercent, formatSeleccion } from "../utils/format";
import "./AnalysisTable.css";

function ScorePill({ label, valor }) {
  const tono = valor >= 70 ? "good" : valor >= 40 ? "warning" : "critical";
  return (
    <span className={`score-pill score-pill--${tono}`} title={label}>
      {label} {valor}
    </span>
  );
}

export default function AnalysisTable({ analisis }) {
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
            <tr key={a.id}>
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
                  <ScorePill label="Confianza" valor={a.confidence_score} />
                  <ScorePill label="Valor" valor={a.value_score} />
                </div>
              </td>
              <td>
                {a.recomendacion === "VALUE_BET" ? (
                  <span className="analysis-table__badge analysis-table__badge--value">
                    🟢 VALUE BET
                  </span>
                ) : (
                  <span className="analysis-table__badge analysis-table__badge--no-bet" title={a.motivo_no_bet}>
                    🔴 NO BET
                  </span>
                )}
              </td>
              <td>{formatDateTime(a.fecha_analisis)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
