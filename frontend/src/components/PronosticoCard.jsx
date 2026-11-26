import { useState } from "react";

import TeamCrest from "./TeamCrest";
import { etiquetaPronostico } from "../utils/format";
import "./PronosticoCard.css";

const pct = (p) => `${Math.round(p * 100)}%`;

function nivel(p) {
  if (p >= 0.75) return "alta";
  if (p >= 0.6) return "media";
  return "baja";
}

function Pick({ titulo, pron, partido, destacado }) {
  if (!pron) return null;
  return (
    <div className={`pron-pick pron-pick--${nivel(pron.probabilidad)} ${destacado ? "pron-pick--destacado" : ""}`}>
      <span className="pron-pick__titulo">{titulo}</span>
      <span className="pron-pick__texto">{etiquetaPronostico(pron, partido)}</span>
      <span className="pron-pick__prob">{pct(pron.probabilidad)}</span>
    </div>
  );
}

const miles = (n) => n.toLocaleString("es-CL");

function Simulacion({ sim, partido }) {
  const n = sim.simulaciones;
  const max = Math.max(...sim.marcadores_frecuentes.map((m) => m.veces));
  const filas = [
    [partido.equipo_local.nombre, sim.victorias_local, "local"],
    ["Empate", sim.empates, "empate"],
    [partido.equipo_visitante.nombre, sim.victorias_visitante, "visita"],
  ];
  return (
    <div className="pron-sim">
      <p className="pron-sim__titulo">
        Partido simulado <strong>{miles(n)}</strong> veces
      </p>
      <div className="pron-sim__resultados">
        {filas.map(([nombre, veces, tipo]) => (
          <div key={tipo} className={`pron-sim__res pron-sim__res--${tipo}`}>
            <span className="pron-sim__veces">{miles(veces)}</span>
            <span className="pron-sim__nombre">{nombre}</span>
          </div>
        ))}
      </div>

      <p className="pron-sim__sub">Marcadores más repetidos</p>
      <ul className="pron-sim__marcadores">
        {sim.marcadores_frecuentes.map((m) => (
          <li key={`${m.local}-${m.visitante}`}>
            <span className="pron-sim__marcador">
              {m.local}-{m.visitante}
            </span>
            <span className="pron-sim__bar">
              <span style={{ width: `${(m.veces / max) * 100}%` }} />
            </span>
            <span className="pron-sim__pct">{((m.veces / n) * 100).toFixed(1)}%</span>
          </li>
        ))}
      </ul>

      <div className="pron-sim__extras">
        <span>
          Ambos anotan <strong>{Math.round((sim.ambos_anotan / n) * 100)}%</strong>
        </span>
        <span>
          +2.5 goles <strong>{Math.round((sim.mas_de_2_5 / n) * 100)}%</strong>
        </span>
        <span>
          Goles promedio{" "}
          <strong>
            {sim.goles_promedio_local} - {sim.goles_promedio_visitante}
          </strong>
        </span>
      </div>
      <p className="pron-sim__nota">Simulación del modelo de goles, sin cuotas del mercado.</p>
    </div>
  );
}

export default function PronosticoCard({ pronostico }) {
  const { partido, probabilidades: p } = pronostico;
  const fecha = new Date(partido.fecha_hora);
  const [verSim, setVerSim] = useState(false);

  return (
    <article className="pron-card">
      <header className="pron-card__fecha">
        <span>
          {fecha.toLocaleDateString("es-CL", { weekday: "short", day: "numeric", month: "short" })} ·{" "}
          {fecha.toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" })}
        </span>
        <span
          className={`pron-card__fuente ${pronostico.fuente === "modelo+mercado" ? "pron-card__fuente--mercado" : ""}`}
          title={
            pronostico.fuente === "modelo+mercado"
              ? "Mezcla 50/50 del modelo con las cuotas de las casas de apuestas"
              : "Las cuotas se cargan ~24 h antes del partido; hasta entonces es solo el modelo"
          }
        >
          {pronostico.fuente === "modelo+mercado" ? "Modelo + mercado" : "Modelo"}
        </span>
      </header>

      <div className="pron-card__equipos">
        <div className="pron-card__equipo">
          <TeamCrest equipo={partido.equipo_local} className="pron-card__escudo" />
          <span>{partido.equipo_local.nombre}</span>
        </div>
        <span className="pron-card__vs">vs</span>
        <div className="pron-card__equipo pron-card__equipo--visita">
          <TeamCrest equipo={partido.equipo_visitante} className="pron-card__escudo" />
          <span>{partido.equipo_visitante.nombre}</span>
        </div>
      </div>

      <div className="pron-barra" role="img" aria-label={`Local ${pct(p.LOCAL)}, empate ${pct(p.EMPATE)}, visita ${pct(p.VISITANTE)}`}>
        <div className="pron-barra__seg pron-barra__seg--local" style={{ flexGrow: p.LOCAL }}>
          {pct(p.LOCAL)}
        </div>
        <div className="pron-barra__seg pron-barra__seg--empate" style={{ flexGrow: p.EMPATE }}>
          {pct(p.EMPATE)}
        </div>
        <div className="pron-barra__seg pron-barra__seg--visita" style={{ flexGrow: p.VISITANTE }}>
          {pct(p.VISITANTE)}
        </div>
      </div>
      <div className="pron-barra__leyenda">
        <span>Local</span>
        <span>Empate</span>
        <span>Visita</span>
      </div>

      <div className="pron-card__picks">
        <Pick titulo="Más seguro" pron={pronostico.doble_oportunidad} partido={partido} destacado />
        <Pick titulo="Resultado" pron={pronostico.pronostico} partido={partido} />
        <Pick titulo="Goles" pron={pronostico.goles} partido={partido} />
      </div>

      {pronostico.simulacion && (
        <>
          <button type="button" className="pron-card__toggle" onClick={() => setVerSim((v) => !v)} aria-expanded={verSim}>
            {verSim ? "Ocultar simulación" : `Ver simulación (${miles(pronostico.simulacion.simulaciones)} partidos)`}
          </button>
          {verSim && <Simulacion sim={pronostico.simulacion} partido={partido} />}
        </>
      )}
    </article>
  );
}
