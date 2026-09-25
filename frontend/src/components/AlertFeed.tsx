import type { Alert } from "../api/client";
import { ConfidenceBadge } from "./ConfidenceBadge";

export function AlertFeed({ alerts, status }: { alerts: Alert[]; status?: string }) {
  if (!alerts.length) return <p className="muted">No alerts for this date ({status || "no flags"}).</p>;
  return (
    <ul className="feed">
      {alerts.map((alert) => (
        <li key={alert.alert_id}>
          <strong>
            {alert.severity} · {alert.indicator}
          </strong>
          <ConfidenceBadge score={alert.confidence} reasons={alert.confidence_reasons} />
          <p>{alert.template}</p>
          {alert.polished_summary ? <p className="polish">{alert.polished_summary}</p> : null}
          <p className="muted">
            {alert.location} · {alert.affected_region} · {alert.datetime} · {alert.narrative_source}
          </p>
        </li>
      ))}
    </ul>
  );
}
