import { useState } from "react";

import PartidoCell from "./PartidoCell";
import StatusBadge from "./StatusBadge";
import {
  aceptarCombinada,
  descartarCombinada,
  marcarCombinadaAnulada,
  marcarCombinadaGanada,
  marcarCombinadaPerdida,
  revertirCombinada,
} from "../services/api";
import { formatCurrency, formatMercado, formatOdds, formatPercent, formatSeleccion } from "../utils/format";
import "./CombinadasList.css";

function AccionesCombinada({ combinada, onCambiar }) {
  const [enviando, setEnviando] = useState(false);

  const ejecutar = async (accion) => {
    setEnviando(true);
    try {
      const actualizada = await accion(combinada.id);
      onCambiar(actualizada);
    } catch {
      alert("No se pudo aplicar la acción. Puede que ya se haya actualizado desde otro lado.");
    } finally {
      setEnviando(false);
    }
  };

  const ejecutarConConfirmacion = (accion, mensaje) => {
    if (window.confirm(mensaje)) ejecutar(accion);
  };

  if (combinada.estado === "RECOMMENDED") {
    return (
      <div className="operations-table__acciones">
        <button className="operations-table__accion--primary" disabled={enviando} onClick={() => ejecutar(aceptarCombinada)}>
          Aceptar
        </button>
        <button disabled={enviando} onClick={() => ejecutar(descartarCombinada)}>
          Descartar
        </button>
      </div>
    );
  }

  if (combinada.estado === "ACCEPTED") {
    return (
      <div className="operations-table__acciones">
        <button
          className="operations-table__accion--good"
          disabled={enviando}
          onClick={() =>
            ejecutarConConfirmacion(marcarCombinadaGanada, "¿Confirmás que la combinada completa ganó? Calcula el PNL.")
          }
        >
          Ganó
        </button>
        <button
          className="operations-table__accion--danger"
          disabled={enviando}
          onClick={() =>
            ejecutarConConfirmacion(marcarCombinadaPerdida, "¿Confirmás que perdió (alguna pata falló)?")
          }
        >
          Perdió
        </button>
        <button
          disabled={enviando}
          onClick={() =>
            ejecutarConConfirmacion(
              marcarCombinadaAnulada,
              "¿Confirmás anular (push)? Se devuelve el stake, sin efecto en el PNL."
            )
          }
        >
          Anulada
        </button>
      </div>
    );
  }

  if (["WON", "LOST", "VOID"].includes(combinada.estado)) {
    return (
      <button
        className="operations-table__deshacer"
        disabled={enviando}
        onClick={() =>
          ejecutarConConfirmacion(revertirCombinada, '¿Deshacer esto y volver a "Aceptada"? Se borra el PNL calculado.')
        }
        title='Volver a "Aceptada" -- por si se marcó por error'
      >
        Deshacer
      </button>
    );
  }

  return null;
}

export default function CombinadasList({ combinadas, onCambiarCombinada }) {
  if (!combinadas.length) {
    return (
      <p className="operations-table__empty">
        No hay combinadas sugeridas ahora mismo -- hacen falta al menos 2 partidos distintos con
        recomendación de valor vigente para armar una.
      </p>
    );
  }

  return (
    <div className="combinadas-list">
      {combinadas.map((c) => (
        <div key={c.id} className="combinada-card">
          <div className="combinada-card__header">
            <span className="combinada-card__patas-count">{c.patas.length} patas</span>
            <StatusBadge estado={c.estado} />
          </div>

          <ul className="combinada-card__patas">
            {c.patas.map((pata) => (
              <li key={pata.id}>
                <PartidoCell partido={pata.partido} />
                <span className="combinada-card__apuesta">
                  {formatSeleccion(pata.mercado, pata.seleccion_evaluada)} ({formatMercado(pata.mercado)}) @{" "}
                  {formatOdds(pata.cuota_mercado)}
                  <span className="operations-table__mercado"> · prob. {formatPercent(pata.probabilidad_seleccion)}</span>
                </span>
              </li>
            ))}
          </ul>

          <div className="combinada-card__resumen">
            <div>
              <span className="operations-table__mercado">Cuota combinada</span>
              <strong>{formatOdds(c.cuota_combinada)}</strong>
            </div>
            <div>
              <span className="operations-table__mercado">Probabilidad</span>
              <strong>{formatPercent(c.probabilidad_combinada)}</strong>
            </div>
            <div>
              <span className="operations-table__mercado">EV</span>
              <strong className={c.valor_esperado >= 0 ? "is-positive" : "is-negative"}>
                {formatPercent(c.valor_esperado)}
              </strong>
            </div>
            <div>
              <span className="operations-table__mercado">Stake sugerido</span>
              <strong>{formatCurrency(c.stake)}</strong>
            </div>
            {c.pnl !== null && (
              <div>
                <span className="operations-table__mercado">PNL</span>
                <strong className={Number(c.pnl) >= 0 ? "is-positive" : "is-negative"}>
                  {formatCurrency(c.pnl)}
                </strong>
              </div>
            )}
          </div>

          {onCambiarCombinada && (
            <div className="combinada-card__acciones">
              <AccionesCombinada combinada={c} onCambiar={onCambiarCombinada} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
