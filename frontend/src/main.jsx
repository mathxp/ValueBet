import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);

// Habilita "Agregar a pantalla de inicio" en el celular (ver manifest.json).
// Los navegadores solo instalan el service worker en HTTPS o localhost --
// en HTTP dentro de la red local esto no corre, pero el acceso directo al
// dashboard sigue funcionando igual, solo sin instalación como app.
if ("serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
