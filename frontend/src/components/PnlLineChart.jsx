import { useMemo, useState } from "react";

import { formatCurrency, formatDateTime } from "../utils/format";
import "./PnlLineChart.css";

const WIDTH = 720;
const HEIGHT = 220;
const PADDING = { top: 16, right: 16, bottom: 24, left: 16 };

export default function PnlLineChart({ points }) {
  const [hoverIndex, setHoverIndex] = useState(null);

  const { path, scaleX, scaleY } = useMemo(() => {
    if (!points.length) {
      return { path: "", scaleX: () => 0, scaleY: () => 0 };
    }

    const values = points.map((p) => p.value);
    const minY = Math.min(0, ...values);
    const maxY = Math.max(0, ...values);
    const spanY = maxY - minY || 1;

    const innerWidth = WIDTH - PADDING.left - PADDING.right;
    const innerHeight = HEIGHT - PADDING.top - PADDING.bottom;

    const scaleX = (i) =>
      PADDING.left + (points.length === 1 ? innerWidth / 2 : (i / (points.length - 1)) * innerWidth);
    const scaleY = (v) => PADDING.top + innerHeight - ((v - minY) / spanY) * innerHeight;

    const path = points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${scaleX(i).toFixed(1)} ${scaleY(p.value).toFixed(1)}`)
      .join(" ");

    return { path, scaleX, scaleY };
  }, [points]);

  if (!points.length) {
    return <p className="pnl-chart__empty">Aún no hay operaciones registradas.</p>;
  }

  const zeroY = scaleY(0);
  const hovered = hoverIndex !== null ? points[hoverIndex] : null;

  return (
    <div className="pnl-chart">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="Evolución del PNL acumulado"
        onMouseLeave={() => setHoverIndex(null)}
        onMouseMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const x = ((event.clientX - rect.left) / rect.width) * WIDTH;
          let nearest = 0;
          let bestDist = Infinity;
          points.forEach((_, i) => {
            const dist = Math.abs(scaleX(i) - x);
            if (dist < bestDist) {
              bestDist = dist;
              nearest = i;
            }
          });
          setHoverIndex(nearest);
        }}
      >
        <line
          x1={PADDING.left}
          x2={WIDTH - PADDING.right}
          y1={zeroY}
          y2={zeroY}
          className="pnl-chart__baseline"
        />
        <path d={path} className="pnl-chart__line" fill="none" />
        {hovered && (
          <>
            <line
              x1={scaleX(hoverIndex)}
              x2={scaleX(hoverIndex)}
              y1={PADDING.top}
              y2={HEIGHT - PADDING.bottom}
              className="pnl-chart__crosshair"
            />
            <circle
              cx={scaleX(hoverIndex)}
              cy={scaleY(hovered.value)}
              r="4"
              className="pnl-chart__dot"
            />
          </>
        )}
      </svg>
      {hovered && (
        <div
          className="pnl-chart__tooltip"
          style={{ left: `${(scaleX(hoverIndex) / WIDTH) * 100}%` }}
        >
          <strong>{formatCurrency(hovered.value)}</strong>
          <span>{formatDateTime(hovered.label)}</span>
        </div>
      )}
    </div>
  );
}
