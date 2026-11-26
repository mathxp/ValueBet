import axios from "axios";

const api = axios.create({
  baseURL: "/api/",
});

// El backend (Render gratis) se duerme sin uso y tarda ~30-50 s en despertar.
// La Pages Function ya reintenta; si aun así llega un 502/503/504, se reintenta
// acá unas veces más y se avisa a la UI (ver components/AvisoDespertando.jsx).
const REINTENTOS_MAX = 3;
const ESPERA_MS = 5000;

function avisarDespertando(activo) {
  window.dispatchEvent(new CustomEvent("api-despertando", { detail: activo }));
}

api.interceptors.response.use(
  (resp) => {
    avisarDespertando(false);
    return resp;
  },
  async (error) => {
    const config = error.config;
    const estado = error.response?.status;
    const reintentable = !error.response || [502, 503, 504].includes(estado);
    const esLectura = (config?.method ?? "get").toLowerCase() === "get";
    if (config && reintentable && esLectura && (config.__intentos ?? 0) < REINTENTOS_MAX) {
      config.__intentos = (config.__intentos ?? 0) + 1;
      avisarDespertando(true);
      await new Promise((r) => setTimeout(r, ESPERA_MS));
      return api(config);
    }
    avisarDespertando(false);
    return Promise.reject(error);
  }
);

export const getPartidos = (params) => api.get("partidos/", { params }).then((r) => r.data);

export const getOperaciones = (params) =>
  api.get("operaciones/", { params }).then((r) => r.data);

export const getResumenOperaciones = () =>
  api.get("operaciones/resumen/").then((r) => r.data);

export const getEquipos = (params) => api.get("equipos/", { params }).then((r) => r.data);

export const getPrediccion = (partidoId) =>
  api.get(`partidos/${partidoId}/prediccion/`).then((r) => r.data);

export const getEquipoRatings = () => api.get("equipos/ratings/").then((r) => r.data);

export const aceptarOperacion = (id) => api.post(`operaciones/${id}/aceptar/`).then((r) => r.data);

export const descartarOperacion = (id) =>
  api.post(`operaciones/${id}/descartar/`).then((r) => r.data);

export const marcarOperacionGanada = (id) =>
  api.post(`operaciones/${id}/marcar-ganada/`).then((r) => r.data);

export const marcarOperacionPerdida = (id) =>
  api.post(`operaciones/${id}/marcar-perdida/`).then((r) => r.data);

export const marcarOperacionAnulada = (id) =>
  api.post(`operaciones/${id}/marcar-anulada/`).then((r) => r.data);

export const revertirOperacion = (id) => api.post(`operaciones/${id}/revertir/`).then((r) => r.data);

export const getCombinadas = (params) => api.get("combinadas/", { params }).then((r) => r.data);

export const aceptarCombinada = (id) => api.post(`combinadas/${id}/aceptar/`).then((r) => r.data);

export const descartarCombinada = (id) =>
  api.post(`combinadas/${id}/descartar/`).then((r) => r.data);

export const marcarCombinadaGanada = (id) =>
  api.post(`combinadas/${id}/marcar-ganada/`).then((r) => r.data);

export const marcarCombinadaPerdida = (id) =>
  api.post(`combinadas/${id}/marcar-perdida/`).then((r) => r.data);

export const marcarCombinadaAnulada = (id) =>
  api.post(`combinadas/${id}/marcar-anulada/`).then((r) => r.data);

export const revertirCombinada = (id) => api.post(`combinadas/${id}/revertir/`).then((r) => r.data);

export const getAnalisis = (params) => api.get("analisis/", { params }).then((r) => r.data);

export const getRendimientoModelo = () =>
  api.get("analisis/rendimiento/").then((r) => r.data);

export const getRendimientoValueBets = () =>
  api.get("analisis/rendimiento-value-bets/").then((r) => r.data);

export const getRendimientoPorMercado = () =>
  api.get("analisis/rendimiento-por-mercado/").then((r) => r.data);

export const getBacktest = () => api.get("analisis/backtest/").then((r) => r.data);

export const getConfiguracion = () => api.get("config/").then((r) => r.data);

export const actualizarConfiguracionRiesgo = (cambios) =>
  api.patch("config/", cambios).then((r) => r.data);

export default api;

export const getTablas = () => api.get("tablas/").then((r) => r.data);

export const getPronosticos = () => api.get("pronosticos/").then((r) => r.data);

export const getHistorialPronosticos = () => api.get("pronosticos/historial/").then((r) => r.data);
