import { useEffect, useState } from "react";

import Card from "../components/Card";
import TeamCrest from "../components/TeamCrest";
import { getTablas } from "../services/api";
import "./Tablas.css";

function TablaGrupo({ grupo, campeon }) {
  return (
    <div className="operations-table__scroll">
      <table className="operations-table tablas__tabla">
        <thead>
          <tr>
            <th>#</th>
            <th>Equipo</th>
            <th className="tablas__num">Pts</th>
            <th className="tablas__num">PJ</th>
            <th className="tablas__num">G</th>
            <th className="tablas__num">E</th>
            <th className="tablas__num">P</th>
            <th className="tablas__num tablas__ocultable">GF</th>
            <th className="tablas__num tablas__ocultable">GC</th>
            <th className="tablas__num">Dif</th>
          </tr>
        </thead>
        <tbody>
          {grupo.filas.map((f) => (
            <tr key={f.equipo} className={f.nota ? "tablas__fila--clasifica" : ""} title={f.nota || undefined}>
              <td className="tablas__pos">{f.pos}</td>
              <td>
                <div className="tablas__equipo">
                  <TeamCrest equipo={{ nombre: f.equipo, logo_url: f.logo_url }} className="tablas__escudo" />
                  <span>{f.equipo}</span>
                  {campeon === f.equipo && <span className="tablas__badge">Campeón</span>}
                </div>
              </td>
              <td className="tablas__num tablas__pts">{f.pts}</td>
              <td className="tablas__num">{f.pj}</td>
              <td className="tablas__num">{f.g}</td>
              <td className="tablas__num">{f.e}</td>
              <td className="tablas__num">{f.p}</td>
              <td className="tablas__num tablas__ocultable">{f.gf}</td>
              <td className="tablas__num tablas__ocultable">{f.gc}</td>
              <td className="tablas__num">{f.dif > 0 ? `+${f.dif}` : f.dif}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Llaves({ llaves }) {
  const rondas = [];
  for (const llave of llaves) {
    let ronda = rondas.find((r) => r.nombre === llave.ronda);
    if (!ronda) {
      ronda = { nombre: llave.ronda, cruces: [] };
      rondas.push(ronda);
    }
    ronda.cruces.push(llave);
  }

  return (
    <div className="tablas__llaves">
      {rondas.map((ronda) => (
        <div key={ronda.nombre} className="tablas__ronda">
          <h3>{ronda.nombre}</h3>
          {ronda.cruces.map((c) => (
            <div key={`${c.local}-${c.visitante}`} className="tablas__cruce">
              {[
                [c.local, c.global_local],
                [c.visitante, c.global_visitante],
              ].map(([equipo, goles]) => (
                <div
                  key={equipo}
                  className={`tablas__cruce-equipo ${c.ganador === equipo ? "tablas__cruce-equipo--gana" : ""}`}
                >
                  <span>{equipo}</span>
                  <span className="tablas__cruce-goles">{goles ?? "–"}</span>
                </div>
              ))}
              <div className="tablas__cruce-detalle">{c.ganador ? c.detalle : "Por jugar"}</div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function Competicion({ comp }) {
  const actualizado = new Date(comp.actualizado_en).toLocaleString("es-CL", {
    dateStyle: "short",
    timeStyle: "short",
  });

  return (
    <>
      {comp.campeon && (
        <div className="tablas__campeon">
          🏆 <strong>{comp.campeon}</strong> campeón de {comp.nombre} {comp.temporada}
        </div>
      )}

      {comp.llaves.length > 0 && (
        <Card title="Fase eliminatoria">
          <Llaves llaves={comp.llaves} />
        </Card>
      )}

      {comp.grupos.length === 1 ? (
        <Card title="Tabla de posiciones">
          <TablaGrupo grupo={comp.grupos[0]} campeon={comp.campeon} />
        </Card>
      ) : (
        <div className="tablas__grupos">
          {comp.grupos.map((g) => (
            <Card key={g.nombre} title={g.nombre}>
              <TablaGrupo grupo={g} />
            </Card>
          ))}
        </div>
      )}

      <p className="tablas__fuente">
        Actualizado {actualizado} ·{" "}
        <a href={comp.fuente} target="_blank" rel="noreferrer">
          fuente
        </a>
      </p>
    </>
  );
}

export default function Tablas() {
  const [tablas, setTablas] = useState([]);
  const [activa, setActiva] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getTablas()
      .then(setTablas)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="tablas-page">
      <header className="page-header">
        <h1>Tablas</h1>
        <p className="page-header__subtitle">Posiciones de la Liga de Primera, Copa Chile y Copa de la Liga.</p>
      </header>

      {loading && <p className="page-status">Cargando...</p>}
      {error && <p className="page-status page-status--error">Error: {error}</p>}
      {!loading && !error && tablas.length === 0 && (
        <p className="page-status">Todavía no hay tablas cargadas (se actualizan con el pipeline horario).</p>
      )}

      {tablas.length > 0 && (
        <>
          <div className="tablas__tabs" role="tablist">
            {tablas.map((t, i) => (
              <button
                key={t.slug}
                role="tab"
                aria-selected={i === activa}
                className={i === activa ? "active" : ""}
                onClick={() => setActiva(i)}
              >
                {t.nombre}
              </button>
            ))}
          </div>
          <Competicion comp={tablas[activa]} />
        </>
      )}
    </div>
  );
}
