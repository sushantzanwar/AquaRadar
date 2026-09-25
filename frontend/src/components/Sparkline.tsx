export function Sparkline({ label, values, unit }: { label: string; values: number[]; unit: string }) {
  if (!values.length) return <p className="muted">{label}: no stored values.</p>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const width = 160;
  const height = 36;
  const step = values.length === 1 ? 0 : width / (values.length - 1);
  const points = values
    .map((value, index) => `${index * step},${height - ((value - min) / span) * (height - 6) - 3}`)
    .join(" ");
  return (
    <figure className="spark">
      <figcaption>
        {label} <span className="muted">{unit}</span>
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label} sparkline`}>
        <polyline points={points} className="series" />
      </svg>
    </figure>
  );
}
