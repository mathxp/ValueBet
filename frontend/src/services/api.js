import axios from "axios";

const api = axios.create({
  baseURL: "/api/",
});

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

export const getAnalisis = (params) => api.get("analisis/", { params }).then((r) => r.data);

export const getRendimientoModelo = () =>
  api.get("analisis/rendimiento/").then((r) => r.data);

export default api;
