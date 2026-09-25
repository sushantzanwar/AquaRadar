import { useState, type FormEvent } from "react";
import { runStress, type StressResponse } from "../api/client";

type Props = {
  waterBodyId: string;
  date: string;
  onResult: (result: StressResponse, lon: number, lat: number) => void;
};

export function StressControls({ waterBodyId, date, onResult }: Props) {
  const [lon, setLon] = useState("0.03");
  const [lat, setLat] = useState("0.04");
  const [radius, setRadius] = useState("400");
  const [indicator, setIndicator] = useState("turbidity");
  const [magnitude, setMagnitude] = useState("0.2");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const result = await runStress({
        water_body_id: waterBodyId,
        date,
        lon: Number(lon),
        lat: Number(lat),
        radius_m: Number(radius),
        indicator,
        magnitude: Number(magnitude),
      });
      onResult(result, Number(lon), Number(lat));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stress run failed");
    }
  }

  return (
    <form onSubmit={submit} className="stack">
      <h3>Stress-test plume</h3>
      <p className="muted">Paints a copy of the cached scene. The original GeoTIFFs stay unchanged.</p>
      <label>
        Longitude
        <input value={lon} onChange={(event) => setLon(event.target.value)} />
      </label>
      <label>
        Latitude
        <input value={lat} onChange={(event) => setLat(event.target.value)} />
      </label>
      <label>
        Radius (m)
        <input value={radius} onChange={(event) => setRadius(event.target.value)} />
      </label>
      <label>
        Indicator
        <select value={indicator} onChange={(event) => setIndicator(event.target.value)}>
          <option value="turbidity">turbidity</option>
          <option value="chlorophyll">chlorophyll</option>
          <option value="transparency">transparency</option>
        </select>
      </label>
      <label>
        Magnitude
        <input value={magnitude} onChange={(event) => setMagnitude(event.target.value)} />
      </label>
      <button type="submit">Run pipeline</button>
      {error ? <p className="error">{error}</p> : null}
    </form>
  );
}
