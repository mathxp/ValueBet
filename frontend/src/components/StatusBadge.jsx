import { ESTADO_OPERACION_CONFIG } from "../utils/format";
import "./StatusBadge.css";

export default function StatusBadge({ estado }) {
  const config = ESTADO_OPERACION_CONFIG[estado] ?? { label: estado, tone: "muted", icon: "○" };

  return (
    <span className={`status-badge status-badge--${config.tone}`}>
      <span aria-hidden="true">{config.icon}</span>
      {config.label}
    </span>
  );
}
