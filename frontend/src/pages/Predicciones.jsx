import { useEffect, useMemo, useState } from "react";

import Card from "../components/Card";
import CombinadasList from "../components/CombinadasList";
import MejorApuestaCard from "../components/MejorApuestaCard";
import PartidoCell from "../components/PartidoCell";
import PronosticoCard from "../components/PronosticoCard";
import TeamCrest from "../components/TeamCrest";
import { getAnalisis, getCombinadas, getPronosticos } from "../services/api";
import { etiquetaPronostico, formatMercado, formatOdds, formatPercent, formatSeleccion } from "../utils/format";

// Igual que LINEAS_OVER_UNDER_VALIDAS en el backend -- un mercado retirado
// (ej. la línea 4.5) no debe poder "ganar" el puesto de mejor apuesta con un
// análisis viejo que ya no se evalúa más.
const MERCADOS_VIGENTES = new Set([
  "1X2",
  "DOBLE_OPORTUNIDAD",
  "OVER_UNDER_0.5",
  "OVER_UNDER_1.5",
  "OVER_UNDER_2.5",
  "OVER_UNDER_3.5",
]);

// Piso de probabilidad para que una recomendación se destaque como "la mejor
// apuesta de la fecha" -- más exigente que PROBABILIDAD_MINIMA_SELECCION del
// backend (que solo exige no perder la mayoría de las veces, ver
// Configuración). Acá el objetivo es otro: no "tiene valor", sino "es una
// apuesta segura" -- more likely than not por un margen claro, no un
// cincuenta y pico que técnicamente pasa el filtro general.
const PROBABILIDAD_MINIMA_DESTACADA = 0.6;

export default function Predicciones() {
  const [pronosticos, setPronosticos] = useState([]);
  const [loadingPron, setLoadingPron] = useState(true);
  const [errorPron, setErrorPron] = useState(null);

  const [analisis, setAnalisis] = useState([]);
  const [combinadas, setCombinadas] = useState([]);
  const [loadingRecom, setLoadingRecom] = useState(true);

  useEffect(() => {
    getPronosticos()
      .then(setPronosticos)
      .catch((err) => setErrorPron(err.message))
      .finally(() => setLoadingPron(false));

    // Solo las que tienen valor -- el detalle completo (incluidos los NO BET,
    // para auditar el modelo) y el historial de aceptadas/descartadas viven
    // en Dashboard. Acá la idea es entrar y saber altiro a quién apostarle,
    // no revisar cada mercado que se evaluó.
    getAnalisis({ partido__fecha_hora__gte: new Date().toISOString(), recomendacion: "VALUE_BET" })
      .then((data) => setAnalisis(data.results ?? data))
      .catch(() => setAnalisis([]))
      .finally(() => setLoadingRecom(false));

    getCombinadas({ estado: "RECOMMENDED" })
      .then((d) => setCombinadas(d.results ?? d))
      .catch(() => setCombinadas([]));
  }, []);

  const handleCambiarCombinada = (actualizada) => {
    setCombinadas((actuales) => actuales.filter((c) => c.id !== actualizada.id));
  };

  // Mismo dedupe que antes: si un partido se escaneó varias veces, solo
  // cuenta la versión más reciente de cada mercado.
  const analisisVigente = useMemo(() => {
    const masReciente = new Map();
    for (const a of analisis) {
      if (!MERCADOS_VIGENTES.has(a.mercado)) continue;
      const clave = `${a.partido?.id}|${a.mercado}`;
      const actual = masReciente.get(clave);
      if (!actual || new Date(a.fecha_analisis) > new Date(actual.fecha_analisis)) {
        masReciente.set(clave, a);
      }
    }
    return Array.from(masReciente.values());
  }, [analisis]);

  // La única apuesta que se destaca arriba de todo -- entre las VALUE_BET con
  // probabilidad alta (no cualquiera con valor), la de mejor value_score (EV +
  // calibración + calidad + confianza + estabilidad combinados, ver
  // ml_models/pipelines/quality.py). Prioriza acertar por sobre EV puro.
  const mejorApuesta = useMemo(() => {
    const candidatas = analisisVigente.filter((a) => a.probabilidad_seleccion >= PROBABILIDAD_MINIMA_DESTACADA);
    if (candidatas.length === 0) return null;
    return candidatas.reduce((mejor, actual) => (actual.value_score > mejor.value_score ? actual : mejor));
  }, [analisisVigente]);

  // El resto de las recomendaciones con valor, sin repetir la que ya se
  // destacó arriba -- ordenadas por probabilidad, mismo criterio que la
  // mejor apuesta (tratar de acertar, no perseguir el EV más alto).
  const otrasRecomendaciones = useMemo(() => {
    return analisisVigente
      .filter((a) => a.id !== mejorApuesta?.id)
      .sort((a, b) => b.probabilidad_seleccion - a.probabilidad_seleccion);
  }, [analisisVigente, mejorApuesta]);

  // Los 3 pronósticos más probables de la fecha ("X gana o empata").
  const masSeguros = useMemo(
    () =>
      [...pronosticos]
        .sort((a, b) => b.doble_oportunidad.probabilidad - a.doble_oportunidad.probabilidad)
        .slice(0, 3),
    [pronosticos]
  );

  return (
    <div className="predicciones-page">
      <header className="page-header">
        <h1>Predicciones</h1>
        <p className="page-header__subtitle">
          Lo más probable de cada partido de la próxima fecha, según el modelo.
        </p>
      </header>

      {loadingPron && <p className="page-status">Cargando...</p>}
      {errorPron && <p className="page-status page-status--error">Error: {errorPron}</p>}

      {masSeguros.length > 0 && (
        <section>
          <h2 className="seccion-titulo">🔒 Los más seguros de la fecha</h2>
          <div className="pron-top">
            {masSeguros.map((x, i) => (
              <div key={x.partido.id} className="pron-top__item">
                <span className="pron-top__rank">#{i + 1} más probable</span>
                <div className="pron-top__partido">
                  <TeamCrest equipo={x.partido.equipo_local} />
                  <span>{x.partido.equipo_local.nombre}</span>
                  <span>vs</span>
                  <span>{x.partido.equipo_visitante.nombre}</span>
                  <TeamCrest equipo={x.partido.equipo_visitante} />
                </div>
                <span className="pron-top__pick">{etiquetaPronostico(x.doble_oportunidad, x.partido)}</span>
                <span className="pron-top__prob">{formatPercent(x.doble_oportunidad.probabilidad)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {!loadingRecom && mejorApuesta && <MejorApuestaCard analisis={mejorApuesta} />}

      {!loadingPron && !errorPron && (
        <section>
          <h2 className="seccion-titulo">Todos los partidos</h2>
          {pronosticos.length === 0 ? (
            <p className="page-status">No hay partidos próximos con pronóstico todavía.</p>
          ) : (
            <div className="pron-grid">
              {pronosticos.map((x) => (
                <PronosticoCard key={x.partido.id} pronostico={x} />
              ))}
            </div>
          )}
          <p className="pron-nota">
            Probabilidades calibradas con los resultados reales de temporadas anteriores. Son
            estimaciones, no certezas: el fútbol siempre tiene sorpresas.
          </p>
        </section>
      )}

      {!loadingRecom && otrasRecomendaciones.length > 0 && (
        <Card title="Apuestas con valor (cuota mejor que la probabilidad real)">
          <div className="recom-simple-list">
            {otrasRecomendaciones.map((a) => (
              <div key={a.id} className="recom-simple-item">
                <PartidoCell partido={a.partido} />
                <div className="recom-simple-item__pick">
                  <span className="recom-simple-item__seleccion">
                    {formatSeleccion(a.mercado, a.seleccion_evaluada)}
                  </span>
                  <span className="recom-simple-item__mercado">{formatMercado(a.mercado)}</span>
                </div>
                <div className="recom-simple-item__numeros">
                  <span>{formatPercent(a.probabilidad_seleccion)}</span>
                  <span>{formatOdds(a.cuota_mercado)}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {!loadingRecom && combinadas.length > 0 && (
        <Card title="Combinadas sugeridas">
          <CombinadasList combinadas={combinadas} onCambiarCombinada={handleCambiarCombinada} />
        </Card>
      )}
    </div>
  );
}
