import { useEffect, useState } from "react";

import TeamCrest from "../components/TeamCrest";
import { getTablas } from "../services/api";
import "./Tablas.css";

const DESCENSOS_LIGA = 2;

function Escudo({ nombre, logo, className = "" }) {
  return <TeamCrest equipo={{ nombre, logo_url: logo }} className={`tb-escudo ${className}`} />;
}

function Forma({ forma }) {
  if (!forma?.length) return <span className="tb-muted">—</span>;
  return (
    <div className="tb-forma" aria-label={`Últimos partidos: ${forma.join(", ")}`}>
      {forma.map((r, i) => (
        <span key={i} className={`tb-forma__r tb-forma__r--${r}`}>
          {r}
        </span>
      ))}
    </div>
  );
}

function TablaPosiciones({ filas, campeon, esLiga }) {
  const total = filas.length;
  return (
    <div className="tb-scroll">
      <table className="tb-tabla">
        <thead>
          <tr>
            <th className="tb-c">#</th>
            <th>Equipo</th>
            <th className="tb-c">PJ</th>
            <th className="tb-c tb-hide-sm">G</th>
            <th className="tb-c tb-hide-sm">E</th>
            <th className="tb-c tb-hide-sm">P</th>
            <th className="tb-c tb-hide-md">GF</th>
            <th className="tb-c tb-hide-md">GC</th>
            <th className="tb-c">DIF</th>
            {esLiga && <th className="tb-c tb-hide-sm">Forma</th>}
            <th className="tb-c">PTS</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((f) => {
            const zona =
              campeon === f.equipo
                ? "campeon"
                : esLiga && f.pos > total - DESCENSOS_LIGA
                  ? "descenso"
                  : !esLiga && f.nota
                    ? "clasifica"
                    : "";
            return (
              <tr key={f.equipo} className={zona ? `tb-fila--${zona}` : ""} title={f.nota || undefined}>
                <td className="tb-c">
                  <span className="tb-pos">{f.pos}</span>
                </td>
                <td>
                  <div className="tb-equipo">
                    <Escudo nombre={f.equipo} logo={f.logo_url} />
                    <span className="tb-equipo__nombre">{f.equipo}</span>
                    {campeon === f.equipo && <span className="tb-chip tb-chip--oro">🏆 Campeón</span>}
                  </div>
                </td>
                <td className="tb-c">{f.pj}</td>
                <td className="tb-c tb-hide-sm">{f.g}</td>
                <td className="tb-c tb-hide-sm">{f.e}</td>
                <td className="tb-c tb-hide-sm">{f.p}</td>
                <td className="tb-c tb-hide-md">{f.gf}</td>
                <td className="tb-c tb-hide-md">{f.gc}</td>
                <td className={`tb-c tb-dif ${f.dif > 0 ? "tb-dif--pos" : f.dif < 0 ? "tb-dif--neg" : ""}`}>
                  {f.dif > 0 ? `+${f.dif}` : f.dif}
                </td>
                {esLiga && (
                  <td className="tb-c tb-hide-sm">
                    <Forma forma={f.forma} />
                  </td>
                )}
                <td className="tb-c">
                  <span className="tb-pts">{f.pts}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Podio({ filas }) {
  const top = filas.slice(0, 3);
  if (top.length < 3) return null;
  const orden = [top[1], top[0], top[2]];
  return (
    <div className="tb-podio">
      {orden.map((f) => (
        <div key={f.equipo} className={`tb-podio__item tb-podio__item--${f.pos}`}>
          <Escudo nombre={f.equipo} logo={f.logo_url} className="tb-escudo--xl" />
          <span className="tb-podio__nombre">{f.equipo}</span>
          <span className="tb-podio__pts">{f.pts} pts</span>
          <div className="tb-podio__base">{f.pos}°</div>
        </div>
      ))}
    </div>
  );
}

function Llaves({ llaves, campeon, logoCampeon }) {
  const rondas = [];
  for (const llave of [...llaves].sort((a, b) => a.orden_ronda - b.orden_ronda)) {
    let ronda = rondas.find((r) => r.nombre === llave.ronda);
    if (!ronda) {
      ronda = { nombre: llave.ronda, cruces: [] };
      rondas.push(ronda);
    }
    ronda.cruces.push(llave);
  }

  return (
    <div className="tb-bracket">
      {rondas.map((ronda) => (
        <div key={ronda.nombre} className="tb-bracket__ronda">
          <h3 className="tb-bracket__titulo">{ronda.nombre}</h3>
          <div className="tb-bracket__cruces">
            {ronda.cruces.map((c) => (
              <div key={`${c.local}-${c.visitante}`} className={`tb-cruce ${c.ganador ? "" : "tb-cruce--pendiente"}`}>
                {[
                  [c.local, c.global_local, c.logo_local],
                  [c.visitante, c.global_visitante, c.logo_visitante],
                ].map(([equipo, goles, logo]) => (
                  <div
                    key={equipo}
                    className={`tb-cruce__equipo ${c.ganador === equipo ? "tb-cruce__equipo--gana" : c.ganador ? "tb-cruce__equipo--pierde" : ""}`}
                  >
                    <Escudo nombre={equipo} logo={logo} className="tb-escudo--sm" />
                    <span className="tb-cruce__nombre">{equipo}</span>
                    <span className="tb-cruce__goles">{goles ?? "–"}</span>
                  </div>
                ))}
                <div className="tb-cruce__detalle">{c.ganador ? c.detalle || "Partido único" : "Por jugar"}</div>
              </div>
            ))}
          </div>
        </div>
      ))}
      <div className="tb-bracket__ronda tb-bracket__ronda--campeon">
        <h3 className="tb-bracket__titulo">Campeón</h3>
        <div className={`tb-trofeo ${campeon ? "" : "tb-trofeo--vacio"}`}>
          <span className="tb-trofeo__icono">🏆</span>
          {campeon ? (
            <>
              <Escudo nombre={campeon} logo={logoCampeon} className="tb-escudo--xl" />
              <strong>{campeon}</strong>
            </>
          ) : (
            <span className="tb-muted">Por definir</span>
          )}
        </div>
      </div>
    </div>
  );
}

function Competicion({ comp }) {
  const esLiga = comp.grupos.length === 1 && comp.llaves.length === 0;
  const actualizado = new Date(comp.actualizado_en).toLocaleString("es-CL", { dateStyle: "medium", timeStyle: "short" });
  const filaCampeon = comp.grupos.flatMap((g) => g.filas).find((f) => f.equipo === comp.campeon);
  const llaveCampeon = comp.llaves.find((l) => l.ganador === comp.campeon);
  const logoCampeon =
    filaCampeon?.logo_url ||
    (llaveCampeon && (llaveCampeon.local === comp.campeon ? llaveCampeon.logo_local : llaveCampeon.logo_visitante)) ||
    "";

  return (
    <div className="tb-comp">
      <section className={`tb-hero ${comp.campeon ? "tb-hero--campeon" : ""}`}>
        <div className="tb-hero__texto">
          <span className="tb-hero__temporada">Temporada {comp.temporada}</span>
          <h2 className="tb-hero__titulo">{comp.nombre}</h2>
          {comp.campeon ? (
            <p className="tb-hero__sub">
              🏆 <strong>{comp.campeon}</strong> es el campeón
            </p>
          ) : (
            <p className="tb-hero__sub">{comp.llaves.length ? "Fase eliminatoria en curso" : "En disputa"}</p>
          )}
        </div>
        {comp.campeon && <Escudo nombre={comp.campeon} logo={logoCampeon} className="tb-escudo--hero" />}
      </section>

      {esLiga && <Podio filas={comp.grupos[0].filas} />}

      {comp.llaves.length > 0 && (
        <section className="tb-panel">
          <h3 className="tb-panel__titulo">Fase eliminatoria</h3>
          <Llaves llaves={comp.llaves} campeon={comp.campeon} logoCampeon={logoCampeon} />
        </section>
      )}

      {esLiga ? (
        <section className="tb-panel">
          <h3 className="tb-panel__titulo">Tabla de posiciones</h3>
          <TablaPosiciones filas={comp.grupos[0].filas} campeon={comp.campeon} esLiga />
          <div className="tb-leyenda">
            <span>
              <i className="tb-leyenda__dot tb-leyenda__dot--campeon" /> Campeón
            </span>
            <span>
              <i className="tb-leyenda__dot tb-leyenda__dot--descenso" /> Zona de descenso
            </span>
          </div>
        </section>
      ) : (
        <>
          <h3 className="tb-seccion">Fase de grupos</h3>
          <div className="tb-grupos">
            {comp.grupos.map((g) => (
              <section key={g.nombre} className="tb-panel tb-panel--grupo">
                <h3 className="tb-panel__titulo">{g.nombre}</h3>
                <TablaPosiciones filas={g.filas} />
              </section>
            ))}
          </div>
          <div className="tb-leyenda">
            <span>
              <i className="tb-leyenda__dot tb-leyenda__dot--clasifica" /> Clasificado a la siguiente fase
            </span>
          </div>
        </>
      )}

      <p className="tb-fuente">
        Actualizado {actualizado} ·{" "}
        <a href={comp.fuente} target="_blank" rel="noreferrer">
          Ver fuente
        </a>
      </p>
    </div>
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
        <p className="page-header__subtitle">Liga de Primera, Copa Chile y Copa de la Liga — se actualizan solas cada hora.</p>
      </header>

      {loading && <p className="page-status">Cargando...</p>}
      {error && <p className="page-status page-status--error">Error: {error}</p>}
      {!loading && !error && tablas.length === 0 && <p className="page-status">Todavía no hay tablas cargadas.</p>}

      {tablas.length > 0 && (
        <>
          <div className="tb-tabs" role="tablist">
            {tablas.map((t, i) => (
              <button
                key={t.slug}
                role="tab"
                aria-selected={i === activa}
                className={`tb-tab ${i === activa ? "tb-tab--activa" : ""}`}
                onClick={() => setActiva(i)}
              >
                {t.nombre}
                {t.campeon && <span className="tb-tab__trofeo">🏆</span>}
              </button>
            ))}
          </div>
          <Competicion comp={tablas[activa]} />
        </>
      )}
    </div>
  );
}
