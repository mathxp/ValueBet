const currencyFormatter = new Intl.NumberFormat("es-CL", {
  style: "currency",
  currency: "CLP",
  maximumFractionDigits: 0,
});

const percentFormatter = new Intl.NumberFormat("es-CL", {
  style: "percent",
  maximumFractionDigits: 1,
});

export function formatCurrency(value) {
  return currencyFormatter.format(Number(value ?? 0));
}

export function formatPercent(value) {
  return percentFormatter.format(Number(value ?? 0));
}

export function formatOdds(value) {
  return Number(value ?? 0).toFixed(2);
}

const SELECCION_1X2 = { LOCAL: "Gana local", EMPATE: "Empate", VISITANTE: "Gana visitante" };
const SELECCION_DOBLE_OPORTUNIDAD = {
  "1X": "Local o empate",
  "12": "Local o visitante",
  X2: "Empate o visitante",
};

export function formatMercado(mercado) {
  if (mercado === "1X2") return "Resultado (1X2)";
  if (mercado === "DOBLE_OPORTUNIDAD") return "Doble Oportunidad";
  if (mercado.startsWith("OVER_UNDER_")) {
    const linea = mercado.replace("OVER_UNDER_", "");
    return `Goles totales (línea ${linea})`;
  }
  return mercado;
}

export function formatSeleccion(mercado, seleccion) {
  if (mercado === "1X2") return SELECCION_1X2[seleccion] ?? seleccion;
  if (mercado === "DOBLE_OPORTUNIDAD") return SELECCION_DOBLE_OPORTUNIDAD[seleccion] ?? seleccion;
  if (mercado.startsWith("OVER_UNDER_")) {
    const linea = mercado.replace("OVER_UNDER_", "");
    return seleccion === "OVER" ? `Más de ${linea} goles` : `Menos de ${linea} goles`;
  }
  return seleccion;
}

export const ESTADO_OPERACION_CONFIG = {
  RECOMMENDED: { label: "Recomendada", tone: "info", icon: "◐" },
  ACCEPTED: { label: "Aceptada", tone: "warning", icon: "●" },
  DISCARDED: { label: "Descartada", tone: "muted", icon: "✕" },
  WON: { label: "Ganada", tone: "good", icon: "▲" },
  LOST: { label: "Perdida", tone: "critical", icon: "▼" },
  VOID: { label: "Anulada", tone: "muted", icon: "○" },
};

const NIVELES_CONFIANZA = [
  { min: 90, emoji: "🔵", label: "Muy alta" },
  { min: 75, emoji: "🟢", label: "Alta" },
  { min: 60, emoji: "🟡", label: "Media" },
  { min: 40, emoji: "🟠", label: "Baja" },
  { min: 0, emoji: "🔴", label: "Muy baja" },
];

export function nivelConfianza(valor) {
  return NIVELES_CONFIANZA.find((nivel) => valor >= nivel.min) ?? NIVELES_CONFIANZA[NIVELES_CONFIANZA.length - 1];
}

export function formatDateTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("es-CL", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Texto con nombres de equipo para un pronóstico de /api/pronosticos/.
export function etiquetaPronostico(pron, partido) {
  const local = partido.equipo_local.nombre;
  const visita = partido.equipo_visitante.nombre;
  if (pron.mercado === "1X2") {
    return { LOCAL: `Gana ${local}`, VISITANTE: `Gana ${visita}`, EMPATE: "Empate" }[pron.seleccion];
  }
  if (pron.mercado === "DOBLE_OPORTUNIDAD") {
    return { "1X": `${local} o empate`, X2: `${visita} o empate`, 12: "No hay empate" }[pron.seleccion];
  }
  return pron.seleccion === "OVER" ? "Más de 2.5 goles" : "Menos de 2.5 goles";
}
