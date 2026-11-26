import { useEffect, useMemo, useState } from "react";

import Card from "../components/Card";
import InfoBox from "../components/InfoBox";
import TeamCrest from "../components/TeamCrest";
import { getEquipoRatings } from "../services/api";

const COLUMNAS_RATING = [
  { key: "nombre", label: "Equipo" },
  { key: "ataque", label: "Ataque" },
  { key: "defensa", label: "Defensa" },
  { key: "partidos", label: "Partidos" },
  { key: "confiable", label: "Confiable" },
];

function valorOrden(r, campo) {
  if (campo === "nombre") return r.equipo.nombre;
  if (campo === "confiable") return r.confiable ? 1 : 0;
  return r[campo];
}

function TablaRatings({ ratings }) {
  // Sin ordenar por defecto (orden que ya trae la API) -- un clic en la
  // columna alcanza para ver, por ejemplo, quién tiene más ataque o peor
  // defensa (descendente = los números más altos primero, sea cual sea la
  // columna -- para Defensa eso muestra primero a los que MÁS goles reciben,
  // no a los mejores).
  const [ordenPor, setOrdenPor] = useState(null);
  const [ordenDesc, setOrdenDesc] = useState(true);

  const filas = useMemo(() => {
    if (!ordenPor) return ratings;
    const copia = [...ratings];
    copia.sort((a, b) => {
      const valorA = valorOrden(a, ordenPor);
      const valorB = valorOrden(b, ordenPor);
      if (typeof valorA === "string") {
        return ordenDesc ? valorB.localeCompare(valorA) : valorA.localeCompare(valorB);
      }
      return ordenDesc ? valorB - valorA : valorA - valorB;
    });
    return copia;
  }, [ratings, ordenPor, ordenDesc]);

  function ordenarPor(campo) {
    if (campo === ordenPor) {
      setOrdenDesc((desc) => !desc);
    } else {
      setOrdenPor(campo);
      setOrdenDesc(true);
    }
  }

  return (
    <div className="operations-table__scroll">
      <table className="operations-table">
        <thead>
          <tr>
            {COLUMNAS_RATING.map((col) => (
              <th key={col.key} onClick={() => ordenarPor(col.key)} className="equipos-page__th-ordenable">
                {col.label}
                {ordenPor === col.key && (ordenDesc ? " ▼" : " ▲")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((r) => (
            <tr key={r.equipo.id}>
              <td>
                <div className="equipos-page__nombre">
                  <TeamCrest equipo={r.equipo} className="equipos-page__logo" />
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
  );
}

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
          el mínimo de 3 partidos para que la proyección se use en las predicciones. Hacé clic en
          una columna para ordenar por esa estadística — por ejemplo, para ver qué equipos tienen
          más ataque o peor defensa.
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
            <TablaRatings ratings={ratings} />
          )}
        </Card>
      )}

      {!loading && !error && <EstadisticasFotMob ratings={ratings} />}
    </div>
  );
}

const COLUMNAS_FOTMOB = [
  { key: "possession_percentage_team", label: "Posesión", formato: (v) => `${v.toFixed(1)}%` },
  { key: "big_chance_team", label: "Grandes ocasiones", formato: (v) => v },
  { key: "big_chance_missed_team", label: "... falladas", formato: (v) => v },
  { key: "ontarget_scoring_att_team", label: "Tiros al arco", formato: (v) => `${v.toFixed(1)}/partido` },
  { key: "corner_taken_team", label: "Corners", formato: (v) => v },
];

function EstadisticasFotMob({ ratings }) {
  const [ordenPor, setOrdenPor] = useState("possession_percentage_team");
  const [ordenDesc, setOrdenDesc] = useState(true);

  const filas = ratings.filter((r) => r.equipo.metadata?.fotmob);

  const filasOrdenadas = useMemo(() => {
    const copia = [...filas];
    copia.sort((a, b) => {
      const valorA = a.equipo.metadata.fotmob[ordenPor] ?? 0;
      const valorB = b.equipo.metadata.fotmob[ordenPor] ?? 0;
      return ordenDesc ? valorB - valorA : valorA - valorB;
    });
    return copia;
  }, [filas, ordenPor, ordenDesc]);

  if (filas.length === 0) return null;

  const temporada = filas[0].equipo.metadata.fotmob.temporada;

  function ordenarPor(campo) {
    if (campo === ordenPor) {
      setOrdenDesc((desc) => !desc);
    } else {
      setOrdenPor(campo);
      setOrdenDesc(true);
    }
  }

  return (
    <>
      <InfoBox title={`Estadísticas complementarias (FotMob, temporada ${temporada})`}>
        <p>
          Posesión, grandes ocasiones y tiros al arco promedio de la temporada, vía{" "}
          <strong>FotMob</strong>. Es información de contexto para vos —{" "}
          <strong>todavía no se usa en el cálculo de ataque/defensa ni en las probabilidades</strong>{" "}
          de arriba: son promedios de temporada sin calibrar contra los resultados reales de esta
          liga, y el resto del modelo sí pasó por ese proceso antes de influir en una
          recomendación. Hacé clic en una columna para ordenar por esa estadística — por ejemplo,
          para ver qué equipos generan más corners o más ocasiones claras.
        </p>
        <p>
          Solo aparecen los equipos que FotMob ya publicó para la temporada {temporada} -- un
          equipo recién ascendido puede no figurar acá todavía aunque sí tenga rating de
          ataque/defensa arriba (ese se calcula con nuestro propio historial de partidos, no
          depende de FotMob).
        </p>
      </InfoBox>

      <Card>
        <div className="operations-table__scroll">
          <table className="operations-table">
            <thead>
              <tr>
                <th>Equipo</th>
                {COLUMNAS_FOTMOB.map((col) => (
                  <th
                    key={col.key}
                    onClick={() => ordenarPor(col.key)}
                    className="equipos-page__th-ordenable"
                  >
                    {col.label}
                    {ordenPor === col.key && (ordenDesc ? " ▼" : " ▲")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filasOrdenadas.map((r) => {
                const f = r.equipo.metadata.fotmob;
                return (
                  <tr key={r.equipo.id}>
                    <td>
                      <div className="equipos-page__nombre">
                        {r.equipo.logo_url && (
                          <img src={r.equipo.logo_url} alt="" className="equipos-page__logo" />
                        )}
                        {r.equipo.nombre}
                      </div>
                    </td>
                    {COLUMNAS_FOTMOB.map((col) => (
                      <td key={col.key}>
                        {f[col.key] != null ? col.formato(f[col.key]) : "—"}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
