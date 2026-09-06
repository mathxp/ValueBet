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

export function formatMercado(mercado) {
  if (mercado === "1X2") return "Resultado (1X2)";
  if (mercado.startsWith("OVER_UNDER_")) {
    const linea = mercado.replace("OVER_UNDER_", "");
    return `Goles totales (línea ${linea})`;
  }
  return mercado;
}

export function formatSeleccion(mercado, seleccion) {
  if (mercado === "1X2") return SELECCION_1X2[seleccion] ?? seleccion;
  if (mercado.startsWith("OVER_UNDER_")) {
    const linea = mercado.replace("OVER_UNDER_", "");
    return seleccion === "OVER" ? `Más de ${linea} goles` : `Menos de ${linea} goles`;
  }
  return seleccion;
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
