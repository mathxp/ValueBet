import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import Card from "../components/Card";
import { AccionesOperacion } from "../components/OperationsTable";
import PartidoCell from "../components/PartidoCell";
import PnlLineChart from "../components/PnlLineChart";
import StatusBadge from "../components/StatusBadge";
import TeamCrest from "../components/TeamCrest";
import { getBacktest, getOperaciones, getPronosticos, getResumenOperaciones } from "../services/api";
import { etiquetaPronostico, formatCurrency, formatOdds, formatPercent, formatSeleccion } from "../utils/format";
import "./Dashboard.css";

const ICONO_RACHA = { WON: "G", LOST: "P", VOID: "A" };

function Resumen({ resumen, pendientes }) {
  const pnl = Number(resumen?.pnl_total ?? 0);
  const marca = resumen?.marca ?? { ganadas: 0, perdidas: 0, anuladas: 0 };
  return (
    <section className={`dash-hero ${pnl >= 0 ? "dash-hero--positivo" : "dash-hero--negativo"}`}>
      <div className="dash-hero__principal">
        <span className="dash-hero__label">Ganancia total</span>
        <span className="dash-hero__valor">{formatCurrency(pnl)}</span>
        {resumen?.roi != null && (
          <span className="dash-hero__roi">
            {resumen.roi >= 0 ? "▲" : "▼"} {formatPercent(resumen.roi)} de retorno sobre {formatCurrency(resumen.apostado)} apostados
          </span>
        )}
      </div>

      <div className="dash-hero__stats">
        <div>
          <span className="dash-hero__stat">{resumen?.win_rate != null ? formatPercent(resumen.win_rate) : "–"}</span>
          <span className="dash-hero__stat-label">aciertos</span>
        </div>
        <div>
          <span className="dash-hero__stat">
            {marca.ganadas}-{marca.perdidas}
            {marca.anuladas ? `-${marca.anuladas}` : ""}
          </span>
          <span className="dash-hero__stat-label" title="Ganadas - Perdidas - Anuladas">
            marca G-P{marca.anuladas ? "-A" : ""}
          </span>
        </div>
        <div>
          <span className="dash-hero__stat">{pendientes}</span>
          <span className="dash-hero__stat-label">por resolver</span>
        </div>
      </div>

      {resumen?.racha?.length > 0 && (
        <div className="dash-hero__racha" aria-label="Últimos resultados">
          <span className="dash-hero__stat-label">Últimas {resumen.racha.length}</span>
          <div className="dash-racha">
            {resumen.racha.map((estado, i) => (
              <span key={i} className={`dash-racha__punto dash-racha__punto--${estado}`} title={estado}>
                {ICONO_RACHA[estado] ?? "·"}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function MejoresDeLaFecha({ pronosticos }) {
  const top = [...pronosticos]
    .sort((a, b) => b.doble_oportunidad.probabilidad - a.doble_oportunidad.probabilidad)
    .slice(0, 3);
  if (!top.length) return null;
  return (
    <Card title="Lo mejor de la próxima fecha" action={<Link className="dash-link" to="/">Ver todo →</Link>}>
      <ul className="dash-top">
        {top.map((x, i) => (
          <li key={x.partido.id} className="dash-top__item">
            <span className="dash-top__rank">{i + 1}</span>
            <div className="dash-top__escudos">
              <TeamCrest equipo={x.partido.equipo_local} className="dash-top__escudo" />
              <TeamCrest equipo={x.partido.equipo_visitante} className="dash-top__escudo" />
            </div>
            <div className="dash-top__texto">
              <strong>{etiquetaPronostico(x.doble_oportunidad, x.partido)}</strong>
              <span>
                {x.partido.equipo_local.nombre} vs {x.partido.equipo_visitante.nombre}
              </span>
            </div>
            <span className="dash-top__prob">{formatPercent(x.doble_oportunidad.probabilidad)}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Confiabilidad({ backtest }) {
  const m = backtest?.mercados?.find((x) => x.mercado === "1X2");
  if (!m) return null;
  return (
    <Card title="¿Qué tan confiable es el modelo?">
      <p className="dash-conf__intro">
        Probado contra <strong>{m.n.toLocaleString("es-CL")}</strong> partidos reales de la liga, prediciendo cada uno
        solo con lo que se sabía antes de jugarse.
      </p>
      <div className="dash-conf__kpis">
        <div>
          <span className="dash-conf__kpi">{formatPercent(m.accuracy)}</span>
          <span className="dash-conf__kpi-label">acierta el resultado</span>
        </div>
        <div>
          <span className="dash-conf__kpi dash-conf__kpi--muted">{formatPercent(m.accuracy_baseline)}</span>
          <span className="dash-conf__kpi-label">si apostaras siempre al local</span>
        </div>
      </div>
      <p className="dash-conf__sub">Cuando el modelo dice…</p>
      <ul className="dash-conf__buckets">
        {m.buckets.map((b) => (
          <li key={b.rango}>
            <span className="dash-conf__rango">{b.rango}</span>
            <div className="dash-conf__barras">
              <span className="dash-conf__barra dash-conf__barra--pred" style={{ width: `${b.predicho * 100}%` }} />
              <span className="dash-conf__barra dash-conf__barra--real" style={{ width: `${b.real * 100}%` }} />
            </div>
            <span className="dash-conf__real">
              pasó <strong>{formatPercent(b.real)}</strong>
            </span>
          </li>
        ))}
      </ul>
      <div className="dash-conf__leyenda">
        <span>
          <i className="dash-conf__dot dash-conf__dot--pred" /> Predicho
        </span>
        <span>
          <i className="dash-conf__dot dash-conf__dot--real" /> Ocurrió de verdad
        </span>
      </div>
    </Card>
  );
}

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
  const [pronosticos, setPronosticos] = useState([]);
  const [backtest, setBacktest] = useState(null);
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
    getPronosticos().then(setPronosticos).catch(() => setPronosticos([]));
    getBacktest().then(setBacktest).catch(() => setBacktest(null));
  }, []);

  const pnlPoints = useMemo(() => {
    let acumulado = 0;
    const puntos = [...resueltas].reverse().map((op) => {
      acumulado += Number(op.pnl ?? 0);
      return { label: op.creado_en, value: acumulado };
    });
    return puntos.length ? [{ label: puntos[0].label, value: 0 }, ...puntos] : puntos;
  }, [resueltas]);

  if (loading) return <p className="page-status">Cargando...</p>;
  if (error) return <p className="page-status page-status--error">Error: {error}</p>;

  return (
    <div className="dashboard-page">
      <header className="page-header">
        <h1>Dashboard</h1>
        <p className="page-header__subtitle">Cómo te va y qué viene.</p>
      </header>

      <Resumen resumen={resumen} pendientes={pendientes.length} />

      <div className="dash-grid">
        <Card title="Ganancia acumulada">
          <PnlLineChart points={pnlPoints} />
        </Card>
        <MejoresDeLaFecha pronosticos={pronosticos} />
      </div>

      {pendientes.length > 0 && (
        <Card title="Por resolver">
          <ListaApuestas operaciones={pendientes} onCambiar={cargar} />
        </Card>
      )}

      <div className="dash-grid">
        <Card title="Últimos resultados">
          {resueltas.length === 0 ? (
            <p className="page-status">Todavía no hay apuestas resueltas.</p>
          ) : (
            <ListaApuestas operaciones={resueltas.slice(0, 8)} onCambiar={cargar} mostrarPnl />
          )}
        </Card>
        <Confiabilidad backtest={backtest} />
      </div>
    </div>
  );
}
