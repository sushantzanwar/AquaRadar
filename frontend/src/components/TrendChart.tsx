import type { TrendSeries } from "../api/client";

export function TrendChart({ series }: { series: TrendSeries | null }) {
  if (!series) return <p className="muted">Choose a zone to plot its history.</p>;
  const points = series.points.filter((point) => point.value !== null);
  if (!points.length) return <p className="muted">No {series.indicator} values for this zone yet.</p>;
  const values = points.flatMap((point) => [point.value as number, point.baseline_mean ?? point.value]);
  const min = Math.min(...(values as number[]));
  const max = Math.max(...(values as number[]));
  const span = max - min || 1;
  const width = 320;
  const height = 120;
  const step = points.length === 1 ? 0 : width / (points.length - 1);
  const y = (value: number) => height - ((value - min) / span) * (height - 16) - 8;
  const line = points.map((point, index) => `${index * step},${y(point.value as number)}`).join(" ");
  const band = points
    .filter((point) => point.baseline_mean !== null)
    .map((point, index) => `${index * step},${y(point.baseline_mean as number)}`)
    .join(" ");
  return (
    <figure className="chart">
      <figcaption>
        {series.indicator} · {series.zone_id}
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img">
        {band ? <polyline points={band} className="baseline" /> : null}
        <polyline points={line} className="series" />
      </svg>
      <p className="muted">Line is the zone value. The second stroke is the seasonal baseline mean.</p>
    </figure>
  );
}
