import type { FillLayerSpecification, StyleSpecification } from "maplibre-gl";

export const emptyStyle: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": "#d5e2e8" } }],
};

export const zoneFill: FillLayerSpecification["paint"] = {
  "fill-color": [
    "case",
    ["==", ["get", "flagged"], true],
    ["match", ["get", "severity_label"], "severe", "#7f1d1d", "warning", "#c2410c", "#a16207"],
    "#1d4e89",
  ],
  "fill-opacity": 0.78,
};

export const plumeOutline = {
  type: "circle" as const,
  paint: {
    "circle-radius": 14,
    "circle-color": "#7f1d1d",
    "circle-opacity": 0.35,
    "circle-stroke-width": 2,
    "circle-stroke-color": "#7f1d1d",
  },
};

export function boundsOf(collection: {
  features: { geometry: { coordinates: unknown } }[];
}): [number, number, number, number] | null {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  const visit = (coords: unknown) => {
    if (!Array.isArray(coords)) return;
    if (typeof coords[0] === "number" && typeof coords[1] === "number") {
      west = Math.min(west, coords[0]);
      east = Math.max(east, coords[0]);
      south = Math.min(south, coords[1]);
      north = Math.max(north, coords[1]);
      return;
    }
    coords.forEach(visit);
  };
  collection.features.forEach((feature) => visit(feature.geometry));
  if (!Number.isFinite(west)) return null;
  return [west, south, east, north];
}
