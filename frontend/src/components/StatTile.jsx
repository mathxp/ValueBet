import "./StatTile.css";

export default function StatTile({ label, value, tone = "neutral", hint, dim = false }) {
  return (
    <div className={`stat-tile stat-tile--${tone}${dim ? " stat-tile--dim" : ""}`}>
      <span className="stat-tile__label">{label}</span>
      <span className="stat-tile__value">{value}</span>
      {hint && <span className="stat-tile__hint">{hint}</span>}
    </div>
  );
}
