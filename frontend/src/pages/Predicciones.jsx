import { useEffect, useMemo, useState } from "react";

import Card from "../components/Card";
import CombinadasList from "../components/CombinadasList";
import InfoBox from "../components/InfoBox";
import MatchCard from "../components/MatchCard";
import MejorApuestaCard from "../components/MejorApuestaCard";
import PartidoCell from "../components/PartidoCell";
import { getAnalisis, getCombinadas, getPartidos, getPrediccion } from "../services/api";
import { formatMercado, formatOdds, formatPercent, formatSeleccion } from "../utils/format";

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
  const [partidos, setPartidos] = useState([]);
  const [predicciones, setPredicciones] = useState({});
  const [loadingPartidos, setLoadingPartidos] = useState(true);
  const [errorPartidos, setErrorPartidos] = useState(null);

  const [analisis, setAnalisis] = useState([]);
  const [combinadas, setCombinadas] = useState([]);
  const [loadingRecom, setLoadingRecom] = useState(true);

  useEffect(() => {
    getPartidos({ estado: "SCHEDULED" })
      .then((data) => {
        const lista = (data.results ?? data)
          .slice()
          .sort((a, b) => new Date(a.fecha_hora) - new Date(b.fecha_hora))
          .slice(0, 12);
        setPartidos(lista);

        return Promise.all(lista.map((p) => getPrediccion(p.id).then((pred) => [p.id, pred])));
      })
      .then((entradas) => setPredicciones(Object.fromEntries(entradas ?? [])))
      .catch((err) => setErrorPartidos(err.message))
      .finally(() => setLoadingPartidos(false));

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

  return (
    <div className="predicciones-page">
      <header className="page-header">
        <h1>Predicciones — Primera División de Chile</h1>
        <p className="page-header__subtitle">
          Entrá y sabé altiro a quién apostarle. Es apoyo para decidir, no ejecuta ninguna
          apuesta.
        </p>
      </header>

      {!loadingRecom && <MejorApuestaCard analisis={mejorApuesta} />}

      {!loadingRecom && otrasRecomendaciones.length > 0 && (
        <Card title="Otras recomendaciones de valor">
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
                  <span className={a.ev >= 0 ? "is-positive" : "is-negative"}>{formatPercent(a.ev)}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {!loadingRecom && combinadas.length > 0 && (
        <Card title="Combinadas sugeridas (máx. 3 patas)">
          <CombinadasList combinadas={combinadas} onCambiarCombinada={handleCambiarCombinada} />
        </Card>
      )}

      {loadingPartidos && <p className="page-status">Cargando...</p>}
      {errorPartidos && <p className="page-status page-status--error">Error: {errorPartidos}</p>}
      {!loadingPartidos && !errorPartidos && (
        <>
          {partidos.length === 0 ? (
            <p className="page-status">
              No hay partidos próximos cargados todavía. Corré{" "}
              <code>python manage.py run_pipeline_once</code> para sincronizarlos.
            </p>
          ) : (
            <div className="match-grid">
              {partidos.map((partido) => (
                <MatchCard key={partido.id} partido={partido} prediccion={predicciones[partido.id]} />
              ))}
            </div>
          )}
        </>
      )}

      <InfoBox title="¿Qué son los Goles Esperados Proyectados y de dónde salen?">
        <p>
          <strong>Goles Esperados Proyectados</strong> (a veces llamado <strong>xG</strong> en la
          jerga del fútbol) es una estimación de cuántos goles debería anotar cada equipo según su
          rendimiento real reciente, no según el resultado de un solo partido puntual.{" "}
          <strong>
            No es el xG oficial (el que se calcula analizando la calidad de cada tiro) — acá no
            tenemos ese dato para esta liga
          </strong>{" "}
          (ver <strong>Equipos</strong> para el detalle del rating detrás de cada proyección).
        </p>
        <p>
          Se calcula con un <strong>rating de ataque y defensa por equipo</strong>, construido a
          partir de los goles reales marcados y recibidos en sus últimos partidos (hasta 15),
          comparado contra el promedio de la liga. Ninguno de los dos números es una certeza —
          son estimaciones estadísticas, no un pronóstico garantizado.
        </p>
        <p>
          El análisis completo de cada mercado (incluidos los que no tienen valor) y el historial
          de recomendaciones aceptadas/descartadas están en <strong>Dashboard</strong>.
        </p>
      </InfoBox>
    </div>
  );
}
