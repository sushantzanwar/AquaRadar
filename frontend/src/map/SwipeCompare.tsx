import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import type { FeatureCollection } from "../api/client";
import { boundsOf, fit, zoneStyle } from "./layers";

type Props = {
  before: FeatureCollection | null;
  after: FeatureCollection | null;
  beforeLabel: string;
  afterLabel: string;
};

export function SwipeCompare({ before, after, beforeLabel, afterLabel }: Props) {
  const backRef = useRef<HTMLDivElement>(null);
  const frontRef = useRef<HTMLDivElement>(null);
  const maps = useRef<{ back: L.Map; front: L.Map } | null>(null);
  const layers = useRef<Map<L.Map, L.GeoJSON>>(new Map());
  const [cut, setCut] = useState(55);
  const beforeRef = useRef(before);
  const afterRef = useRef(after);
  beforeRef.current = before;
  afterRef.current = after;

  useEffect(() => {
    if (!backRef.current || !frontRef.current || maps.current) return;
    const back = createMap(backRef.current);
    const front = createMap(frontRef.current);
    let lock = false;
    const sync = (source: L.Map, target: L.Map) => {
      source.on("move", () => {
        if (lock) return;
        lock = true;
        target.setView(source.getCenter(), source.getZoom(), { animate: false });
        lock = false;
      });
    };
    sync(back, front);
    sync(front, back);
    maps.current = { back, front };
    paint(back, beforeRef.current, layers.current);
    paint(front, afterRef.current, layers.current);
    requestAnimationFrame(() => {
      back.invalidateSize();
      front.invalidateSize();
    });
    return () => {
      back.remove();
      front.remove();
      maps.current = null;
      layers.current.clear();
    };
  }, []);

  useEffect(() => {
    if (!maps.current) return;
    paint(maps.current.back, before, layers.current);
    paint(maps.current.front, after, layers.current);
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

function createMap(node: HTMLDivElement): L.Map {
  const map = L.map(node, { zoomControl: true }).setView([0.025, 0.03], 11);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 18,
  }).addTo(map);
  return map;
}

function paint(map: L.Map, zones: FeatureCollection | null, layers: Map<L.Map, L.GeoJSON>) {
  if (!zones) return;
  const previous = layers.get(map);
  if (previous) map.removeLayer(previous);
  const layer = L.geoJSON(zones as GeoJSON.FeatureCollection, {
    style: (feature) => zoneStyle(feature?.properties as Record<string, unknown> | undefined),
  }).addTo(map);
  layers.set(map, layer);
  const box = boundsOf(zones);
  if (box) fit(map, box);
}
