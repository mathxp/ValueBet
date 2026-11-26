import { NavLink, Route, Routes } from "react-router-dom";

import "./App.css";
import logoMark from "./assets/logo-mark.png";
import ThemeToggle from "./components/ThemeToggle";
import Configuracion from "./pages/Configuracion";
import Dashboard from "./pages/Dashboard";
import Equipos from "./pages/Equipos";
import Predicciones from "./pages/Predicciones";
import Tablas from "./pages/Tablas";

function IconoIndicador() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 17 9 11 13 15 21 6" />
      <polyline points="15 6 21 6 21 12" />
    </svg>
  );
}

function IconoEquipos() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

function IconoDashboard() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </svg>
  );
}

function IconoTablas() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 21h8" />
      <path d="M12 17v4" />
      <path d="M7 4h10v5a5 5 0 0 1-10 0V4z" />
      <path d="M17 6h3v2a3 3 0 0 1-3 3" />
      <path d="M7 6H4v2a3 3 0 0 0 3 3" />
    </svg>
  );
}

function IconoConfiguracion() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" y1="21" x2="4" y2="14" />
      <line x1="4" y1="10" x2="4" y2="3" />
      <line x1="12" y1="21" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12" y2="3" />
      <line x1="20" y1="21" x2="20" y2="16" />
      <line x1="20" y1="12" x2="20" y2="3" />
      <line x1="1" y1="14" x2="7" y2="14" />
      <line x1="9" y1="8" x2="15" y2="8" />
      <line x1="17" y1="16" x2="23" y2="16" />
    </svg>
  );
}

export default function App() {
  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="app-sidebar__brand">
          <img src={logoMark} alt="" className="app-sidebar__brand-logo" />
          <div className="app-sidebar__brand-text">
            <span className="app-sidebar__brand-name">ValueBet</span>
            <span className="app-sidebar__brand-tag">Primera División Chile</span>
          </div>
        </div>

        <nav className="app-sidebar__nav">
          <NavLink to="/" end>
            <IconoIndicador />
            <span>Predicciones</span>
          </NavLink>
          <NavLink to="/dashboard">
            <IconoDashboard />
            <span>Dashboard</span>
          </NavLink>
          <NavLink to="/tablas">
            <IconoTablas />
            <span>Tablas</span>
          </NavLink>
          <NavLink to="/equipos">
            <IconoEquipos />
            <span>Equipos</span>
          </NavLink>
          <NavLink to="/configuracion">
            <IconoConfiguracion />
            <span>Configuración</span>
          </NavLink>
        </nav>

        <ThemeToggle />

        <p className="app-sidebar__disclaimer">
          Herramienta de apoyo a la decisión. No ejecuta apuestas ni garantiza resultados.
        </p>
      </aside>

      <div className="app-content">
        <main className="app-main">
          <Routes>
            <Route path="/" element={<Predicciones />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/tablas" element={<Tablas />} />
            <Route path="/equipos" element={<Equipos />} />
            <Route path="/configuracion" element={<Configuracion />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
