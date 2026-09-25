import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import type { FeatureCollection } from "../api/client";
import { boundsOf, emptyStyle, zoneFill } from "./layers";

type Props = {
  before: FeatureCollection | null;
  after: FeatureCollection | null;
  beforeLabel: string;
  afterLabel: string;
};

export function SwipeCompare({ before, after, beforeLabel, afterLabel }: Props) {
  const backRef = useRef<HTMLDivElement>(null);
  const frontRef = useRef<HTMLDivElement>(null);
  const maps = useRef<{ back: maplibregl.Map; front: maplibregl.Map } | null>(null);
  const [cut, setCut] = useState(55);

  useEffect(() => {
    if (!backRef.current || !frontRef.current || maps.current) return;
    const back = new maplibregl.Map({ container: backRef.current, style: emptyStyle, center: [0.03, 0.025], zoom: 10 });
    const front = new maplibregl.Map({ container: frontRef.current, style: emptyStyle, center: [0.03, 0.025], zoom: 10 });
    const add = (map: maplibregl.Map) => {
      map.on("load", () => {
        map.addSource("zones", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.addLayer({ id: "zones-fill", type: "fill", source: "zones", paint: zoneFill });
      });
    };
    add(back);
    add(front);
    let lock = false;
    const sync = (source: maplibregl.Map, target: maplibregl.Map) => {
      source.on("move", () => {
        if (lock) return;
        lock = true;
        target.jumpTo({ center: source.getCenter(), zoom: source.getZoom() });
        lock = false;
      });
    };
    sync(back, front);
    sync(front, back);
    maps.current = { back, front };
    return () => {
      back.remove();
      front.remove();
      maps.current = null;
    };
  }, []);

  useEffect(() => {
    paint(maps.current?.back, before);
    paint(maps.current?.front, after);
  }, [before, after]);

  return (
    <div className="swipe">
      <div ref={backRef} className="map-canvas" />
      <div className="swipe-front" style={{ clipPath: `inset(0 ${100 - cut}% 0 0)` }}>
        <div ref={frontRef} className="map-canvas" />
      </div>
      <label className="swipe-control">
        <span>
          {beforeLabel} / {afterLabel}
        </span>
        <input type="range" min={0} max={100} value={cut} onChange={(event) => setCut(Number(event.target.value))} />
      </label>
    </div>
  );
}

function paint(map: maplibregl.Map | undefined, zones: FeatureCollection | null) {
  if (!map || !map.isStyleLoaded() || !zones) return;
  const source = map.getSource("zones") as maplibregl.GeoJSONSource | undefined;
  source?.setData(zones as GeoJSON.FeatureCollection);
  const box = boundsOf(zones);
  if (box) map.fitBounds(box, { padding: 28, animate: false });
}
