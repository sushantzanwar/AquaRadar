import type { PathOptions } from "leaflet";

export function zoneStyle(properties: Record<string, unknown> | null | undefined): PathOptions {
  const flagged = properties?.flagged === true;
  const severity = properties?.severity_label;
  let fill = "#1d4e89";
  if (flagged && severity === "severe") fill = "#7f1d1d";
  else if (flagged && severity === "warning") fill = "#c2410c";
  else if (flagged) fill = "#a16207";
  return { color: "#102033", weight: 1.2, fillColor: fill, fillOpacity: 0.78 };
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
  collection.features.forEach((feature) => visit(feature.geometry));
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
