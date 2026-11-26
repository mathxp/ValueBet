import { useEffect, useState } from "react";

import Card from "../components/Card";
import InfoBox from "../components/InfoBox";
import { actualizarConfiguracionRiesgo, getConfiguracion } from "../services/api";
import { formatCurrency, formatPercent } from "../utils/format";

const CAMPOS_RIESGO = [
  { key: "paper_bankroll", label: "Bankroll de referencia", tipo: "monto" },
  { key: "kelly_fraction", label: "Fracción de Kelly", tipo: "porcentaje" },
  { key: "max_stake_per_bet", label: "Stake máximo sugerido", tipo: "monto" },
  { key: "min_edge_threshold", label: "Edge mínimo para recomendar", tipo: "porcentaje" },
  { key: "probabilidad_minima_seleccion", label: "Probabilidad mínima para recomendar sola", tipo: "porcentaje" },
];

function aFormulario(config) {
  return {
    paper_bankroll: String(config.paper_bankroll),
    kelly_fraction: String(Number(config.kelly_fraction) * 100),
    max_stake_per_bet: String(config.max_stake_per_bet),
    min_edge_threshold: String(Number(config.min_edge_threshold) * 100),
    probabilidad_minima_seleccion: String(Number(config.probabilidad_minima_seleccion) * 100),
  };
}

export default function Configuracion() {
  const [config, setConfig] = useState(null);
  const [error, setError] = useState(null);
  const [editando, setEditando] = useState(false);
  const [form, setForm] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [errorGuardado, setErrorGuardado] = useState(null);

  useEffect(() => {
    getConfiguracion()
      .then(setConfig)
      .catch((err) => setError(err.message));
  }, []);

  if (error) return <p className="page-status page-status--error">Error: {error}</p>;
  if (!config) return <p className="page-status">Cargando...</p>;

  const iniciarEdicion = () => {
    setForm(aFormulario(config));
    setErrorGuardado(null);
    setEditando(true);
  };

  const cancelar = () => {
    setEditando(false);
    setErrorGuardado(null);
  };

  const guardar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setErrorGuardado(null);
    try {
      const cambios = {
        paper_bankroll: Number(form.paper_bankroll),
        kelly_fraction: Number(form.kelly_fraction) / 100,
        max_stake_per_bet: Number(form.max_stake_per_bet),
        min_edge_threshold: Number(form.min_edge_threshold) / 100,
        probabilidad_minima_seleccion: Number(form.probabilidad_minima_seleccion) / 100,
      };
      const actualizada = await actualizarConfiguracionRiesgo(cambios);
      setConfig(actualizada);
      setEditando(false);
    } catch (err) {
      const detalle = err.response?.data;
      const primerError = detalle && Object.values(detalle).flat()[0];
      setErrorGuardado(primerError || "No se pudo guardar. Revisá los valores.");
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="config-page">
      <header className="page-header">
        <h1>Configuración</h1>
        <p className="page-header__subtitle">Estado de las fuentes de datos y parámetros del sistema.</p>
      </header>

      <Card title="Fuentes de datos">
        <dl className="config-list">
          <div>
            <dt>Liga(s) monitoreada(s)</dt>
            <dd>
              {config.watched_leagues.length === 0
                ? "Ninguna configurada"
                : config.watched_leagues.map((id) => `#${id}`).join(", ")}
            </dd>
          </div>
          <div>
            <dt>api-football.com</dt>
            <dd>{config.api_football_configurado ? "Configurada" : "Sin configurar"}</dd>
          </div>
        </dl>
        <p className="config-hint">
          Se ajusta con la variable <code>WATCHED_LEAGUES</code> en <code>backend/.env</code>.
        </p>
      </Card>

      <InfoBox title="Sobre las recomendaciones">
        <p>
          Los parámetros de abajo (Kelly, stake máximo, edge mínimo, probabilidad mínima) solo
          afectan a las recomendaciones de la pestaña <strong>Predicciones</strong> — no tienen
          efecto sobre las predicciones de goles esperados, que se calculan aparte con el historial real de
          partidos. La <strong>probabilidad mínima</strong> es la única que no mide rentabilidad:
          filtra selecciones que tienen valor pero perderían la mayoría de las veces (ej. un
          equipo con 30% de probabilidad de ganar), para no recomendarlas solas aunque a la larga
          serían rentables. Si el mismo partido tiene una versión más segura de la misma señal
          (ej. Doble Oportunidad en vez de 1X2 a secas), esa se sigue recomendando igual.
        </p>
      </InfoBox>

      <Card
        title="Gestión de riesgo (Kelly fraccional)"
        action={
          !editando && (
            <button type="button" className="config-form__editar" onClick={iniciarEdicion}>
              Editar
            </button>
          )
        }
      >
        {editando ? (
          <form className="config-form" onSubmit={guardar}>
            {CAMPOS_RIESGO.map(({ key, label, tipo }) => (
              <label key={key} className="config-form__campo">
                <span>
                  {label} {tipo === "porcentaje" ? "(%)" : "(CLP)"}
                </span>
                <input
                  type="number"
                  step="any"
                  min="0"
                  value={form[key]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                  required
                />
              </label>
            ))}
            {errorGuardado && <p className="config-form__error">{errorGuardado}</p>}
            <div className="config-form__acciones">
              <button type="submit" disabled={guardando}>
                {guardando ? "Guardando..." : "Guardar"}
              </button>
              <button type="button" onClick={cancelar} disabled={guardando}>
                Cancelar
              </button>
            </div>
          </form>
        ) : (
          <dl className="config-list">
            <div>
              <dt>Bankroll de referencia</dt>
              <dd>{formatCurrency(config.paper_bankroll)}</dd>
            </div>
            <div>
              <dt>Fracción de Kelly</dt>
              <dd>{formatPercent(config.kelly_fraction)}</dd>
            </div>
            <div>
              <dt>Stake máximo sugerido</dt>
              <dd>{formatCurrency(config.max_stake_per_bet)}</dd>
            </div>
            <div>
              <dt>Edge mínimo para recomendar</dt>
              <dd>{formatPercent(config.min_edge_threshold)}</dd>
            </div>
            <div>
              <dt>Probabilidad mínima para recomendar sola</dt>
              <dd>{formatPercent(config.probabilidad_minima_seleccion)}</dd>
            </div>
            <div>
              <dt>Exchange conectado</dt>
              <dd>{config.betfair_configurado ? "Betfair" : "Ninguno (solo cuotas de referencia)"}</dd>
            </div>
          </dl>
        )}
        <p className="config-hint">
          Un cambio acá aplica en el próximo escaneo (cada 30s) -- no hace falta reiniciar nada.
          Actualizá <strong>Bankroll de referencia</strong> cuando cambie tu saldo real en la
          casa/exchange.
        </p>
      </Card>
    </div>
  );
}
