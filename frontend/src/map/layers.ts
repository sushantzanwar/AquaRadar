import type { PathOptions } from "leaflet";

export function heatmapColor(value: number, low: number, high: number): string {
  const span = high - low || 1;
  const t = Math.max(0, Math.min(1, (value - low) / span));
  const red = Math.round(40 + t * 190);
  const green = Math.round(150 - t * 110);
  const blue = Math.round(170 - t * 140);
  return `rgb(${red}, ${green}, ${blue})`;
}

export function rangeOf(values: number[]): [number, number] {
  if (!values.length) return [0, 1];
  return [Math.min(...values), Math.max(...values)];
}

export function zoneStyle(properties: Record<string, unknown> | null | undefined): PathOptions {
  const flagged = properties?.flagged === true;
  const severity = properties?.severity_label;
  let fill = "#1d4e89";
  if (flagged && severity === "severe") fill = "#7f1d1d";
  else if (flagged && severity === "warning") fill = "#c2410c";
  else if (flagged) fill = "#a16207";
  return { color: "#102033", weight: 1.2, fillColor: fill, fillOpacity: 0.78 };
}

export function indicatorStyle(
  properties: Record<string, unknown> | null | undefined,
  indicator: "turbidity" | "chlorophyll",
  low: number,
  high: number,
): PathOptions {
  const means = properties?.means as Record<string, number> | undefined;
  const value = means?.[indicator];
  if (typeof value !== "number" || Number.isNaN(value)) {
    return { color: "#102033", weight: 1, fillColor: "#94a3b8", fillOpacity: 0.35 };
  }
  return { color: "#102033", weight: 1, fillColor: heatmapColor(value, low, high), fillOpacity: 0.72 };
}

export function anomalyStyle(properties: Record<string, unknown> | null | undefined): PathOptions {
  const flagged = properties?.flagged === true;
  return {
    color: flagged ? "#7f1d1d" : "#1d4e89",
    weight: flagged ? 3 : 1,
    dashArray: flagged ? "6 4" : undefined,
    fillOpacity: 0,
  };
}

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
  collection.features.forEach((feature) => visit(feature.geometry?.coordinates));
  if (!Number.isFinite(west)) return null;
  return [west, south, east, north];
}

export function fit(map: import("leaflet").Map, box: [number, number, number, number]) {
  const [west, south, east, north] = box;
  map.fitBounds(
    [
      [south, west],
      [north, east],
    ],
    { padding: [28, 28] },
  );
}
