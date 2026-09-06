import { NavLink, Route, Routes } from "react-router-dom";

import "./App.css";
import Configuracion from "./pages/Configuracion";
import Equipos from "./pages/Equipos";
import Predicciones from "./pages/Predicciones";
import Recomendaciones from "./pages/Recomendaciones";

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__brand">
          <span className="app-header__brand-name">ValueBet</span>
          <span className="app-header__brand-tag">Análisis predictivo · Primera División Chile</span>
        </div>
        <nav className="app-nav">
          <NavLink to="/" end>
            Predicciones
          </NavLink>
          <NavLink to="/equipos">Equipos</NavLink>
          <NavLink to="/recomendaciones" className="app-nav__secondary">
            Recomendaciones
          </NavLink>
          <NavLink to="/configuracion">Configuración</NavLink>
        </nav>
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<Predicciones />} />
          <Route path="/equipos" element={<Equipos />} />
          <Route path="/recomendaciones" element={<Recomendaciones />} />
          <Route path="/configuracion" element={<Configuracion />} />
        </Routes>
      </main>
    </div>
  );
}
