import { useEffect, useMemo, useState } from "react";

import Card from "../components/Card";
import { AccionesOperacion } from "../components/OperationsTable";
import PartidoCell from "../components/PartidoCell";
import PnlLineChart from "../components/PnlLineChart";
import StatTile from "../components/StatTile";
import StatusBadge from "../components/StatusBadge";
import { getOperaciones, getResumenOperaciones } from "../services/api";
import { formatCurrency, formatOdds, formatPercent, formatSeleccion } from "../utils/format";
import "./Dashboard.css";

function ListaApuestas({ operaciones, onCambiar, mostrarPnl }) {
  return (
    <ul className="bet-list">
      {operaciones.map((op) => (
        <li key={op.id} className="bet-list__item">
          <PartidoCell partido={op.partido} />
          <div className="bet-list__pick">
            <span className="bet-list__seleccion">{formatSeleccion(op.mercado, op.seleccion)}</span>
            <span className="bet-list__cuota">@ {formatOdds(op.cuota_apostada)}</span>
          </div>
          {mostrarPnl ? (
            <span className={`bet-list__pnl ${Number(op.pnl) >= 0 ? "is-positive" : "is-negative"}`}>
              {op.pnl != null ? formatCurrency(op.pnl) : "-"}
            </span>
          ) : (
            <span className="bet-list__stake">{formatCurrency(op.stake)}</span>
          )}
          <StatusBadge estado={op.estado} />
          <AccionesOperacion operacion={op} onCambiar={onCambiar} />
        </li>
      ))}
    </ul>
  );
}

export default function Dashboard() {
  const [resumen, setResumen] = useState(null);
  const [pendientes, setPendientes] = useState([]);
  const [resueltas, setResueltas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const cargar = () =>
    Promise.all([
      getResumenOperaciones(),
      getOperaciones({ estado__in: "RECOMMENDED,ACCEPTED" }),
      getOperaciones({ estado__in: "WON,LOST,VOID" }),
    ])
      .then(([r, p, s]) => {
        setResumen(r);
        setPendientes(p.results ?? p);
        setResueltas(s.results ?? s);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));

  useEffect(() => {
    cargar();
  }, []);

  const pnlPoints = useMemo(() => {
    let acumulado = 0;
    return [...resueltas]
      .reverse()
      .map((op) => {
        acumulado += Number(op.pnl ?? 0);
        return { label: op.creado_en, value: acumulado };
      });
  }, [resueltas]);

  if (loading) return <p className="page-status">Cargando...</p>;
  if (error) return <p className="page-status page-status--error">Error: {error}</p>;

  const pnl = Number(resumen?.pnl_total ?? 0);

  return (
    <div className="dashboard-page">
      <header className="page-header">
        <h1>Dashboard</h1>
        <p className="page-header__subtitle">Cómo te va con tus apuestas.</p>
      </header>

      <div className="dashboard__stats dashboard__stats--3">
        <StatTile label="Ganancia" value={formatCurrency(pnl)} tone={pnl >= 0 ? "good" : "critical"} />
        <StatTile
          label="Aciertos"
          value={resumen?.win_rate != null ? formatPercent(resumen.win_rate) : "-"}
          hint={resumen?.finalizadas ? `${resumen.finalizadas} apuestas jugadas` : undefined}
        />
        <StatTile label="Por resolver" value={pendientes.length} />
      </div>

      <Card title="Ganancia acumulada">
        <PnlLineChart points={pnlPoints} />
      </Card>

      {pendientes.length > 0 && (
        <Card title="Por resolver">
          <ListaApuestas operaciones={pendientes} onCambiar={cargar} />
        </Card>
      )}

      <Card title="Últimos resultados">
        {resueltas.length === 0 ? (
          <p className="page-status">Todavía no hay apuestas resueltas.</p>
        ) : (
          <ListaApuestas operaciones={resueltas.slice(0, 10)} onCambiar={cargar} mostrarPnl />
        )}
      </Card>
    </div>
  );
}
