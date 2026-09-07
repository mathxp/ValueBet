import { useState } from "react";

import StatusBadge from "./StatusBadge";
import {
  aceptarOperacion,
  descartarOperacion,
  marcarOperacionAnulada,
  marcarOperacionGanada,
  marcarOperacionPerdida,
} from "../services/api";
import {
  formatCurrency,
  formatDateTime,
  formatMercado,
  formatOdds,
  formatPercent,
  formatSeleccion,
} from "../utils/format";
import "./OperationsTable.css";

function AccionesOperacion({ operacion, onCambiar }) {
  const [enviando, setEnviando] = useState(false);

  const ejecutar = async (accion) => {
    setEnviando(true);
    try {
      const actualizada = await accion(operacion.id);
      onCambiar(actualizada);
    } catch {
      // El estado puede haber cambiado en otra pestaña/el admin; refrescar la lista lo resuelve.
      alert("No se pudo aplicar la acción. Puede que ya se haya actualizado desde otro lado.");
    } finally {
      setEnviando(false);
    }
  };

  if (operacion.estado === "RECOMMENDED") {
    return (
      <div className="operations-table__acciones">
        <button
          className="operations-table__accion--primary"
          disabled={enviando}
          onClick={() => ejecutar(aceptarOperacion)}
        >
          Aceptar
        </button>
        <button disabled={enviando} onClick={() => ejecutar(descartarOperacion)}>
          Descartar
        </button>
      </div>
    );
  }

  if (operacion.estado === "ACCEPTED") {
    return (
      <div className="operations-table__acciones">
        <button
          className="operations-table__accion--good"
          disabled={enviando}
          onClick={() => ejecutar(marcarOperacionGanada)}
        >
          Ganó
        </button>
        <button
          className="operations-table__accion--danger"
          disabled={enviando}
          onClick={() => ejecutar(marcarOperacionPerdida)}
        >
          Perdió
        </button>
        <button disabled={enviando} onClick={() => ejecutar(marcarOperacionAnulada)}>
          Anulada
        </button>
      </div>
    );
  }

  return <span className="page-status">—</span>;
}

export default function OperationsTable({ operaciones, onCambiarOperacion }) {
  if (!operaciones.length) {
    return <p className="operations-table__empty">No hay recomendaciones para mostrar.</p>;
  }

  return (
    <div className="operations-table__scroll">
      <table className="operations-table">
        <thead>
          <tr>
            <th>Partido</th>
            <th>Apuesta</th>
            <th>Cuota</th>
            <th>Edge</th>
            <th>EV</th>
            <th>Stake sugerido</th>
            <th>PNL</th>
            <th>Estado</th>
            <th>Fecha</th>
            {onCambiarOperacion && <th>Acciones</th>}
          </tr>
        </thead>
        <tbody>
          {operaciones.map((op) => (
            <tr key={op.id}>
              <td>
                {op.partido?.equipo_local?.nombre} vs {op.partido?.equipo_visitante?.nombre}
              </td>
              <td>
                <div className="operations-table__apuesta">
                  <span>{formatSeleccion(op.mercado, op.seleccion)}</span>
                  <span className="operations-table__mercado">{formatMercado(op.mercado)}</span>
                </div>
              </td>
              <td>{formatOdds(op.cuota_apostada)}</td>
              <td className={op.edge >= 0 ? "is-positive" : "is-negative"} title="Probabilidad del modelo - probabilidad implícita del mercado (puntos porcentuales)">
                {op.edge != null ? formatPercent(op.edge) : "-"}
              </td>
              <td className={op.valor_esperado >= 0 ? "is-positive" : "is-negative"} title="Valor esperado proporcional por unidad apostada: (prob. modelo × cuota) - 1">
                {formatPercent(op.valor_esperado)}
              </td>
              <td title={`Kelly fraccional ${formatPercent(op.kelly_fraccion_usada)}`}>
                {formatCurrency(op.stake)}
                <span className="operations-table__mercado"> ({formatPercent(op.kelly_fraccion_usada)} Kelly)</span>
              </td>
              <td className={Number(op.pnl) >= 0 ? "is-positive" : "is-negative"}>
                {op.pnl !== null ? formatCurrency(op.pnl) : "-"}
              </td>
              <td>
                <StatusBadge estado={op.estado} />
              </td>
              <td>{formatDateTime(op.creado_en)}</td>
              {onCambiarOperacion && (
                <td>
                  <AccionesOperacion operacion={op} onCambiar={onCambiarOperacion} />
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
