import PartidoCell from "./PartidoCell";
import { formatMercado, formatOdds, formatPercent, formatSeleccion } from "../utils/format";
import "./MejorApuestaCard.css";

/**
 * La única apuesta que el sistema destaca de toda la fecha -- no "la de mayor
 * EV", sino la mejor entre las que además pasan un piso de probabilidad más
 * exigente que el general (ver PROBABILIDAD_MINIMA_DESTACADA en
 * Predicciones.jsx). La idea explícita: tratar de acertar, no maximizar
 * valor esperado puro -- ver InfoBox "Sobre las combinadas" para la misma
 * filosofía aplicada a las combinadas.
 */
export default function MejorApuestaCard({ analisis }) {
  if (!analisis) {
    return (
      <div className="mejor-apuesta mejor-apuesta--vacia">
        <span className="mejor-apuesta__icono" aria-hidden="true">
          ⚪
        </span>
        <div>
          <p className="mejor-apuesta__titulo">No hay una apuesta lo bastante segura hoy</p>
          <p className="mejor-apuesta__detalle">
            Hay valor en algunos partidos, pero ninguno con suficiente probabilidad como para
            destacarlo acá. Revisá el análisis completo más abajo si igual te interesa ver el
            detalle.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mejor-apuesta">
      <div className="mejor-apuesta__encabezado">
        <span className="mejor-apuesta__etiqueta">⭐ Mejor apuesta de la fecha</span>
        <span className="mejor-apuesta__score" title="Value Score: combina EV, calibración, calidad de datos y confianza">
          Score {analisis.value_score}/100
        </span>
      </div>

      <PartidoCell partido={analisis.partido} />

      <div className="mejor-apuesta__pick">
        <span className="mejor-apuesta__seleccion">
          {formatSeleccion(analisis.mercado, analisis.seleccion_evaluada)}
        </span>
        <span className="mejor-apuesta__mercado">{formatMercado(analisis.mercado)}</span>
      </div>

      <div className="mejor-apuesta__numeros">
        <div>
          <span className="mejor-apuesta__numero-label">Probabilidad</span>
          <strong>{formatPercent(analisis.probabilidad_seleccion)}</strong>
        </div>
        <div>
          <span className="mejor-apuesta__numero-label">Cuota</span>
          <strong>{formatOdds(analisis.cuota_mercado)}</strong>
        </div>
        <div>
          <span className="mejor-apuesta__numero-label">EV</span>
          <strong className={analisis.ev >= 0 ? "is-positive" : "is-negative"}>
            {formatPercent(analisis.ev)}
          </strong>
        </div>
      </div>

      <p className="mejor-apuesta__nota">
        De todas las recomendaciones con valor de la fecha, esta es la de mayor probabilidad real
        de acertar y mejor puntaje combinado -- no necesariamente la de EV más alto.
      </p>
    </div>
  );
}
