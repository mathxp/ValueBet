import "./StatusBadge.css";

const ESTADO_CONFIG = {
  RECOMMENDED: { label: "Recomendada", tone: "info", icon: "◐" },
  ACCEPTED: { label: "Aceptada", tone: "warning", icon: "●" },
  DISCARDED: { label: "Descartada", tone: "muted", icon: "✕" },
  WON: { label: "Ganada", tone: "good", icon: "▲" },
  LOST: { label: "Perdida", tone: "critical", icon: "▼" },
  VOID: { label: "Anulada", tone: "muted", icon: "○" },
};

export default function StatusBadge({ estado }) {
  const config = ESTADO_CONFIG[estado] ?? { label: estado, tone: "muted", icon: "○" };

  return (
    <span className={`status-badge status-badge--${config.tone}`}>
      <span aria-hidden="true">{config.icon}</span>
      {config.label}
    </span>
  );
}
