import { useEffect, useMemo, useState } from "react";

import AnalysisTable from "../components/AnalysisTable";
import Card from "../components/Card";
import InfoBox from "../components/InfoBox";
import OperationsTable from "../components/OperationsTable";
import PnlLineChart from "../components/PnlLineChart";
import RendimientoModelo from "../components/RendimientoModelo";
import StatTile from "../components/StatTile";
import { getAnalisis, getOperaciones, getResumenOperaciones } from "../services/api";
import { formatCurrency, formatPercent } from "../utils/format";

const PAGE_SIZE = 25;

export default function Recomendaciones() {
  const [resumen, setResumen] = useState(null);
  const [operaciones, setOperaciones] = useState([]);
  const [analisis, setAnalisis] = useState([]);
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([getResumenOperaciones(), getOperaciones({ page }), getAnalisis()])
      .then(([resumenData, operacionesData, analisisData]) => {
        setResumen(resumenData);
        setOperaciones(operacionesData.results ?? operacionesData);
        setCount(operacionesData.count ?? (operacionesData.results ?? operacionesData).length);
        setAnalisis(analisisData.results ?? analisisData);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [page]);

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
          <strong>Edge</strong>: cuánta ventaja calcula el modelo que tiene esa apuesta sobre la
          cuota ofrecida (ej. 15% de edge = el modelo cree que vale más de lo que paga la casa).{" "}
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
          <div className="dashboard__stats">
            <StatTile
              label="PNL total"
              value={formatCurrency(resumen?.pnl_total)}
              tone={Number(resumen?.pnl_total) >= 0 ? "good" : "critical"}
            />
            <StatTile label="Recomendaciones" value={resumen?.total_operaciones ?? 0} />
            <StatTile
              label="Win rate"
              value={resumen?.win_rate != null ? formatPercent(resumen.win_rate) : "-"}
            />
          </div>

          <Card title="PNL acumulado (de las que aceptaste y ya se jugaron)">
            <PnlLineChart points={pnlPoints} />
          </Card>

          <RendimientoModelo />

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

          <Card title="Historial completo de análisis (incluye los NO BET)">
            <AnalysisTable analisis={analisis} />
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
            <OperationsTable operaciones={operaciones} onCambiarOperacion={handleCambiarOperacion} />
          </Card>
        </>
      )}
    </div>
  );
}
