import { useEffect, useRef } from "react";
import L from "leaflet";
import type { FeatureCollection } from "../api/client";
import { boundsOf, fit, zoneStyle } from "./layers";

type Props = {
  zones: FeatureCollection | null;
  onSelect: (zoneId: string) => void;
  plume?: { lon: number; lat: number } | null;
};

export function AnomalyMap({ zones, onSelect, plume }: Props) {
  const node = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const zonesLayer = useRef<L.GeoJSON | null>(null);
  const plumeLayer = useRef<L.CircleMarker | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!node.current || mapRef.current) return;
    const map = L.map(node.current, { zoomControl: true }).setView([0.025, 0.03], 11);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(map);
    mapRef.current = map;
    requestAnimationFrame(() => map.invalidateSize());
    return () => {
      map.remove();
      mapRef.current = null;
      zonesLayer.current = null;
      plumeLayer.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !zones) return;
    if (zonesLayer.current) map.removeLayer(zonesLayer.current);
    zonesLayer.current = L.geoJSON(zones as GeoJSON.FeatureCollection, {
      style: (feature) => zoneStyle(feature?.properties as Record<string, unknown> | undefined),
      onEachFeature: (feature, layer) => {
        layer.on("click", () => {
          const id = feature.properties?.id;
          if (typeof id === "string") onSelectRef.current(id);
        });
      },
    }).addTo(map);
    const box = boundsOf(zones);
    if (box) fit(map, box);
  }, [zones]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (plumeLayer.current) {
      map.removeLayer(plumeLayer.current);
      plumeLayer.current = null;
    }
    if (!plume) return;
    plumeLayer.current = L.circleMarker([plume.lat, plume.lon], {
      radius: 14,
      color: "#7f1d1d",
      weight: 2,
      fillColor: "#7f1d1d",
      fillOpacity: 0.45,
    }).addTo(map);
  }, [plume]);

  return <div ref={node} className="map-canvas" />;
}
