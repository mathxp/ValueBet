import { useEffect, useState } from "react";

import Card from "../components/Card";
import InfoBox from "../components/InfoBox";
import { getEquipoRatings } from "../services/api";

export default function Equipos() {
  const [ratings, setRatings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getEquipoRatings()
      .then(setRatings)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="equipos-page">
      <header className="page-header">
        <h1>Equipos</h1>
        <p className="page-header__subtitle">
          Rating de ataque y defensa de cada equipo, la base de las predicciones.
        </p>
      </header>

      <InfoBox title="Cómo leer esta tabla">
        <p>
          <strong>Ataque</strong>: promedio de goles a favor en sus últimos partidos (hasta 15).{" "}
          <strong>Defensa</strong>: promedio de goles en contra — más bajo es mejor.
        </p>
        <p>
          Los números están <strong>ajustados estadísticamente</strong> hacia el promedio de la
          liga cuando un equipo tiene pocos partidos jugados, para no sacar conclusiones
          exageradas de una racha corta. La columna <strong>confiable</strong> indica si ya superó
          el mínimo de 3 partidos para que la proyección se use en las predicciones.
        </p>
      </InfoBox>

      {loading && <p className="page-status">Cargando...</p>}
      {error && <p className="page-status page-status--error">Error: {error}</p>}

      {!loading && !error && (
        <Card>
          {ratings.length === 0 ? (
            <p className="page-status">
              Todavía no hay partidos finalizados cargados para calcular ratings.
            </p>
          ) : (
            <div className="operations-table__scroll">
              <table className="operations-table">
                <thead>
                  <tr>
                    <th>Equipo</th>
                    <th>Ataque</th>
                    <th>Defensa</th>
                    <th>Partidos</th>
                    <th>Confiable</th>
                  </tr>
                </thead>
                <tbody>
                  {ratings.map((r) => (
                    <tr key={r.equipo.id}>
                      <td>
                        <div className="equipos-page__nombre">
                          {r.equipo.logo_url && (
                            <img src={r.equipo.logo_url} alt="" className="equipos-page__logo" />
                          )}
                          {r.equipo.nombre}
                        </div>
                      </td>
                      <td>{r.ataque.toFixed(2)}</td>
                      <td>{r.defensa.toFixed(2)}</td>
                      <td>{r.partidos}</td>
                      <td>{r.confiable ? "Sí" : "Todavía no"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
