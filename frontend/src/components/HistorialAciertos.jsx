import { useEffect, useState } from "react";

import ChipCompeticion from "./ChipCompeticion";
import { getHistorialPronosticos } from "../services/api";
import { formatPercent } from "../utils/format";
import "./HistorialAciertos.css";

const PICK_TEXTO = {
  LOCAL: "Local",
  EMPATE: "Empate",
  VISITANTE: "Visita",
  "1X": "Local o empate",
  X2: "Visita o empate",
  12: "Sin empate",
};

function Fecha({ g }) {
  const [abierta, setAbierta] = useState(false);
  const pct = g.aciertos_seguro / g.partidos;
  return (
    <li className="hist-fecha">
      <button type="button" className="hist-fecha__fila" onClick={() => setAbierta((v) => !v)} aria-expanded={abierta}>
        <ChipCompeticion nombre={g.competicion} />
        <span className="hist-fecha__nombre">
          {g.etiqueta_fecha}
          {g.reconstruido && (
            <span
              className="hist-fecha__tag"
              title="Calculado después, con el modelo usando solo partidos anteriores a cada uno"
            >
              reconstruido
            </span>
          )}
        </span>
        <span className="hist-fecha__dato">
          <strong>
            {g.aciertos_seguro}/{g.partidos}
          </strong>{" "}
          más seguro
        </span>
        <span className="hist-fecha__dato hist-fecha__dato--sec">
          {g.aciertos_1x2}/{g.partidos} resultado
        </span>
        <span className="hist-fecha__barra" aria-hidden="true">
          <span style={{ width: `${pct * 100}%` }} />
        </span>
      </button>
      {abierta && (
        <ul className="hist-detalle">
          {g.detalle.map((d, i) => (
            <li key={i}>
              <span className="hist-detalle__partido">
                {d.local} <strong>{d.marcador}</strong> {d.visitante}
              </span>
              <span className={`hist-detalle__pick ${d.acierto_seguro ? "ok" : "no"}`}>
                {d.acierto_seguro ? "✓" : "✗"} {PICK_TEXTO[d.pick_seguro] ?? d.pick_seguro}
              </span>
              <span className={`hist-detalle__pick ${d.acierto_1x2 ? "ok" : "no"}`}>
                {d.acierto_1x2 ? "✓" : "✗"} {PICK_TEXTO[d.pick_1x2] ?? d.pick_1x2}
              </span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export default function HistorialAciertos() {
  const [datos, setDatos] = useState(null);

  useEffect(() => {
    getHistorialPronosticos()
      .then(setDatos)
      .catch(() => setDatos(null));
  }, []);

  if (!datos || !datos.fechas?.length) return null;
  const t = datos.temporada;

  return (
    <section className="hist">
      <h2 className="seccion-titulo">📊 ¿Cómo nos fue?</h2>
      {t?.partidos > 0 && (
        <div className="hist-kpis">
          <div>
            <span className="hist-kpis__valor">{formatPercent(t.acierto_seguro)}</span>
            <span className="hist-kpis__label">acierto del &quot;más seguro&quot; · {t.anio}</span>
          </div>
          <div>
            <span className="hist-kpis__valor">{formatPercent(t.acierto_1x2)}</span>
            <span className="hist-kpis__label">acierto del resultado (1X2)</span>
          </div>
          <div>
            <span className="hist-kpis__valor">{formatPercent(t.acierto_goles)}</span>
            <span className="hist-kpis__label">acierto en goles (±2.5)</span>
          </div>
          <div>
            <span className="hist-kpis__valor">{t.partidos}</span>
            <span className="hist-kpis__label">partidos evaluados</span>
          </div>
        </div>
      )}
      <ul className="hist-lista">
        {datos.fechas.map((g) => (
          <Fecha key={`${g.competicion}|${g.etiqueta_fecha}|${g.temporada}`} g={g} />
        ))}
      </ul>
      <p className="pron-nota">
        &quot;Reconstruido&quot;: pronóstico calculado después del partido, con el modelo usando solo los partidos
        jugados antes de cada uno. Desde ahora cada pronóstico se guarda antes de que empiece el partido.
      </p>
    </section>
  );
}
