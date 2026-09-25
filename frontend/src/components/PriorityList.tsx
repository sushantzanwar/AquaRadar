import type { PrioritySite } from "../api/client";

export function PriorityList({ sites, formula }: { sites: PrioritySite[]; formula?: string }) {
  if (!sites.length) return <p className="muted">No sample sites. A zone appears here only after it is flagged.</p>;
  return (
    <div>
      {formula ? <p className="formula">{formula}</p> : null}
      <ol className="priority">
        {sites.map((site) => (
          <li key={site.zone_id}>
            <strong>
              {site.rank}. {site.zone_name}
            </strong>
            <span>
              {site.lat.toFixed(5)}, {site.lon.toFixed(5)}
            </span>
            <span>
              priority {site.priority.toFixed(3)} = severity {site.severity.toFixed(2)} × persistence {site.persistence.toFixed(2)} ×
              proximity {site.proximity.toFixed(2)}
            </span>
            <span className="muted">
              intake {site.distance_to_intake_m?.toFixed(0) ?? "n/a"} m · settlement {site.distance_to_settlement_m?.toFixed(0) ?? "n/a"} m
              · bump {site.severity_bump.toFixed(2)}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
