import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import type { FeatureCollection, TrueColorFrame } from "../api/client";
import { anomalyStyle, boundsOf, fit, indicatorStyle, rangeOf } from "./layers";

export type MapLayers = {
  trueColor: boolean;
  turbidity: boolean;
  chlorophyll: boolean;
  anomaly: boolean;
};

type Props = {
  bodies: FeatureCollection | null;
  beforeZones: FeatureCollection | null;
  afterZones: FeatureCollection | null;
  beforeImage: TrueColorFrame | null;
  afterImage: TrueColorFrame | null;
  beforeLabel: string;
  afterLabel: string;
  layers: MapLayers;
  selectedId: string | null;
  focus: { lat: number; lon: number; token: number } | null;
  onSelectBody: (id: string) => void;
  onOutside: () => void;
};

export function MonitorMap({
  bodies,
  beforeZones,
  afterZones,
  beforeImage,
  afterImage,
  beforeLabel,
  afterLabel,
  layers,
  selectedId,
  focus,
  onSelectBody,
  onOutside,
}: Props) {
  const backRef = useRef<HTMLDivElement>(null);
  const frontRef = useRef<HTMLDivElement>(null);
  const maps = useRef<{ back: L.Map; front: L.Map } | null>(null);
  const [ready, setReady] = useState(false);
  const [cut, setCut] = useState(100);
  const selectRef = useRef(onSelectBody);
  const outsideRef = useRef(onOutside);
  selectRef.current = onSelectBody;
  outsideRef.current = onOutside;

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
    back.on("click", () => outsideRef.current());
    front.on("click", () => outsideRef.current());
    maps.current = { back, front };
    requestAnimationFrame(() => {
      back.invalidateSize();
      front.invalidateSize();
      setReady(true);
    });
    return () => {
      back.remove();
      front.remove();
      maps.current = null;
      setReady(false);
    };
  }, []);

  useEffect(() => {
    const pair = maps.current;
    if (!pair || !bodies) return;
    const union = boundsOf(bodies);
    const box = viewBox(bodies, selectedId);
    if (!union || !box) return;
    const padded = pad(union, 0.4);
    const limits = L.latLngBounds(
      [padded[1], padded[0]],
      [padded[3], padded[2]],
    );
    pair.back.setMaxBounds(limits);
    pair.front.setMaxBounds(limits);
    pair.back.invalidateSize();
    pair.front.invalidateSize();
    fit(pair.back, box);
    fit(pair.front, box);
  }, [bodies, ready, selectedId]);

  useEffect(() => {
    const pair = maps.current;
    if (!pair) return;
    drawBodies(pair.back, bodies, selectRef);
    drawBodies(pair.front, bodies, selectRef);
  }, [bodies, ready]);

  useEffect(() => {
    const pair = maps.current;
    if (!pair) return;
    drawImage(pair.back, layers.trueColor ? beforeImage : null);
    drawImage(pair.front, layers.trueColor ? afterImage : null);
    drawZones(pair.back, beforeZones, layers);
    drawZones(pair.front, afterZones, layers);
  }, [beforeZones, afterZones, beforeImage, afterImage, layers, ready]);

  useEffect(() => {
    const pair = maps.current;
    if (!pair || !focus) return;
    pair.back.flyTo([focus.lat, focus.lon], Math.max(pair.back.getZoom(), 13));
  }, [focus, ready]);

  useEffect(() => {
    const pair = maps.current;
    if (!pair) return;
    requestAnimationFrame(() => {
      pair.back.invalidateSize();
      pair.front.invalidateSize();
    });
  }, [beforeLabel, afterLabel, ready]);

  const swiping = beforeLabel !== afterLabel;

  return (
    <div className="monitor-map">
      <div ref={backRef} className="map-canvas" />
      <div className="swipe-front" style={{ clipPath: swiping ? `inset(0 ${100 - cut}% 0 0)` : "inset(0 0 0 0)", display: swiping ? "block" : "none" }}>
        <div ref={frontRef} className="map-canvas" />
      </div>
      {swiping ? (
        <label className="swipe-control">
          <span>
            {beforeLabel} / {afterLabel}
          </span>
          <input type="range" min={0} max={100} value={cut} onChange={(event) => setCut(Number(event.target.value))} />
        </label>
      ) : null}
    </div>
  );
}

const bodyLayers = new WeakMap<L.Map, L.GeoJSON>();
const zoneLayers = new WeakMap<L.Map, L.GeoJSON>();
const contourLayers = new WeakMap<L.Map, L.GeoJSON>();
const imageLayers = new WeakMap<L.Map, L.ImageOverlay>();

function createMap(node: HTMLDivElement): L.Map {
  const map = L.map(node, { zoomControl: true, minZoom: 2 }).setView([0.025, 0.03], 11);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 18,
  }).addTo(map);
  return map;
}

function drawBodies(map: L.Map, bodies: FeatureCollection | null, selectRef: { current: (id: string) => void }) {
  const previous = bodyLayers.get(map);
  if (previous) map.removeLayer(previous);
  if (!bodies) return;
  const layer = L.geoJSON(bodies as GeoJSON.FeatureCollection, {
    style: { color: "#083844", weight: 3, fillColor: "#1a7a8c", fillOpacity: 0.55 },
    onEachFeature: (feature, shape) => {
      const name = feature.properties?.name;
      if (typeof name === "string") {
        shape.bindTooltip(name, { permanent: true, direction: "center", className: "water-label" });
      }
      shape.on("click", (event) => {
        L.DomEvent.stopPropagation(event);
        const id = feature.properties?.id;
        if (typeof id === "string") selectRef.current(id);
      });
    },
  }).addTo(map);
  bodyLayers.set(map, layer);
}

function drawZones(map: L.Map, zones: FeatureCollection | null, layers: MapLayers) {
  const previous = zoneLayers.get(map);
  const previousContour = contourLayers.get(map);
  if (previous) map.removeLayer(previous);
  if (previousContour) map.removeLayer(previousContour);
  if (!zones) return;
  const values = (name: "turbidity" | "chlorophyll") =>
    zones.features.flatMap((feature) => {
      const means = feature.properties?.means as Record<string, number> | undefined;
      const value = means?.[name];
      return typeof value === "number" ? [value] : [];
    });
  const [turbidityLow, turbidityHigh] = rangeOf(values("turbidity"));
  const [chlorophyllLow, chlorophyllHigh] = rangeOf(values("chlorophyll"));
  const layer = L.geoJSON(zones as GeoJSON.FeatureCollection, {
    onEachFeature: (_feature, shape) => {
      shape.on("click", (event) => L.DomEvent.stopPropagation(event));
    },
    style: (feature) => {
      const properties = feature?.properties as Record<string, unknown> | undefined;
      if (layers.turbidity) return indicatorStyle(properties, "turbidity", turbidityLow, turbidityHigh);
      if (layers.chlorophyll) return indicatorStyle(properties, "chlorophyll", chlorophyllLow, chlorophyllHigh);
      return { color: "#102033", weight: 1, fillColor: "#1d4e89", fillOpacity: 0.25 };
    },
  }).addTo(map);
  zoneLayers.set(map, layer);
  if (layers.anomaly) {
    const contour = L.geoJSON(zones as GeoJSON.FeatureCollection, {
      onEachFeature: (_feature, shape) => {
        shape.on("click", (event) => L.DomEvent.stopPropagation(event));
      },
      style: (feature) => anomalyStyle(feature?.properties as Record<string, unknown> | undefined),
    }).addTo(map);
    contourLayers.set(map, contour);
  }
}

function drawImage(map: L.Map, frame: TrueColorFrame | null) {
  const previous = imageLayers.get(map);
  if (previous) map.removeLayer(previous);
  if (!frame) return;
  const overlay = L.imageOverlay(frame.url, frame.bounds, { opacity: 0.92 }).addTo(map);
  imageLayers.set(map, overlay);
}

function viewBox(bodies: FeatureCollection, selectedId: string | null): [number, number, number, number] | null {
  const selected = bodies.features.find((feature) => feature.properties?.id === selectedId);
  if (selected) return boundsOf({ features: [selected] });
  const union = boundsOf(bodies);
  if (!union) return null;
  const span = Math.max(union[2] - union[0], union[3] - union[1]);
  if (span > 0.3 && bodies.features[0]) return boundsOf({ features: [bodies.features[0]] });
  return union;
}

function pad(box: [number, number, number, number], fraction: number): [number, number, number, number] {
  const [west, south, east, north] = box;
  const width = Math.max(east - west, 0.02);
  const height = Math.max(north - south, 0.02);
  return [west - width * fraction, south - height * fraction, east + width * fraction, north + height * fraction];
}
