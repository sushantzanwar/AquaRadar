import type { AlertEvidenceCard as Card } from "../api/client";
import { ConfidenceBadge } from "./ConfidenceBadge";

function formatNumber(value: number | null, digits: number) {
  return value === null ? "n/a" : value.toFixed(digits);
}

export function AlertEvidenceCard({ card }: { card: Card | null }) {
  if (!card) return <p className="muted">Select a series alert to see the numbers behind it.</p>;
  const rows = card.contributing_indicators.length ? card.contributing_indicators : card.indicators;
  return (
    <article className="card">
      <header>
        <h3>
          {card.zone_id} · {card.datetime.slice(0, 10)}
        </h3>
        <ConfidenceBadge score={card.confidence} reasons={card.confidence_reasons} />
      </header>
      <p className="summary">{card.summary}</p>
      <p>
        Clear pixels {formatNumber(card.valid_pixel_fraction === null ? null : card.valid_pixel_fraction * 100, 0)}% · mask
        agreement {formatNumber(card.mask_agreement, 2)}
      </p>
      <table>
        <thead>
          <tr>
            <th>Indicator</th>
            <th>Value</th>
            <th>Baseline</th>
            <th>Sigma</th>
            <th>Threshold</th>
            <th>Crossed</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.indicator}>
              <td>{row.indicator}</td>
              <td>
                {row.value.toFixed(3)} {row.unit}
              </td>
              <td>
                {row.baseline_mean.toFixed(3)} ± {formatNumber(row.baseline_std, 3)}
              </td>
              <td>{formatNumber(row.sigma, 2)}</td>
              <td>{row.threshold.toFixed(0)} sigma</td>
              <td>{row.crossed ? "yes" : "no"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>Thresholds crossed: {card.thresholds_crossed.join(", ") || "none"}</p>
      <p className="disclaimer-inline">{card.disclaimer}</p>
    </article>
  );
}
