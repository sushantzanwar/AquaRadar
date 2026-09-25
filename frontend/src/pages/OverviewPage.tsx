import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  getAlertEvidence,
  getMonitored,
  getSeriesAlerts,
  getTimeSeries,
  getTrueColor,
  getZones,
  type AlertEvidenceCard as SeriesCard,
  type FeatureCollection,
  type SceneIndex,
  type SeriesAlert,
  type TrueColorFrame,
  type WaterBodySeries,
} from "../api/client";
import { AlertEvidenceCard } from "../components/AlertEvidenceCard";
import { HealthPanel } from "../components/HealthPanel";
import { MonitorMap, type MapLayers } from "../map/MonitorMap";

const EMPTY_LAYERS: MapLayers = { trueColor: true, turbidity: false, chlorophyll: false, anomaly: true };

export function OverviewPage({ scenes }: { scenes: SceneIndex | null }) {
  const [bodies, setBodies] = useState<FeatureCollection | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [date, setDate] = useState("");
  const [compare, setCompare] = useState("");
  const [layers, setLayers] = useState<MapLayers>(EMPTY_LAYERS);
  const [beforeZones, setBeforeZones] = useState<FeatureCollection | null>(null);
  const [afterZones, setAfterZones] = useState<FeatureCollection | null>(null);
  const [beforeImage, setBeforeImage] = useState<TrueColorFrame | null>(null);
  const [afterImage, setAfterImage] = useState<TrueColorFrame | null>(null);
  const [series, setSeries] = useState<WaterBodySeries | null>(null);
  const [alerts, setAlerts] = useState<SeriesAlert[]>([]);
  const [card, setCard] = useState<SeriesCard | null>(null);
  const [focus, setFocus] = useState<{ lat: number; lon: number; token: number } | null>(null);
  const [outside, setOutside] = useState(false);
  const [requested, setRequested] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const heldImages = useRef<string[]>([]);

  const body = scenes?.water_bodies.find((item) => item.id === selected) ?? null;
  const dates = body?.dates.map((item) => item.date) ?? [];

  useEffect(() => {
    getMonitored()
      .then(setBodies)
      .catch(() => setBodies(null));
    getSeriesAlerts()
      .then((list) => setAlerts(list.alerts))
      .catch(() => setAlerts([]));
  }, []);

  useEffect(() => {
    if (!dates.length) return;
    setDate((current) => (dates.includes(current) ? current : dates[dates.length - 1]));
    setCompare((current) => (dates.includes(current) ? current : dates[0]));
  }, [dates]);

  useEffect(() => {
    if (!selected || !date) {
      setBeforeZones(null);
      setAfterZones(null);
      return;
    }
    const other = compare && compare !== date ? compare : undefined;
    getZones(selected, date, other)
      .then((payload) => {
        setAfterZones(payload.date);
        setBeforeZones(other ? payload.compare ?? null : payload.date);
      })
      .catch(() => {
        setAfterZones(null);
        setBeforeZones(null);
      });
  }, [selected, date, compare]);

  useEffect(() => {
    if (!selected) {
      setSeries(null);
      return;
    }
    getTimeSeries(selected)
      .then(setSeries)
      .catch(() => setSeries(null));
  }, [selected]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!layers.trueColor || !selected || !date) {
        setBeforeImage(null);
        setAfterImage(null);
        setNote(null);
        return;
      }
      const after = await getTrueColor(selected, date);
      const before = compare && compare !== date ? await getTrueColor(selected, compare) : after;
      if (cancelled) {
        if (after) URL.revokeObjectURL(after.url);
        if (before && before !== after) URL.revokeObjectURL(before.url);
        return;
      }
      heldImages.current.forEach((url) => URL.revokeObjectURL(url));
      heldImages.current = [after, before].filter((frame): frame is TrueColorFrame => frame !== null).map((frame) => frame.url);
      if (before === after && after) heldImages.current = [after.url];
      setAfterImage(after);
      setBeforeImage(before);
      setNote(after ? null : "True-color Sentinel-2 render is not in the local cache for this date.");
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [layers.trueColor, selected, date, compare]);

  function toggle(name: keyof MapLayers) {
    setLayers((current) => ({ ...current, [name]: !current[name] }));
  }

  function openAlert(alert: SeriesAlert) {
    setSelected(alert.water_body_id);
    setOutside(false);
    if (alert.lat !== null && alert.lon !== null) {
      setFocus({ lat: alert.lat, lon: alert.lon, token: Date.now() });
    }
    getAlertEvidence(alert.id)
      .then(setCard)
      .catch(() => setCard(null));
  }

  const bodyAlerts = alerts.filter((alert) => alert.water_body_id === selected);

  return (
    <div className="workspace monitor">
      <div className="map-column">
        <div className="toolbar">
          <label>
            Date
            <select value={date} onChange={(event) => setDate(event.target.value)} disabled={!body}>
              {dates.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label>
            Compare
            <select value={compare} onChange={(event) => setCompare(event.target.value)} disabled={!body}>
              {dates.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          {(["trueColor", "turbidity", "chlorophyll", "anomaly"] as const).map((name) => (
            <label key={name} className="check">
              <input type="checkbox" checked={layers[name]} onChange={() => toggle(name)} />
              {name === "trueColor" ? "true-color" : name === "chlorophyll" ? "chl-a heatmap" : name === "turbidity" ? "turbidity heatmap" : "anomaly contours"}
            </label>
          ))}
        </div>
        {note ? <p className="muted">{note}</p> : null}
        <div className="monitor-stage">
          <MonitorMap
            bodies={bodies}
            beforeZones={beforeZones}
            afterZones={afterZones}
            beforeImage={beforeImage}
            afterImage={afterImage}
            beforeLabel={compare || date}
            afterLabel={date}
            layers={layers}
            focus={focus}
            onSelectBody={(id) => {
              setSelected(id);
              setOutside(false);
              setCard(null);
            }}
            onOutside={() => setOutside(true)}
          />
          {outside ? (
            <div className="map-toast" role="status">
              <strong>Not currently monitored</strong>
              <button type="button" onClick={() => setRequested(true)} disabled={requested}>
                {requested ? "Request recorded" : "Request monitoring"}
              </button>
            </div>
          ) : null}
        </div>
      </div>
      <aside className="side">
        <HealthPanel
          body={body}
          series={series}
          alerts={bodyAlerts}
          onAlert={openAlert}
          outside={outside}
          requested={requested}
          onRequest={() => setRequested(true)}
        />
        <article className="card">
          <h3>Alerts feed</h3>
          {alerts.length ? (
            <ul className="feed">
              {alerts.map((alert) => (
                <li key={alert.id}>
                  <button type="button" onClick={() => openAlert(alert)}>
                    {alert.severity} · {alert.water_body_id} · {alert.zone_id}
                  </button>
                  <p className="muted">
                    {alert.datetime} · {alert.indicators.join(", ")}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No active series alerts. Alerts appear when stored zone series cross the sigma threshold.</p>
          )}
        </article>
        <AlertEvidenceCard card={card} />
        {body ? <p><Link to={`/water/${body.id}`}>Open the full water-body page</Link></p> : null}
      </aside>
    </div>
  );
}
