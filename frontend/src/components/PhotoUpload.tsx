import { useState, type FormEvent } from "react";
import { submitPhoto, type CreditVerdict } from "../api/client";

export function PhotoUpload({ waterBodyId, onDone }: { waterBodyId: string; onDone: () => void }) {
  const [lon, setLon] = useState("0.03");
  const [lat, setLat] = useState("0.04");
  const [note, setNote] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [verdict, setVerdict] = useState<CreditVerdict | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Choose a photo");
      return;
    }
    const form = new FormData();
    form.set("water_body_id", waterBodyId);
    form.set("lon", lon);
    form.set("lat", lat);
    form.set("note", note);
    form.set("photo", file);
    setError(null);
    try {
      const result = await submitPhoto(form);
      setVerdict(result);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  }

  return (
    <form onSubmit={submit} className="stack">
      <label>
        Photo
        <input type="file" accept="image/*" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
      </label>
      <label>
        Longitude
        <input value={lon} onChange={(event) => setLon(event.target.value)} />
      </label>
      <label>
        Latitude
        <input value={lat} onChange={(event) => setLat(event.target.value)} />
      </label>
      <label>
        Note
        <input value={note} onChange={(event) => setNote(event.target.value)} />
      </label>
      <button type="submit">Submit report</button>
      {error ? <p className="error">{error}</p> : null}
      {verdict ? (
        <p>
          {verdict.accepted ? "Accepted" : "Rejected"} · {verdict.reason} · {verdict.credits_awarded} credits · total{" "}
          {verdict.total_credits}
          {verdict.zone_id ? ` · zone ${verdict.zone_id}` : ""} · bump {verdict.severity_bump.toFixed(2)}
        </p>
      ) : null}
    </form>
  );
}
