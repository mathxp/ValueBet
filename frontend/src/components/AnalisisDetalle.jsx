import { formatCurrency, formatDateTime, formatMercado, formatOdds, formatPercent, formatSeleccion } from "../utils/format";

// Mismos umbrales que ml_models/pipelines/quality.py -- si cambian ahí,
// cambiar acá también (no hay un endpoint que los exponga todavía).
const MIN_DATA_QUALITY_SCORE = 40;
const MIN_CONFIDENCE_SCORE = 35;

function Factor({ favorable, texto }) {
  return (
    <li className={`analisis-detalle__factor analisis-detalle__factor--${favorable ? "favorable" : "desfavorable"}`}>
      <span aria-hidden="true">{favorable ? "🟢" : "🔴"}</span> {texto}
    </li>
  );
}

function calcularFactores(a) {
  const factores = [];

  if (a.xg_local != null && a.xg_visitante != null) {
    const diferencia = a.xg_local - a.xg_visitante;
    if (Math.abs(diferencia) < 0.3) {
      factores.push({ favorable: null, texto: "Ataque proyectado parejo entre ambos equipos" });
    } else if (diferencia > 0) {
      factores.push({ favorable: true, texto: `Ataque proyectado favorece al local (+${diferencia.toFixed(2)} goles)` });
    } else {
      factores.push({ favorable: true, texto: `Ataque proyectado favorece al visitante (+${(-diferencia).toFixed(2)} goles)` });
    }
  }

  if (a.edge != null) {
    factores.push(
      a.edge > 0
        ? { favorable: true, texto: `El modelo ve ${formatPercent(a.edge)} más probabilidad que el mercado` }
        : { favorable: false, texto: `El mercado ya paga acorde (o mejor) a lo que calcula el modelo` }
    );
  }

  factores.push({
    favorable: a.data_quality_score >= MIN_DATA_QUALITY_SCORE,
    texto: `Calidad de datos ${a.data_quality_score}/100 (mínimo ${MIN_DATA_QUALITY_SCORE})`,
  });
  factores.push({
    favorable: a.confidence_score >= MIN_CONFIDENCE_SCORE,
    texto: `Confianza ${a.confidence_score}/100 (mínimo ${MIN_CONFIDENCE_SCORE})`,
  });

  return factores;
}

export default function AnalisisDetalle({ analisis: a }) {
  const factores = calcularFactores(a);

  return (
    <div className="analisis-detalle">
      <section className="analisis-detalle__seccion">
        <h3>Goles esperados proyectados</h3>
        <div className="analisis-detalle__xg">
          <div>
            <span className="analisis-detalle__xg-equipo">{a.partido?.equipo_local?.nombre}</span>
            <span className="analisis-detalle__xg-valor">{a.xg_local != null ? a.xg_local.toFixed(2) : "-"}</span>
          </div>
          <div>
            <span className="analisis-detalle__xg-equipo">{a.partido?.equipo_visitante?.nombre}</span>
            <span className="analisis-detalle__xg-valor">{a.xg_visitante != null ? a.xg_visitante.toFixed(2) : "-"}</span>
          </div>
        </div>
        {a.probabilidad_local != null && (
          <p className="config-hint">
            Probabilidad 1X2 -- Local {formatPercent(a.probabilidad_local)} · Empate{" "}
            {formatPercent(a.probabilidad_empate)} · Visitante {formatPercent(a.probabilidad_visitante)}
          </p>
        )}
      </section>

      <section className="analisis-detalle__seccion">
        <h3>Mercado evaluado</h3>
        <dl className="config-list">
          <div>
            <dt>Apuesta</dt>
            <dd>
              {a.mercado === "GENERAL" ? "Sin datos para analizar" : formatSeleccion(a.mercado, a.seleccion_evaluada)}
              {a.mercado !== "GENERAL" && ` (${formatMercado(a.mercado)})`}
            </dd>
          </div>
          <div>
            <dt>Cuota de mercado</dt>
            <dd>{a.cuota_mercado != null ? formatOdds(a.cuota_mercado) : "-"}</dd>
          </div>
          <div>
            <dt>Cuota justa (según el modelo)</dt>
            <dd>{a.cuota_justa != null ? formatOdds(a.cuota_justa) : "-"}</dd>
          </div>
          <div>
            <dt>Probabilidad del modelo</dt>
            <dd>{a.probabilidad_seleccion != null ? formatPercent(a.probabilidad_seleccion) : "-"}</dd>
          </div>
          <div>
            <dt>Probabilidad implícita del mercado</dt>
            <dd>{a.probabilidad_implicita != null ? formatPercent(a.probabilidad_implicita) : "-"}</dd>
          </div>
          <div>
            <dt>Edge (puntos porcentuales)</dt>
            <dd>{a.edge != null ? formatPercent(a.edge) : "-"}</dd>
          </div>
          <div>
            <dt>EV (proporcional)</dt>
            <dd>{a.ev != null ? formatPercent(a.ev) : "-"}</dd>
          </div>
          {a.stake_sugerido != null && (
            <div>
              <dt>Stake sugerido</dt>
              <dd>
                {formatCurrency(a.stake_sugerido)}
                {a.kelly_fraccion_usada != null && ` (${formatPercent(a.kelly_fraccion_usada)} Kelly)`}
              </dd>
            </div>
          )}
        </dl>
      </section>

      <section className="analisis-detalle__seccion">
        <h3>Factores a favor / en contra</h3>
        <ul className="analisis-detalle__factores">
          {factores.map((f, i) => (
            <Factor key={i} favorable={f.favorable ?? true} texto={f.texto} />
          ))}
        </ul>
      </section>

      {a.motivo_no_bet && (
        <section className="analisis-detalle__seccion">
          <h3>Motivo</h3>
          <p className="config-hint">{a.motivo_no_bet}</p>
        </section>
      )}

      <p className="config-hint">Analizado el {formatDateTime(a.fecha_analisis)}.</p>
    </div>
  );
}
