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
import { getAnalisis, getConfiguracion, getOperaciones, getResumenOperaciones } from "../services/api";
import { ESTADO_OPERACION_CONFIG, formatCurrency, formatMercado, formatPercent } from "../utils/format";

const PAGE_SIZE = 25;

// Líneas históricas: 4.5 ya no se recomienda (ver LINEAS_OVER_UNDER_VALIDAS
// en el backend), pero sigue en el historial de análisis viejos.
const MERCADOS_FILTRO = [
  "1X2",
  "DOBLE_OPORTUNIDAD",
  "OVER_UNDER_0.5",
  "OVER_UNDER_1.5",
  "OVER_UNDER_2.5",
  "OVER_UNDER_3.5",
  "OVER_UNDER_4.5",
];
// Igual que LINEAS_OVER_UNDER_VALIDAS en el backend -- se usa para no
// mostrar en "partidos pendientes" un mercado que ya no se escanea (ej. 4.5),
// que si no quedaría congelado ahí para siempre con su último estado viejo.
const MERCADOS_VIGENTES = new Set([
  "1X2",
  "DOBLE_OPORTUNIDAD",
  "OVER_UNDER_0.5",
  "OVER_UNDER_1.5",
  "OVER_UNDER_2.5",
  "OVER_UNDER_3.5",
]);
const TEMPORADAS_FILTRO = ["2022", "2023", "2024", "2025", "2026"];

// Sin filtro de estado explícito se pide todo MENOS descartadas -- si no, el
// historial se ve desordenado con propuestas viejas que ya se dejaron pasar
// mezcladas con las vigentes/resueltas. El usuario igual puede elegir
// "Descartada" a mano en el filtro si quiere verlas.
const ESTADOS_VISIBLES_POR_DEFECTO = Object.keys(ESTADO_OPERACION_CONFIG).filter((e) => e !== "DISCARDED");

function labelMercado(mercado) {
  return mercado === "1X2" ? "Resultado (1X2)" : formatMercado(mercado);
}

export default function Dashboard() {
  const [resumen, setResumen] = useState(null);
  const [config, setConfig] = useState(null);
  const [contadorValueBet, setContadorValueBet] = useState(null);
  const [contadorNoBet, setContadorNoBet] = useState(null);
  const [operaciones, setOperaciones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [analisisPendiente, setAnalisisPendiente] = useState([]);
  const [historial, setHistorial] = useState([]);
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [loadingHistorial, setLoadingHistorial] = useState(true);
  const [filtroMercado, setFiltroMercado] = useState("");
  const [filtroEstado, setFiltroEstado] = useState("");
  const [filtroTemporada, setFiltroTemporada] = useState("");

  useEffect(() => {
    Promise.all([getResumenOperaciones(), getConfiguracion(), getOperaciones({ page: 1 })])
      .then(([resumenData, configData, operacionesData]) => {
        setResumen(resumenData);
        setConfig(configData);
        setOperaciones(operacionesData.results ?? operacionesData);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));

    getAnalisis({ recomendacion: "VALUE_BET" })
      .then((d) => setContadorValueBet(d.count))
      .catch(() => setContadorValueBet(null));
    getAnalisis({ recomendacion: "NO_BET" })
      .then((d) => setContadorNoBet(d.count))
      .catch(() => setContadorNoBet(null));

    // Análisis de partidos pendientes -- todos los mercados, no solo los que
    // tienen valor (eso ya se ve resumido en Predicciones). Acá es para
    // auditar el modelo, no para decidir a quién apostarle.
    getAnalisis({ partido__fecha_hora__gte: new Date().toISOString() })
      .then((d) => setAnalisisPendiente(d.results ?? d))
      .catch(() => setAnalisisPendiente([]));
  }, []);

  useEffect(() => {
    setLoadingHistorial(true);
    const filtros = {
      ...(filtroMercado && { mercado: filtroMercado }),
      ...(filtroTemporada && { partido__temporada: filtroTemporada }),
      ...(filtroEstado ? { estado: filtroEstado } : { estado__in: ESTADOS_VISIBLES_POR_DEFECTO.join(",") }),
    };
    getOperaciones({ page, ...filtros })
      .then((data) => {
        setHistorial(data.results ?? data);
        setCount(data.count ?? (data.results ?? data).length);
      })
      .catch(() => setHistorial([]))
      .finally(() => setLoadingHistorial(false));
  }, [page, filtroMercado, filtroEstado, filtroTemporada]);

  const cambiarFiltro = (setter) => (e) => {
    setPage(1);
    setter(e.target.value);
  };

  // Mismo dedupe de siempre: solo la versión más reciente de cada mercado
  // por partido, y solo mercados que todavía se evalúan en vivo.
  const analisisVigente = useMemo(() => {
    const masReciente = new Map();
    for (const a of analisisPendiente) {
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
  }, [analisisPendiente]);

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
    setHistorial((actuales) => actuales.map((op) => (op.id === actualizada.id ? actualizada : op)));
  };

  if (loading) return <p className="page-status">Cargando...</p>;
  if (error) return <p className="page-status page-status--error">Error: {error}</p>;

  return (
    <div className="dashboard-page">
      <header className="page-header">
        <h1>Dashboard</h1>
        <p className="page-header__subtitle">
          Rendimiento del sistema en el tiempo, análisis completo de cada mercado y tu historial
          de recomendaciones.
        </p>
      </header>

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
            <option value="">Todos (sin descartadas)</option>
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
        {loadingHistorial ? (
          <p className="page-status">Cargando...</p>
        ) : (
          <OperationsTable operaciones={historial} onCambiarOperacion={handleCambiarOperacion} />
        )}
      </Card>
    </div>
  );
}
