"""AOI clipping and vector geometry used by the pipeline and photo checks."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def apply_aoi(valid: np.ndarray, inside: np.ndarray) -> np.ndarray:
    return valid & inside


def load_features(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        import geopandas as gpd

        frame = gpd.read_file(path)
        return json.loads(frame.to_json())["features"]
    except Exception:
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data.get("features", []))


def feature_id(feature: dict, fallback: str) -> str:
    props = feature.get("properties") or {}
    return str(props.get("id") or props.get("name") or fallback)


def feature_name(feature: dict, fallback: str) -> str:
    props = feature.get("properties") or {}
    return str(props.get("name") or props.get("id") or fallback)


def _rings(geometry: dict) -> list[list[list[float]]]:
    kind = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if kind == "Polygon":
        return coords
    if kind == "MultiPolygon":
        rings = []
        for polygon in coords:
            rings.extend(polygon)
        return rings
    return []


def ring_centroid(ring: list[list[float]]) -> tuple[float, float]:
    points = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    if not points:
        return 0.0, 0.0
    lon = sum(point[0] for point in points) / len(points)
    lat = sum(point[1] for point in points) / len(points)
    return lon, lat


def geometry_point(geometry: dict) -> tuple[float, float] | None:
    kind = geometry.get("type")
    if kind == "Point":
        lon, lat = geometry["coordinates"][:2]
        return float(lon), float(lat)
    rings = _rings(geometry)
    if not rings:
        return None
    return ring_centroid(rings[0])


def _point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    count = len(ring)
    if count < 3:
        return False
    j = count - 1
    for i in range(count):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-15) + xi
        if intersects:
            inside = not inside
        j = i
    return inside


def point_in_geometry(lon: float, lat: float, geometry: dict) -> bool:
    kind = geometry.get("type")
    if kind == "Point":
        return False
    if kind == "Polygon":
        rings = geometry.get("coordinates") or []
        if not rings or not _point_in_ring(lon, lat, rings[0]):
            return False
        return not any(_point_in_ring(lon, lat, hole) for hole in rings[1:])
    if kind == "MultiPolygon":
        return any(point_in_geometry(lon, lat, {"type": "Polygon", "coordinates": poly}) for poly in geometry["coordinates"])
    return False


def containing_feature(features: list[dict], lon: float, lat: float) -> dict | None:
    for feature in features:
        if point_in_geometry(lon, lat, feature.get("geometry") or {}):
            return feature
    return None


def rasterize_aoi(features: list[dict], shape: tuple[int, int], transform) -> np.ndarray:
    from rasterio.features import rasterize

    shapes = [feature["geometry"] for feature in features if feature.get("geometry")]
    if not shapes:
        return np.zeros(shape, dtype=bool)
    burned = rasterize(shapes, out_shape=shape, transform=transform, fill=0, default_value=1, dtype="uint8")
    return burned.astype(bool)
