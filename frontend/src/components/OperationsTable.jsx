import { useState } from "react";

import PartidoCell from "./PartidoCell";
import StatusBadge from "./StatusBadge";
import {
  aceptarOperacion,
  descartarOperacion,
  marcarOperacionAnulada,
  marcarOperacionGanada,
  marcarOperacionPerdida,
  revertirOperacion,
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

  // Ganó/Perdió/Anulada calculan PNL y son fáciles de tocar sin querer en el
  // celular (los botones cambian de posición justo después de "Aceptar" --
  // un segundo toque accidental cae directo acá). La confirmación frena eso:
  // un doble-toque en el mismo lugar ya no alcanza para confirmar solo.
  const ejecutarConConfirmacion = (accion, mensaje) => {
    if (window.confirm(mensaje)) {
      ejecutar(accion);
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
          onClick={() =>
            ejecutarConConfirmacion(marcarOperacionGanada, "¿Confirmás que esta apuesta ganó? Calcula el PNL.")
          }
        >
          Ganó
        </button>
        <button
          className="operations-table__accion--danger"
          disabled={enviando}
          onClick={() => ejecutarConConfirmacion(marcarOperacionPerdida, "¿Confirmás que esta apuesta perdió?")}
        >
          Perdió
        </button>
        <button
          disabled={enviando}
          onClick={() =>
            ejecutarConConfirmacion(
              marcarOperacionAnulada,
              "¿Confirmás anular (push)? Se devuelve el stake, sin efecto en el PNL."
            )
          }
        >
          Anulada
        </button>
      </div>
    );
  }

  if (["WON", "LOST", "VOID"].includes(operacion.estado)) {
    return (
      <button
        className="operations-table__deshacer"
        disabled={enviando}
        onClick={() =>
          ejecutarConConfirmacion(revertirOperacion, '¿Deshacer esto y volver a "Aceptada"? Se borra el PNL calculado.')
        }
        title='Volver a "Aceptada" -- por si se marcó por error'
      >
        Deshacer
      </button>
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
            {onCambiarOperacion && <th>Acciones</th>}
          </tr>
        </thead>
        <tbody>
          {operaciones.map((op) => (
            <tr key={op.id}>
              <td>
                <PartidoCell partido={op.partido} />
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
              </td>
              <td className={Number(op.pnl) >= 0 ? "is-positive" : "is-negative"}>
                {op.pnl !== null ? formatCurrency(op.pnl) : "-"}
              </td>
              <td title={`Recomendada el ${formatDateTime(op.creado_en)}`}>
                <StatusBadge estado={op.estado} />
              </td>
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
