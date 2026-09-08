import { useEffect, useMemo, useState } from "react";

import AnalysisTable from "../components/AnalysisTable";
import Card from "../components/Card";
import InfoBox from "../components/InfoBox";
import OperationsTable from "../components/OperationsTable";
import PnlLineChart from "../components/PnlLineChart";
import RendimientoBacktest from "../components/RendimientoBacktest";
import RendimientoModelo from "../components/RendimientoModelo";
import RendimientoPorMercado from "../components/RendimientoPorMercado";
import RendimientoValueBets from "../components/RendimientoValueBets";
import StatTile from "../components/StatTile";
import {
  getAnalisis,
  getConfiguracion,
  getOperaciones,
  getResumenOperaciones,
} from "../services/api";
import { ESTADO_OPERACION_CONFIG, formatCurrency, formatMercado, formatPercent } from "../utils/format";

const PAGE_SIZE = 25;

// Líneas históricas: 4.5 ya no se recomienda (ver LINEAS_OVER_UNDER_VALIDAS
// en el backend), pero sigue en el historial de análisis viejos.
const MERCADOS_FILTRO = ["1X2", "OVER_UNDER_1.5", "OVER_UNDER_2.5", "OVER_UNDER_3.5", "OVER_UNDER_4.5"];
// Igual que LINEAS_OVER_UNDER_VALIDAS en el backend -- se usa para no
// mostrar en "partidos pendientes" un mercado que ya no se escanea (ej. 4.5),
// que si no quedaría congelado ahí para siempre con su último estado viejo.
const MERCADOS_VIGENTES = new Set(["1X2", "OVER_UNDER_1.5", "OVER_UNDER_2.5", "OVER_UNDER_3.5"]);
const TEMPORADAS_FILTRO = ["2022", "2023", "2024", "2025", "2026"];

function labelMercado(mercado) {
  return mercado === "1X2" ? "Resultado (1X2)" : formatMercado(mercado);
}

export default function Recomendaciones() {
  const [resumen, setResumen] = useState(null);
  const [config, setConfig] = useState(null);
  const [contadorValueBet, setContadorValueBet] = useState(null);
  const [contadorNoBet, setContadorNoBet] = useState(null);
  const [operaciones, setOperaciones] = useState([]);
  const [analisis, setAnalisis] = useState([]);
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filtroMercado, setFiltroMercado] = useState("");
  const [filtroEstado, setFiltroEstado] = useState("");
  const [filtroTemporada, setFiltroTemporada] = useState("");

  useEffect(() => {
    setLoading(true);
    const filtros = {
      ...(filtroMercado && { mercado: filtroMercado }),
      ...(filtroEstado && { estado: filtroEstado }),
      ...(filtroTemporada && { partido__temporada: filtroTemporada }),
    };
    Promise.all([
      getResumenOperaciones(),
      getOperaciones({ page, ...filtros }),
      // "Historial completo" abajo es para decidir qué hacer HOY -- los
      // partidos que ya se jugaron no aportan nada ahí (el rendimiento
      // histórico del modelo, incluidos los ya jugados, se ve aparte en
      // RendimientoModelo).
      getAnalisis({ partido__fecha_hora__gte: new Date().toISOString() }),
    ])
      .then(([resumenData, operacionesData, analisisData]) => {
        setResumen(resumenData);
        setOperaciones(operacionesData.results ?? operacionesData);
        setCount(operacionesData.count ?? (operacionesData.results ?? operacionesData).length);
        setAnalisis(analisisData.results ?? analisisData);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [page, filtroMercado, filtroEstado, filtroTemporada]);

  useEffect(() => {
    // Bankroll y conteo de VALUE BET/NO BET: no dependen de página ni
    // filtros, se piden una sola vez. El conteo sale de `count` en la
    // respuesta paginada -- ese total ya es correcto sin importar cuántos
    // resultados trae la página en sí.
    getConfiguracion().then(setConfig).catch(() => setConfig(null));
    getAnalisis({ recomendacion: "VALUE_BET" })
      .then((d) => setContadorValueBet(d.count))
      .catch(() => setContadorValueBet(null));
    getAnalisis({ recomendacion: "NO_BET" })
      .then((d) => setContadorNoBet(d.count))
      .catch(() => setContadorNoBet(null));
  }, []);

  const cambiarFiltro = (setter) => (e) => {
    setPage(1);
    setter(e.target.value);
  };

  // "Partidos pendientes" es para decidir qué hacer AHORA, no un historial
  // completo -- si no se dedupe, un partido que se escaneó varias veces (cada
  // 30s) muestra su análisis viejo y el nuevo juntos, como si el viejo
  // siguiera vigente (pasó con Over 3.5: la versión sin calibrar y la
  // calibrada aparecían las dos). Además se excluyen mercados que ya no se
  // evalúan (ver MERCADOS_VIGENTES) -- si no, una línea retirada (4.5) queda
  // congelada mostrando para siempre su último resultado, que ya no es real.
  const analisisVigente = useMemo(() => {
    const masReciente = new Map();
    for (const a of analisis) {
      if (a.mercado !== "GENERAL" && !MERCADOS_VIGENTES.has(a.mercado)) continue;
      const clave = `${a.partido?.id}|${a.mercado}`;
      const actual = masReciente.get(clave);
      if (!actual || new Date(a.fecha_analisis) > new Date(actual.fecha_analisis)) {
        masReciente.set(clave, a);
      }
    }
    return Array.from(masReciente.values()).sort(
      (a, b) => new Date(b.fecha_analisis) - new Date(a.fecha_analisis)
    );
  }, [analisis]);

  const pnlPoints = useMemo(() => {
    let acumulado = 0;
    return [...operaciones]
      .reverse()
      .filter((op) => op.pnl !== null)
      .map((op) => {
        acumulado += Number(op.pnl);
        return { label: op.creado_en, value: acumulado };
      });
  }, [operaciones]);

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  const handleCambiarOperacion = (actualizada) => {
    setOperaciones((actuales) => actuales.map((op) => (op.id === actualizada.id ? actualizada : op)));
    getResumenOperaciones().then(setResumen);
  };

  return (
    <div className="recomendaciones-page">
      <header className="page-header">
        <h1>Recomendaciones de valor</h1>
        <p className="page-header__subtitle">
          Cuando el modelo cree tener un edge real sobre una cuota de mercado, lo anota acá. Es
          apoyo para decidir, no ejecuta ninguna apuesta.
        </p>
      </header>

      <InfoBox title="Qué significa cada columna y cómo se usa esto">
        <p>
          <strong>Edge</strong> y <strong>EV</strong> no son lo mismo, aunque midan algo parecido:{" "}
          <br />
          Edge = Probabilidad del modelo − Probabilidad implícita de la cuota (1 / cuota), en
          puntos porcentuales. Ej: modelo 45%, cuota 3.00 (33% implícito) → Edge = +12 pp.{" "}
          <br />
          EV = (Probabilidad del modelo × cuota) − 1, la ganancia esperada proporcional por unidad
          apostada. Con los mismos números: EV = (0,45 × 3,00) − 1 = +35%.{" "}
          <br />
          <strong>Stake sugerido</strong>: cuánto apostar según Criterio de Kelly fraccional, para
          no arriesgar de más incluso si el modelo se equivoca.
        </p>
        <p>
          Esto <strong>no apuesta por vos</strong>. Si te interesa una recomendación, la apostás
          vos mismo donde prefieras y apretás <em>Aceptar</em> en la tabla de abajo — o{" "}
          <em>Descartar</em> si no te convence. Una vez jugado el partido, marcás{" "}
          <em>Ganó</em> o <em>Perdió</em> y ahí se calcula el PNL real y aparece en el gráfico.
        </p>
      </InfoBox>

      {loading && <p className="page-status">Cargando...</p>}
      {error && <p className="page-status page-status--error">Error: {error}</p>}

      {!loading && !error && (
        <>
          <h2 className="recomendaciones-page__seccion">
            Rendimiento del usuario (solo lo que aceptaste, plata real)
          </h2>
          <div className="dashboard__stats">
            <StatTile label="Bankroll de referencia" value={formatCurrency(config?.paper_bankroll)} />
            <StatTile
              label="PNL total"
              value={formatCurrency(resumen?.pnl_total)}
              tone={Number(resumen?.pnl_total) >= 0 ? "good" : "critical"}
            />
            <StatTile label="Recomendaciones" value={resumen?.total_operaciones ?? 0} />
            <StatTile
              label="Win rate"
              value={resumen?.win_rate != null ? formatPercent(resumen.win_rate) : "-"}
              dim={resumen ? !resumen.muestra_suficiente : false}
              hint={
                resumen && !resumen.muestra_suficiente
                  ? `⚠️ Muestra: ${resumen.finalizadas}/${resumen.minimo_requerido} -- rendimiento no concluyente todavía`
                  : undefined
              }
            />
            <StatTile label="VALUE BET (histórico)" value={contadorValueBet ?? "-"} />
            <StatTile label="NO BET (histórico)" value={contadorNoBet ?? "-"} />
          </div>

          <Card title="PNL acumulado (de las que aceptaste y ya se jugaron)">
            <PnlLineChart points={pnlPoints} />
          </Card>

          <RendimientoValueBets />

          <RendimientoModelo />

          <RendimientoBacktest />

          <RendimientoPorMercado />

          <InfoBox title="Data Quality, Confianza y Value Score">
            <p>
              Cada análisis (haya o no recomendación) queda registrado con tres puntajes: cuánto
              historial real respalda el rating de ambos equipos (<strong>Calidad</strong>), qué
              tan poco depende ese rating del promedio genérico de la liga (
              <strong>Confianza</strong>), y qué tan fuerte es la oportunidad combinando valor
              esperado y confianza (<strong>Valor</strong>). Cuando la calidad o la confianza son
              muy bajas, el sistema prefiere decir <strong>NO BET</strong> en vez de forzar una
              recomendación poco sólida.
            </p>
          </InfoBox>

          <Card title="Análisis de partidos pendientes (solo la versión vigente de cada mercado)">
            <AnalysisTable analisis={analisisVigente} />
          </Card>

          <Card
            title="Recomendaciones aceptadas/descartadas"
            action={
              <div className="pagination">
                <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                  Anterior
                </button>
                <span>
                  Página {page} de {totalPages}
                </span>
                <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                  Siguiente
                </button>
              </div>
            }
          >
            <div className="historial-filtros">
              <select value={filtroMercado} onChange={cambiarFiltro(setFiltroMercado)}>
                <option value="">Todos los mercados</option>
                {MERCADOS_FILTRO.map((m) => (
                  <option key={m} value={m}>
                    {labelMercado(m)}
                  </option>
                ))}
              </select>
              <select value={filtroEstado} onChange={cambiarFiltro(setFiltroEstado)}>
                <option value="">Todos los estados</option>
                {Object.entries(ESTADO_OPERACION_CONFIG).map(([valor, cfg]) => (
                  <option key={valor} value={valor}>
                    {cfg.label}
                  </option>
                ))}
              </select>
              <select value={filtroTemporada} onChange={cambiarFiltro(setFiltroTemporada)}>
                <option value="">Todas las temporadas</option>
                {TEMPORADAS_FILTRO.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              {(filtroMercado || filtroEstado || filtroTemporada) && (
                <button
                  type="button"
                  className="historial-filtros__limpiar"
                  onClick={() => {
                    setPage(1);
                    setFiltroMercado("");
                    setFiltroEstado("");
                    setFiltroTemporada("");
                  }}
                >
                  Limpiar filtros
                </button>
              )}
            </div>
            <OperationsTable operaciones={operaciones} onCambiarOperacion={handleCambiarOperacion} />
          </Card>
        </>
      )}
    </div>
  );
}
