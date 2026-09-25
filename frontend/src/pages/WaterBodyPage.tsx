import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  getAlerts,
  getAnomalies,
  getEvidence,
  getPriority,
  getTrends,
  getZones,
  type AlertFeed,
  type AnomalyResponse,
  type EvidenceCard as Card,
  type PriorityList,
  type SceneIndex,
  type StressResponse,
  type TrendSeries,
} from "../api/client";
import { AlertFeed as Feed } from "../components/AlertFeed";
import { AssistantPanel } from "../components/AssistantPanel";
import { EvidenceCard } from "../components/EvidenceCard";
import { PriorityList as Samples } from "../components/PriorityList";
import { StressControls } from "../components/StressControls";
import { TrendChart } from "../components/TrendChart";
import { AnomalyMap } from "../map/AnomalyMap";
import { SwipeCompare } from "../map/SwipeCompare";

export function WaterBodyPage({ scenes }: { scenes: SceneIndex | null }) {
  const { id = "" } = useParams();
  const body = scenes?.water_bodies.find((item) => item.id === id);
  const dates = body?.dates.map((item) => item.date) ?? [];
  const [date, setDate] = useState("");
  const [compare, setCompare] = useState("");
  const [zones, setZones] = useState<Awaited<ReturnType<typeof getZones>> | null>(null);
  const [anomalies, setAnomalies] = useState<AnomalyResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertFeed | null>(null);
  const [priority, setPriority] = useState<PriorityList | null>(null);
  const [zoneId, setZoneId] = useState<string | undefined>();
  const [card, setCard] = useState<Card | null>(null);
  const [trend, setTrend] = useState<TrendSeries | null>(null);
  const [indicator, setIndicator] = useState("turbidity");
  const [error, setError] = useState<string | null>(null);
  const [plume, setPlume] = useState<{ lon: number; lat: number } | null>(null);

  useEffect(() => {
    if (!dates.length) return;
    setDate((current) => current || dates[dates.length - 1]);
    setCompare((current) => current || dates[0]);
  }, [dates]);

  useEffect(() => {
    if (!id || !date) return;
    setError(null);
    setPlume(null);
    Promise.all([getZones(id, date, compare || undefined), getAnomalies(id, date), getAlerts(id, date), getPriority(id, date)])
      .then(([map, anomaly, feed, ranked]) => {
        setZones(map);
        setAnomalies(anomaly);
        setAlerts(feed);
        setPriority(ranked);
        setCard(null);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Load failed"));
  }, [id, date, compare]);

  useEffect(() => {
    if (!id || !zoneId) return;
    getEvidence(id, zoneId, date)
      .then(setCard)
      .catch(() => setCard(null));
    getTrends(id, zoneId, indicator)
      .then(setTrend)
      .catch(() => setTrend(null));
  }, [id, zoneId, date, indicator]);

  function applyStress(result: StressResponse) {
    if (result.anomalies) setAnomalies(result.anomalies);
    if (result.alerts) setAlerts(result.alerts);
    if (result.priority) setPriority(result.priority);
    setCard(result.evidence[0] ?? null);
    setError(result.status === "ok" ? null : result.reason);
  }

  if (!body) return <p className="muted">Unknown water body.</p>;

  return (
    <div className="workspace">
      <div className="map-column">
        <div className="toolbar">
          <label>
            Date
            <select value={date} onChange={(event) => setDate(event.target.value)}>
              {body.dates.map((item) => (
                <option key={item.date} value={item.date}>
                  {item.date} · {item.status}
                </option>
              ))}
            </select>
          </label>
          <label>
            Compare
            <select value={compare} onChange={(event) => setCompare(event.target.value)}>
              {body.dates.map((item) => (
                <option key={item.date} value={item.date}>
                  {item.date}
                </option>
              ))}
            </select>
          </label>
          <label>
            Trend
            <select value={indicator} onChange={(event) => setIndicator(event.target.value)}>
              <option value="turbidity">turbidity</option>
              <option value="chlorophyll">chlorophyll</option>
              <option value="transparency">transparency</option>
              <option value="extent">extent</option>
            </select>
          </label>
        </div>
        {error ? <p className="error">{error}</p> : null}
        <p className="muted">
          Scene status {anomalies?.status || "…"}
          {anomalies?.reason ? ` · ${anomalies.reason}` : ""} · extent {anomalies?.scene_extent_m2 ?? "n/a"} m²
        </p>
        <AnomalyMap zones={zones?.date ?? null} onSelect={setZoneId} plume={plume} />
        <SwipeCompare before={zones?.compare ?? null} after={zones?.date ?? null} beforeLabel={compare} afterLabel={date} />
      </div>
      <aside className="side">
        <EvidenceCard card={card} />
        <TrendChart series={trend} />
        <h3>Alerts</h3>
        <Feed alerts={alerts?.alerts ?? []} status={alerts?.status} />
        <h3>Sample here first</h3>
        <Samples sites={priority?.sites ?? []} formula={priority?.sites[0]?.formula} />
        <AssistantPanel waterBodyId={id} zoneId={zoneId} date={date} />
        <StressControls
          waterBodyId={id}
          date={date}
          onResult={(result, lon, lat) => {
            applyStress(result);
            setPlume({ lon, lat });
          }}
        />
      </aside>
    </div>
  );
}
