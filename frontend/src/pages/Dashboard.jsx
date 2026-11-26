import { useEffect, useMemo, useState } from "react";

import Card from "../components/Card";
import OperationsTable from "../components/OperationsTable";
import PnlLineChart from "../components/PnlLineChart";
import RendimientoModelo from "../components/RendimientoModelo";
import StatTile from "../components/StatTile";
import { getConfiguracion, getOperaciones, getResumenOperaciones } from "../services/api";
import { ESTADO_OPERACION_CONFIG, formatCurrency, formatPercent } from "../utils/format";

const PAGE_SIZE = 25;

// Sin filtro explícito se ocultan las descartadas: el historial muestra solo
// lo que se jugó o está pendiente.
const ESTADOS_VISIBLES_POR_DEFECTO = Object.keys(ESTADO_OPERACION_CONFIG).filter((e) => e !== "DISCARDED");

export default function Dashboard() {
  const [resumen, setResumen] = useState(null);
  const [config, setConfig] = useState(null);
  const [operaciones, setOperaciones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [historial, setHistorial] = useState([]);
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [loadingHistorial, setLoadingHistorial] = useState(true);
  const [filtroEstado, setFiltroEstado] = useState("");

  useEffect(() => {
    Promise.all([getResumenOperaciones(), getConfiguracion(), getOperaciones({ page: 1 })])
      .then(([resumenData, configData, operacionesData]) => {
        setResumen(resumenData);
        setConfig(configData);
        setOperaciones(operacionesData.results ?? operacionesData);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    setLoadingHistorial(true);
    const filtros = filtroEstado ? { estado: filtroEstado } : { estado__in: ESTADOS_VISIBLES_POR_DEFECTO.join(",") };
    getOperaciones({ page, ...filtros })
      .then((data) => {
        setHistorial(data.results ?? data);
        setCount(data.count ?? (data.results ?? data).length);
      })
      .catch(() => setHistorial([]))
      .finally(() => setLoadingHistorial(false));
  }, [page, filtroEstado]);

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
        <p className="page-header__subtitle">Cómo te ha ido con las recomendaciones.</p>
      </header>

      <div className="dashboard__stats">
        <StatTile
          label="Ganancia total"
          value={formatCurrency(resumen?.pnl_total)}
          tone={Number(resumen?.pnl_total) >= 0 ? "good" : "critical"}
        />
        <StatTile
          label="Aciertos"
          value={resumen?.win_rate != null ? formatPercent(resumen.win_rate) : "-"}
          dim={resumen ? !resumen.muestra_suficiente : false}
          hint={
            resumen && !resumen.muestra_suficiente
              ? `Muestra chica: ${resumen.finalizadas} de ${resumen.minimo_requerido} jugadas`
              : undefined
          }
        />
        <StatTile label="Recomendaciones" value={resumen?.total_operaciones ?? 0} />
        <StatTile label="Bankroll" value={formatCurrency(config?.paper_bankroll)} />
      </div>

      <Card title="Ganancia acumulada">
        <PnlLineChart points={pnlPoints} />
      </Card>

      <RendimientoModelo />

      <Card
        title="Historial"
        action={
          <select
            className="dashboard__filtro"
            value={filtroEstado}
            onChange={(e) => {
              setPage(1);
              setFiltroEstado(e.target.value);
            }}
          >
            <option value="">Todas</option>
            {Object.entries(ESTADO_OPERACION_CONFIG).map(([valor, cfg]) => (
              <option key={valor} value={valor}>
                {cfg.label}
              </option>
            ))}
          </select>
        }
      >
        {loadingHistorial ? (
          <p className="page-status">Cargando...</p>
        ) : (
          <OperationsTable operaciones={historial} onCambiarOperacion={handleCambiarOperacion} />
        )}
        {totalPages > 1 && (
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
        )}
      </Card>
    </div>
  );
}
