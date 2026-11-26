import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  desuscribirPush,
  enviarPushPrueba,
  getClavePush,
  getNotificaciones,
  marcarNotificacionesLeidas,
  suscribirPush,
} from "../services/api";
import "./Notificaciones.css";

const INTERVALO_MS = 2 * 60 * 1000;
const ICONO = { PRONOSTICO_SEGURO: "🔒", VALUE_BET: "💰", RESULTADO_FECHA: "📊", SISTEMA: "✅" };

function base64UrlAUint8(base64) {
  const relleno = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + relleno).replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(b64);
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

function hace(fecha) {
  const min = Math.round((Date.now() - new Date(fecha).getTime()) / 60000);
  if (min < 1) return "recién";
  if (min < 60) return `hace ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `hace ${h} h`;
  return `hace ${Math.round(h / 24)} d`;
}

const soportaPush = () => "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

function usePush() {
  const [estado, setEstado] = useState("cargando"); // cargando | no-soportado | bloqueado | activo | inactivo
  const [ocupado, setOcupado] = useState(false);

  const refrescar = useCallback(async () => {
    if (!soportaPush()) return setEstado("no-soportado");
    if (Notification.permission === "denied") return setEstado("bloqueado");
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      setEstado(sub ? "activo" : "inactivo");
    } catch {
      setEstado("no-soportado");
    }
  }, []);

  useEffect(() => {
    refrescar();
  }, [refrescar]);

  const activar = async () => {
    setOcupado(true);
    try {
      const permiso = await Notification.requestPermission();
      if (permiso !== "granted") return setEstado(permiso === "denied" ? "bloqueado" : "inactivo");
      const { clave_publica } = await getClavePush();
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: base64UrlAUint8(clave_publica),
      });
      await suscribirPush(sub.toJSON());
      await enviarPushPrueba();
      setEstado("activo");
    } catch {
      setEstado("inactivo");
    } finally {
      setOcupado(false);
    }
  };

  const desactivar = async () => {
    setOcupado(true);
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        await desuscribirPush(sub.endpoint);
        await sub.unsubscribe();
      }
      setEstado("inactivo");
    } finally {
      setOcupado(false);
    }
  };

  return { estado, ocupado, activar, desactivar };
}

export default function Notificaciones() {
  const [abierto, setAbierto] = useState(false);
  const [datos, setDatos] = useState({ no_leidas: 0, items: [] });
  const [toast, setToast] = useState(null);
  const ultimoId = useRef(null);
  const panelRef = useRef(null);
  const navigate = useNavigate();
  const push = usePush();

  const cargar = useCallback(async () => {
    try {
      const d = await getNotificaciones();
      const masNueva = d.items[0];
      if (masNueva && ultimoId.current !== null && masNueva.id > ultimoId.current && !masNueva.leida) {
        setToast(masNueva);
        setTimeout(() => setToast(null), 8000);
      }
      if (masNueva) ultimoId.current = Math.max(ultimoId.current ?? 0, masNueva.id);
      else if (ultimoId.current === null) ultimoId.current = 0;
      setDatos(d);
    } catch {
      // sin conexión: se reintenta en el próximo ciclo
    }
  }, []);

  useEffect(() => {
    cargar();
    const id = setInterval(cargar, INTERVALO_MS);
    const alVolver = () => document.visibilityState === "visible" && cargar();
    document.addEventListener("visibilitychange", alVolver);
    const alMensaje = (e) => e.data?.tipo === "notificacion-nueva" && cargar();
    navigator.serviceWorker?.addEventListener("message", alMensaje);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", alVolver);
      navigator.serviceWorker?.removeEventListener("message", alMensaje);
    };
  }, [cargar]);

  useEffect(() => {
    if (!abierto) return undefined;
    const fuera = (e) => panelRef.current && !panelRef.current.contains(e.target) && setAbierto(false);
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, [abierto]);

  const abrir = async () => {
    const nuevo = !abierto;
    setAbierto(nuevo);
    if (nuevo && datos.no_leidas > 0) {
      await marcarNotificacionesLeidas().catch(() => {});
      setTimeout(() => setDatos((d) => ({ ...d, no_leidas: 0, items: d.items.map((n) => ({ ...n, leida: true })) })), 1500);
    }
  };

  const ir = (n) => {
    setAbierto(false);
    setToast(null);
    navigate(n.url || "/");
  };

  return (
    <div className="notif" ref={panelRef}>
      <button type="button" className="notif__campana" onClick={abrir} aria-label={`Notificaciones (${datos.no_leidas} sin leer)`}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {datos.no_leidas > 0 && <span className="notif__badge">{datos.no_leidas > 9 ? "9+" : datos.no_leidas}</span>}
      </button>

      {abierto && (
        <div className="notif__panel" role="dialog" aria-label="Notificaciones">
          <header className="notif__cabecera">
            <strong>Notificaciones</strong>
          </header>

          <div className="notif__push">
            {push.estado === "activo" && (
              <>
                <span>🔔 Push activado en este dispositivo</span>
                <button type="button" disabled={push.ocupado} onClick={push.desactivar}>
                  Desactivar
                </button>
              </>
            )}
            {push.estado === "inactivo" && (
              <>
                <span>Recibe las alertas aunque la app esté cerrada.</span>
                <button type="button" className="notif__activar" disabled={push.ocupado} onClick={push.activar}>
                  {push.ocupado ? "Activando…" : "Activar en este dispositivo"}
                </button>
              </>
            )}
            {push.estado === "bloqueado" && (
              <span>Las notificaciones están bloqueadas para este sitio. Habilítalas en los ajustes del navegador.</span>
            )}
            {push.estado === "no-soportado" && (
              <span>
                Este navegador no admite push. En iPhone: comparte → &quot;Agregar a inicio&quot; y abre la app desde
                ahí.
              </span>
            )}
          </div>

          {datos.items.length === 0 ? (
            <p className="notif__vacio">
              Todavía no hay notificaciones. Te avisaremos de los pronósticos muy seguros, las apuestas con valor y el
              resultado de cada fecha.
            </p>
          ) : (
            <ul className="notif__lista">
              {datos.items.map((n) => (
                <li key={n.id}>
                  <button type="button" className={`notif__item ${n.leida ? "" : "notif__item--nueva"}`} onClick={() => ir(n)}>
                    <span className="notif__icono">{ICONO[n.tipo] ?? "•"}</span>
                    <span className="notif__texto">
                      <strong>{n.titulo.replace(/^\p{Extended_Pictographic}\s*/u, "")}</strong>
                      {n.cuerpo && <span className="notif__cuerpo">{n.cuerpo}</span>}
                      <span className="notif__hora">{hace(n.creado_en)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {toast && !abierto && (
        <button type="button" className="notif__toast" onClick={() => ir(toast)} role="status">
          <span className="notif__icono">{ICONO[toast.tipo] ?? "•"}</span>
          <span className="notif__texto">
            <strong>{toast.titulo.replace(/^\p{Extended_Pictographic}\s*/u, "")}</strong>
            {toast.cuerpo && <span className="notif__cuerpo">{toast.cuerpo.split("\n")[0]}</span>}
          </span>
        </button>
      )}
    </div>
  );
}
