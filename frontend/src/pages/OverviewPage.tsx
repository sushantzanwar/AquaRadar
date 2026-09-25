import { Link } from "react-router-dom";
import type { SceneIndex } from "../api/client";
import { ConfidenceBadge } from "../components/ConfidenceBadge";

export function OverviewPage({ scenes }: { scenes: SceneIndex | null }) {
  if (!scenes) return <p className="muted">Loading water bodies…</p>;
  return (
    <section className="overview">
      {scenes.water_bodies.map((body) => (
        <article key={body.id} className="card">
          <header>
            <h2>
              <Link to={`/water/${body.id}`}>{body.name}</Link>
            </h2>
            <ConfidenceBadge score={body.confidence} reasons={body.confidence_reasons} />
          </header>
          <ul>
            {body.dates.map((date) => (
              <li key={date.date}>
                {date.date} · {date.status}
                {date.reason ? ` · ${date.reason}` : ""}
              </li>
            ))}
          </ul>
          {body.latest_alert ? (
            <p>
              Latest alert: {body.latest_alert.severity} {body.latest_alert.indicator} at {body.latest_alert.affected_region}
            </p>
          ) : (
            <p className="muted">No alert on the latest usable date.</p>
          )}
        </article>
      ))}
    </section>
  );
}
