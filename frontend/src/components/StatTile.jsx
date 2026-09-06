import "./StatTile.css";

export default function StatTile({ label, value, tone = "neutral" }) {
  return (
    <div className={`stat-tile stat-tile--${tone}`}>
      <span className="stat-tile__label">{label}</span>
      <span className="stat-tile__value">{value}</span>
    </div>
  );
}
