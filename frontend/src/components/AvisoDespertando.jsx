import { useEffect, useState } from "react";

/** Aviso mientras el backend (Render gratis) despierta tras estar inactivo. */
export default function AvisoDespertando() {
  const [activo, setActivo] = useState(false);

  useEffect(() => {
    const manejar = (e) => setActivo(Boolean(e.detail));
    window.addEventListener("api-despertando", manejar);
    return () => window.removeEventListener("api-despertando", manejar);
  }, []);

  if (!activo) return null;
  return (
    <div className="aviso-despertando" role="status">
      <span className="aviso-despertando__punto" aria-hidden="true" />
      Despertando el servidor… la primera carga puede tardar hasta un minuto.
    </div>
  );
}
