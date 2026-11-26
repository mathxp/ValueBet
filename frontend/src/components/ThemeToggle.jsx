import { useState } from "react";

function temaActual() {
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

export default function ThemeToggle() {
  const [tema, setTema] = useState(temaActual);
  const oscuro = tema === "dark";

  function alternar() {
    const nuevo = oscuro ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", nuevo);
    try {
      localStorage.setItem("tema", nuevo);
    } catch {
      // modo privado / almacenamiento bloqueado: el cambio igual aplica en esta visita
    }
    setTema(nuevo);
  }

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={alternar}
      aria-label={oscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
      title={oscuro ? "Modo claro" : "Modo oscuro"}
    >
      {oscuro ? (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      )}
      <span>{oscuro ? "Modo claro" : "Modo oscuro"}</span>
    </button>
  );
}
