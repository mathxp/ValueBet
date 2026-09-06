import { useEffect, useState } from "react";

import Card from "../components/Card";
import InfoBox from "../components/InfoBox";
import api from "../services/api";
import { formatCurrency, formatPercent } from "../utils/format";

export default function Configuracion() {
  const [config, setConfig] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .get("config/")
      .then((r) => setConfig(r.data))
      .catch((err) => setError(err.message));
  }, []);

  if (error) return <p className="page-status page-status--error">Error: {error}</p>;
  if (!config) return <p className="page-status">Cargando...</p>;

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

      <InfoBox title="Sobre la sección de Recomendaciones">
        <p>
          Los parámetros de abajo (Kelly, stake máximo, edge mínimo) solo afectan a la pestaña{" "}
          <strong>Recomendaciones</strong> — no tienen efecto sobre las predicciones de goles
          esperados, que se calculan aparte con el historial real de partidos.
        </p>
      </InfoBox>

      <Card title="Gestión de riesgo (Kelly fraccional)">
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
            <dt>Exchange conectado</dt>
            <dd>{config.betfair_configurado ? "Betfair" : "Ninguno (solo cuotas de referencia)"}</dd>
          </div>
        </dl>
        <p className="config-hint">
          Se ajustan con variables de entorno (<code>PAPER_BANKROLL</code>,{" "}
          <code>KELLY_FRACTION</code>, <code>MAX_STAKE_PER_BET</code>,{" "}
          <code>MIN_EDGE_THRESHOLD</code>) en <code>backend/.env</code> — actualizá{" "}
          <code>PAPER_BANKROLL</code> cuando cambie tu saldo real, no son editables desde acá
          todavía.
        </p>
      </Card>
    </div>
  );
}
