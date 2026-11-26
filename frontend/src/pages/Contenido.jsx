import { useEffect, useMemo, useState } from "react";

import { getContenido, urlImagenContenido } from "../services/api";
import "./Contenido.css";

const CATEGORIAS = [
  { id: "todas", label: "Todo" },
  { id: "previa", label: "🔥 Previa" },
  { id: "recap", label: "📊 Cómo nos fue" },
  { id: "simulacion", label: "🎲 Simulaciones" },
  { id: "tablas", label: "🏆 Tablas y datos" },
];
const LIMITE_X = 280;

// Igual que contenido/generador.py:largo_x -- X cuenta emojis y símbolos como 2.
const largoX = (t) => [...t].reduce((n, c) => n + (c.codePointAt(0) > 0x2000 && !"—–·".includes(c) ? 2 : 1), 0);

async function blobImagen(id) {
  const r = await fetch(urlImagenContenido(id));
  if (!r.ok) throw new Error("No se pudo generar la imagen");
  return r.blob();
}

function descargar(blob, nombre) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

const nombreArchivo = (id) => `valuebet-${id.replace(/[|·\s]+/g, "-").toLowerCase()}.png`;

function Pieza({ pieza }) {
  const [texto, setTexto] = useState(pieza.texto);
  const [conImagen, setConImagen] = useState(pieza.imagen);
  const [aviso, setAviso] = useState("");
  const [cargandoImg, setCargandoImg] = useState(true);
  const largo = largoX(texto);
  const puedeCompartirArchivos = typeof navigator !== "undefined" && !!navigator.canShare;

  const avisar = (msg) => {
    setAviso(msg);
    setTimeout(() => setAviso(""), 3500);
  };

  const publicarEnX = async () => {
    // La ventana se abre primero (sincrónico al clic) para que el navegador no la bloquee.
    window.open(`https://x.com/intent/post?text=${encodeURIComponent(texto)}`, "_blank", "noopener");
    if (conImagen) {
      try {
        descargar(await blobImagen(pieza.id), nombreArchivo(pieza.id));
        avisar("Imagen descargada: adjúntala en X con el ícono de imagen 📎");
      } catch {
        avisar("No se pudo descargar la imagen.");
      }
    }
  };

  const compartir = async () => {
    try {
      const datos = { text: texto };
      if (conImagen) {
        const archivo = new File([await blobImagen(pieza.id)], nombreArchivo(pieza.id), { type: "image/png" });
        if (navigator.canShare({ files: [archivo] })) datos.files = [archivo];
      }
      await navigator.share(datos);
    } catch (e) {
      if (e?.name !== "AbortError") avisar("Este dispositivo no permitió compartir; usa 'Publicar en X'.");
    }
  };

  const copiar = async () => {
    await navigator.clipboard.writeText(texto);
    avisar("Texto copiado ✅");
  };

  return (
    <article className="cont-pieza">
      <header className="cont-pieza__cabecera">
        <h3>{pieza.titulo}</h3>
        {pieza.imagen && (
          <div className="cont-formato" role="group" aria-label="Formato">
            <button type="button" className={conImagen ? "activo" : ""} onClick={() => setConImagen(true)}>
              Con imagen
            </button>
            <button type="button" className={!conImagen ? "activo" : ""} onClick={() => setConImagen(false)}>
              Solo texto
            </button>
          </div>
        )}
      </header>

      {conImagen && (
        <a className="cont-pieza__imagen" href={urlImagenContenido(pieza.id)} target="_blank" rel="noreferrer">
          {cargandoImg && <span className="cont-pieza__cargando">Generando imagen…</span>}
          <img
            src={urlImagenContenido(pieza.id)}
            alt={pieza.titulo}
            loading="lazy"
            onLoad={() => setCargandoImg(false)}
            onError={() => setCargandoImg(false)}
          />
        </a>
      )}

      <div className="cont-pieza__texto">
        <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={Math.min(10, texto.split("\n").length + 1)} />
        <div className="cont-pieza__meta">
          <span className={largo > LIMITE_X ? "cont-pieza__largo cont-pieza__largo--excede" : "cont-pieza__largo"}>
            {largo}/{LIMITE_X}
          </span>
          {texto !== pieza.texto && (
            <button type="button" className="cont-link" onClick={() => setTexto(pieza.texto)}>
              Restaurar texto
            </button>
          )}
        </div>
      </div>

      <div className="cont-pieza__acciones">
        <button type="button" className="cont-btn cont-btn--x" onClick={publicarEnX} disabled={largo > LIMITE_X}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
              fill="currentColor"
              d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"
            />
          </svg>
          Publicar en X
        </button>
        {puedeCompartirArchivos && (
          <button type="button" className="cont-btn" onClick={compartir}>
            📲 Compartir
          </button>
        )}
        <button type="button" className="cont-btn" onClick={copiar}>
          📋 Copiar texto
        </button>
        {conImagen && (
          <button
            type="button"
            className="cont-btn"
            onClick={async () => descargar(await blobImagen(pieza.id), nombreArchivo(pieza.id))}
          >
            ⬇️ Imagen
          </button>
        )}
      </div>
      {aviso && <p className="cont-pieza__aviso">{aviso}</p>}
    </article>
  );
}

export default function Contenido() {
  const [piezas, setPiezas] = useState([]);
  const [categoria, setCategoria] = useState("todas");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [version, setVersion] = useState(0);

  const cargar = (refrescar = false) => {
    setLoading(true);
    getContenido(refrescar)
      .then((d) => {
        setPiezas(d);
        setVersion((v) => v + 1);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    cargar();
  }, []);

  const visibles = useMemo(
    () => (categoria === "todas" ? piezas : piezas.filter((p) => p.categoria === categoria)),
    [piezas, categoria]
  );

  return (
    <div className="contenido-page">
      <header className="page-header">
        <h1>Contenido para X</h1>
        <p className="page-header__subtitle">
          Publicaciones listas con los datos del modelo: elige, ajusta el texto si quieres y publica en un toque.
        </p>
      </header>

      <div className="cont-barra">
        <div className="filtro-comp" role="tablist">
          {CATEGORIAS.map((c) => (
            <button
              key={c.id}
              role="tab"
              aria-selected={categoria === c.id}
              className={`filtro-comp__btn ${categoria === c.id ? "filtro-comp__btn--activo" : ""}`}
              onClick={() => setCategoria(c.id)}
            >
              {c.label}
            </button>
          ))}
        </div>
        <button type="button" className="cont-btn" onClick={() => cargar(true)} disabled={loading}>
          🔄 Regenerar
        </button>
      </div>

      <div className="cont-ayuda">
        <strong>Cómo publicar:</strong> en el PC, <em>Publicar en X</em> abre X con el texto listo y descarga la imagen
        para adjuntarla. En el celular, <em>Compartir</em> → X adjunta la imagen sola.
      </div>

      {loading && <p className="page-status">Generando contenido…</p>}
      {error && <p className="page-status page-status--error">Error: {error}</p>}

      {!loading && (
        <div className="cont-grid">
          {visibles.map((p) => (
            <Pieza key={`${p.id}-${version}`} pieza={p} />
          ))}
        </div>
      )}
    </div>
  );
}
