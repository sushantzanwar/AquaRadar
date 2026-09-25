"""Lon/lat centroid and polygon for one grid zone on an indicator raster."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

_ZONE_ID = re.compile(r"^r(\d+)c(\d+)$")


def zone_location(raster_path: Path, zone_id: str, n_rows: int, n_cols: int) -> tuple[float, float, dict] | None:
    """Return (lat, lon, GeoJSON polygon) for a zone cell, or None when the grid is unknown."""
    match = _ZONE_ID.fullmatch(zone_id)
    if match is None or not raster_path.is_file() or n_rows < 1 or n_cols < 1:
        return None
    row = int(match.group(1))
    col = int(match.group(2))
    if row >= n_rows or col >= n_cols:
        return None
    import rasterio
    from rasterio.warp import transform as warp_transform

    with rasterio.open(raster_path) as source:
        if source.crs is None:
            return None
        height, width = source.height, source.width
        row_edges = np.linspace(0, height, n_rows + 1).astype(int)
        col_edges = np.linspace(0, width, n_cols + 1).astype(int)
        row_start, row_stop = int(row_edges[row]), int(row_edges[row + 1])
        col_start, col_stop = int(col_edges[col]), int(col_edges[col + 1])
        if row_stop <= row_start or col_stop <= col_start:
            return None
        corners = (
            (col_start, row_start),
            (col_stop, row_start),
            (col_stop, row_stop),
            (col_start, row_stop),
        )
        xs, ys = zip(*(source.transform @ corner for corner in corners))
        lons, lats = warp_transform(source.crs, "EPSG:4326", list(xs), list(ys))
    ring = [[float(lon), float(lat)] for lon, lat in zip(lons, lats)]
    ring.append(ring[0])
    polygon = {"type": "Polygon", "coordinates": [ring]}
    lat = float(sum(lats) / len(lats))
    lon = float(sum(lons) / len(lons))
    return lat, lon, polygon
