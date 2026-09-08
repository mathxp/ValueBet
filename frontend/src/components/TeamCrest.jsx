import { useState } from "react";
import "./TeamCrest.css";

// Paleta fija (no depende del tema) para que el color de cada equipo sea
// estable entre renders -- se elige por hash del nombre, no al azar.
const PALETA = ["#2563eb", "#059669", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#be185d", "#4d7c0f"];

function colorParaNombre(nombre) {
  let hash = 0;
  for (let i = 0; i < nombre.length; i++) {
    hash = (hash * 31 + nombre.charCodeAt(i)) | 0;
  }
  return PALETA[Math.abs(hash) % PALETA.length];
}

function iniciales(nombre) {
  const palabras = nombre.split(/\s+/).filter(Boolean);
  if (palabras.length === 1) return palabras[0].slice(0, 2).toUpperCase();
  return (palabras[0][0] + palabras[palabras.length - 1][0]).toUpperCase();
}

/**
 * Escudo de equipo con fallback a un avatar de iniciales -- cubre tanto
 * equipos sin logo_url (datasets históricos sin match en api-football) como
 * una URL externa caída (onError), para no dejar nunca un hueco en blanco.
 */
export default function TeamCrest({ equipo, className = "" }) {
  const [fallo, setFallo] = useState(false);

  if (!equipo.logo_url || fallo) {
    return (
      <div
        className={`team-crest-fallback ${className}`}
        style={{ backgroundColor: colorParaNombre(equipo.nombre) }}
        title={equipo.nombre}
      >
        {iniciales(equipo.nombre)}
      </div>
    );
  }

  return (
    <img
      src={equipo.logo_url}
      alt=""
      className={className}
      loading="lazy"
      onError={() => setFallo(true)}
    />
  );
}
