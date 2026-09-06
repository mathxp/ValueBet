import { useEffect, useState } from "react";

import InfoBox from "../components/InfoBox";
import MatchCard from "../components/MatchCard";
import { getPartidos, getPrediccion } from "../services/api";

export default function Predicciones() {
  const [partidos, setPartidos] = useState([]);
  const [predicciones, setPredicciones] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="predicciones-page">
      <header className="page-header">
        <h1>Predicciones — Primera División de Chile</h1>
        <p className="page-header__subtitle">
          Goles esperados (xG) proyectados para los próximos partidos, calculados con un modelo
          estadístico propio.
        </p>
      </header>

      <InfoBox title="¿Qué es el xG y de dónde sale?">
        <p>
          El <strong>xG (goles esperados)</strong> es una estimación de cuántos goles debería
          anotar cada equipo según su rendimiento real reciente, no según el resultado de un solo
          partido puntual.
        </p>
        <p>
          Se calcula con un <strong>rating de ataque y defensa por equipo</strong>, construido a
          partir de los goles reales marcados y recibidos en sus últimos partidos (hasta 15),
          comparado contra el promedio de la liga. Un equipo necesita al menos 3 partidos jugados
          y cargados para que su proyección se considere confiable — antes de eso, se muestra
          &quot;sin datos aún&quot; en vez de inventar un número. Ver el detalle por equipo en la
          pestaña <strong>Equipos</strong>.
        </p>
        <p>
          El xG por sí solo no dice quién gana: con esos dos números se calcula además la
          probabilidad de victoria de cada equipo (y de empate), que es lo que se muestra como{" "}
          <strong>&quot;Favorito&quot;</strong> en cada tarjeta.
        </p>
      </InfoBox>

      {loading && <p className="page-status">Cargando...</p>}
      {error && <p className="page-status page-status--error">Error: {error}</p>}

      {!loading && !error && (
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
    </div>
  );
}
