import type { EvidenceCard as Card } from "../api/client";
import { ConfidenceBadge } from "./ConfidenceBadge";

export function EvidenceCard({ card }: { card: Card | null }) {
  if (!card) return <p className="muted">Select a zone to see why it was or was not flagged.</p>;
  return (
    <article className="card">
      <header>
        <h3>{card.zone_name}</h3>
        <ConfidenceBadge score={card.confidence} reasons={card.confidence_reasons} />
      </header>
      <p>
        {card.date} · evidence {card.evidence_id}
      </p>
      <table>
        <thead>
          <tr>
            <th>Indicator</th>
            <th>Value</th>
            <th>Baseline</th>
            <th>Sigma</th>
            <th>Crossed</th>
          </tr>
        </thead>
        <tbody>
          {card.comparisons.map((row) => (
            <tr key={row.indicator}>
              <td>{row.indicator}</td>
              <td>{row.value.toFixed(3)}</td>
              <td>
                {row.baseline_mean.toFixed(3)} ± {row.baseline_std ?? "n/a"}
              </td>
              <td>{row.sigma === null ? "n/a" : row.sigma.toFixed(2)}</td>
              <td>{row.crossed ? "yes" : "no"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>Extent change: {card.extent_change_m2 === null ? "n/a" : `${card.extent_change_m2.toFixed(0)} m²`}</p>
      <p>Contributing: {card.contributing_indicators.join(", ") || "none"}</p>
      <p>Thresholds: {card.thresholds_crossed.join(", ") || "none crossed"}</p>
      <p className="disclaimer-inline">{card.disclaimer}</p>
    </article>
  );
}
