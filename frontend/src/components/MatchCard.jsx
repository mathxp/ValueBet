import { formatDateTime, formatPercent } from "../utils/format";
import TeamCrest from "./TeamCrest";
import "./MatchCard.css";

function FilaEquipo({ equipo, xg }) {
  return (
    <div className="match-card__row">
      <div className="match-card__team">
        <TeamCrest equipo={equipo} className="match-card__crest" />
        <span className="match-card__team-name">{equipo.nombre}</span>
      </div>
      {xg !== null ? (
        <span className="match-card__xg-value">{xg.toFixed(1)}</span>
      ) : (
        <span className="match-card__xg-empty">—</span>
      )}
    </div>
  );
}

function favorito(partido, probabilidades) {
  if (!probabilidades) return null;

  const opciones = [
    { clave: "LOCAL", nombre: partido.equipo_local.nombre, prob: probabilidades.LOCAL },
    { clave: "EMPATE", nombre: "Empate", prob: probabilidades.EMPATE },
    { clave: "VISITANTE", nombre: partido.equipo_visitante.nombre, prob: probabilidades.VISITANTE },
  ];
  return opciones.reduce((mejor, actual) => (actual.prob > mejor.prob ? actual : mejor));
}

export default function MatchCard({ partido, prediccion }) {
  const disponible = prediccion?.disponible;
  const gana = disponible ? favorito(partido, prediccion.probabilidades) : null;

  return (
    <div className="match-card">
      <div className="match-card__meta">{formatDateTime(partido.fecha_hora)}</div>

      <div className="match-card__matchup">
        <FilaEquipo equipo={partido.equipo_local} xg={disponible ? prediccion.xg_local : null} />
        <span className="match-card__vs">VS</span>
        <FilaEquipo
          equipo={partido.equipo_visitante}
          xg={disponible ? prediccion.xg_visitante : null}
        />
      </div>

      {gana && (
        <div className="match-card__favorito">
          <span className="match-card__favorito-badge">{formatPercent(gana.prob)}</span>
          {gana.clave === "EMPATE" ? (
            <span>
              Resultado más probable: <strong>empate</strong>
            </span>
          ) : (
            <span>
              Favorito: <strong>{gana.nombre}</strong>
            </span>
          )}
        </div>
      )}

      {!disponible && (
        <p className="match-card__hint">
          Alguno de los dos equipos todavía no acumula suficientes partidos jugados para proyectar
          goles esperados de forma confiable.
        </p>
      )}
    </div>
  );
}
