import type { SeriesAlert, WaterBody, WaterBodySeries } from "../api/client";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { Sparkline } from "./Sparkline";
import { TrendChart } from "./TrendChart";

type Props = {
  body: WaterBody | null;
  series: WaterBodySeries | null;
  alerts: SeriesAlert[];
  onAlert: (alert: SeriesAlert) => void;
  outside: boolean;
  requested: boolean;
  onRequest: () => void;
};

export function HealthPanel({ body, series, alerts, onAlert, outside, requested, onRequest }: Props) {
  if (!body) {
    return (
      <section className="card">
        <h2>Monitored water</h2>
        <p className="muted">Click a water body on the map for its health overview.</p>
        {outside ? <OutsideNotice requested={requested} onRequest={onRequest} /> : null}
      </section>
    );
  }
  const latest = body.dates[body.dates.length - 1];
  const extent = series?.indicators.find((item) => item.indicator === "extent");
  const extentPoints = extent ? meanSeries(extent) : [];
  return (
    <section className="stack">
      <article className="card">
        <header>
          <h2>{body.name}</h2>
          <ConfidenceBadge score={body.confidence} reasons={body.confidence_reasons} />
        </header>
        <p>
          Status <span className={`badge status-${latest?.status || "missing"}`}>{latest?.status || "unknown"}</span>
          {latest ? ` · ${latest.date}` : ""}
        </p>
        <div className="sparks">
          {["turbidity", "chlorophyll", "transparency"].map((name) => {
            const indicator = series?.indicators.find((item) => item.indicator === name);
            const points = indicator ? meanSeries(indicator) : [];
            return <Sparkline key={name} label={name} unit={indicator?.unit || "index"} values={points.map((point) => point.value)} />;
          })}
        </div>
        <TrendChart
          series={
            extent
              ? {
                  confidence: series?.confidence ?? body.confidence,
                  confidence_reasons: series?.confidence_reasons ?? body.confidence_reasons,
                  lab_verification_required: true,
                  disclaimer: series?.disclaimer ?? body.disclaimer,
                  zone_id: "all zones",
                  indicator: "extent",
                  points: extentPoints.map((point) => ({
                    date: point.date,
                    value: point.value,
                    baseline_mean: null,
                    baseline_std: null,
                    status: "ok",
                  })),
                }
              : null
          }
        />
        <p className="disclaimer-inline">{body.disclaimer}</p>
      </article>
      <article className="card">
        <h3>Active alerts</h3>
        {alerts.length ? (
          <ul className="feed">
            {alerts.map((alert) => (
              <li key={alert.id}>
                <button type="button" onClick={() => onAlert(alert)}>
                  {alert.severity} · {alert.zone_id} · {alert.indicators.join(", ")}
                </button>
                <p className="muted">{alert.affected_region}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No active series alerts.</p>
        )}
      </article>
      {outside ? <OutsideNotice requested={requested} onRequest={onRequest} /> : null}
    </section>
  );
}

function OutsideNotice({ requested, onRequest }: { requested: boolean; onRequest: () => void }) {
  return (
    <article className="card toast" role="status">
      <h3>Not currently monitored</h3>
      <p>That location is outside the configured water bodies.</p>
      <button type="button" onClick={onRequest} disabled={requested}>
        {requested ? "Request recorded" : "Request monitoring"}
      </button>
    </article>
  );
}

function meanSeries(indicator: WaterBodySeries["indicators"][number]) {
  const buckets = new Map<string, number[]>();
  for (const zone of indicator.zones) {
    for (const point of zone.points) {
      const values = buckets.get(point.date) ?? [];
      values.push(point.value);
      buckets.set(point.date, values);
    }
  }
  return [...buckets.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([date, values]) => ({ date, value: values.reduce((sum, value) => sum + value, 0) / values.length }));
}
