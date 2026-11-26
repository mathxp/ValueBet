import TeamCrest from "./TeamCrest";
import "./PartidoCell.css";

/**
 * Escudos de ambos equipos en vez del nombre completo -- para tablas donde
 * "Universidad de Concepcion vs Huachipato" como texto ocupa demasiado
 * espacio horizontal. El nombre completo queda como title (tooltip nativo).
 */
export default function PartidoCell({ partido }) {
  if (!partido?.equipo_local || !partido?.equipo_visitante) return null;

  return (
    <div
      className="partido-cell"
      title={`${partido.equipo_local.nombre} vs ${partido.equipo_visitante.nombre}`}
    >
      <TeamCrest equipo={partido.equipo_local} className="partido-cell__crest" />
      <span className="partido-cell__vs">vs</span>
      <TeamCrest equipo={partido.equipo_visitante} className="partido-cell__crest" />
    </div>
  );
}
