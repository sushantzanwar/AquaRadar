import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import type { FeatureCollection } from "../api/client";
import { boundsOf, emptyStyle, zoneFill } from "./layers";

type Props = {
  zones: FeatureCollection | null;
  onSelect: (zoneId: string) => void;
  plume?: { lon: number; lat: number } | null;
};

export function AnomalyMap({ zones, onSelect, plume }: Props) {
  const node = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!node.current || mapRef.current) return;
    const map = new maplibregl.Map({ container: node.current, style: emptyStyle, center: [0.03, 0.025], zoom: 10 });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", () => {
      map.addSource("zones", { type: "geojson", data: emptyCollection() });
      map.addLayer({ id: "zones-fill", type: "fill", source: "zones", paint: zoneFill });
      map.addLayer({
        id: "zones-line",
        type: "line",
        source: "zones",
        paint: { "line-color": "#102033", "line-width": 1.2 },
      });
      map.addSource("plume", { type: "geojson", data: emptyCollection() });
      map.addLayer({
        id: "plume",
        type: "circle",
        source: "plume",
        paint: { "circle-radius": 16, "circle-color": "#7f1d1d", "circle-opacity": 0.45 },
      });
      map.on("click", "zones-fill", (event) => {
        const id = event.features?.[0]?.properties?.id;
        if (typeof id === "string") onSelectRef.current(id);
      });
      map.on("mouseenter", "zones-fill", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "zones-fill", () => {
        map.getCanvas().style.cursor = "";
      });
    });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded() || !zones) return;
    const source = map.getSource("zones") as maplibregl.GeoJSONSource | undefined;
    source?.setData(zones as GeoJSON.FeatureCollection);
    const box = boundsOf(zones);
    if (box) map.fitBounds(box, { padding: 28, animate: false });
  }, [zones]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const source = map.getSource("plume") as maplibregl.GeoJSONSource | undefined;
    const data = plume
      ? {
          type: "FeatureCollection" as const,
          features: [
            {
              type: "Feature" as const,
              properties: {},
              geometry: { type: "Point" as const, coordinates: [plume.lon, plume.lat] },
            },
          ],
        }
      : emptyCollection();
    source?.setData(data);
  }, [plume]);

  return <div ref={node} className="map-canvas" />;
}

function emptyCollection(): GeoJSON.FeatureCollection {
  return { type: "FeatureCollection", features: [] };
}
