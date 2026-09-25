"""True-color PNG from cached Sentinel-2 blue, green, and red bands."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from aquawatch.geo.catalog import resolve_band


def true_color_png(scene_dir: Path) -> tuple[bytes, tuple[float, float, float, float]] | None:
    """Return PNG bytes and west, south, east, north in longitude/latitude.

    None when the red, green, or blue band is missing from the scene folder.
    """
    red = resolve_band(scene_dir, "B04")
    green = resolve_band(scene_dir, "B03")
    blue = resolve_band(scene_dir, "B02")
    if red is None or green is None or blue is None:
        return None
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.transform import array_bounds
    from rasterio.warp import transform as warp_transform

    with rasterio.open(red) as source:
        red_array = source.read(1).astype(np.float64)
        transform = source.transform
        crs = source.crs
        height, width = source.height, source.width
    with rasterio.open(green) as source:
        green_array = source.read(1).astype(np.float64)
    with rasterio.open(blue) as source:
        blue_array = source.read(1).astype(np.float64)
    if green_array.shape != red_array.shape or blue_array.shape != red_array.shape or crs is None:
        return None
    rgb = _stretch(np.stack([red_array, green_array, blue_array], axis=0))
    left, bottom, right, top = array_bounds(height, width, transform)
    longitudes, latitudes = warp_transform(crs, "EPSG:4326", [left, right, left, right], [bottom, bottom, top, top])
    bounds = (min(longitudes), min(latitudes), max(longitudes), max(latitudes))
    profile = {"driver": "PNG", "height": height, "width": width, "count": 3, "dtype": "uint8"}
    with MemoryFile() as memory:
        with memory.open(**profile) as dataset:
            dataset.write(rgb)
        return memory.read(), bounds


def _stretch(stack: np.ndarray) -> np.ndarray:
    scaled = np.zeros(stack.shape, dtype=np.uint8)
    for index in range(stack.shape[0]):
        band = stack[index]
        finite = band[np.isfinite(band)]
        if finite.size == 0:
            continue
        low, high = np.percentile(finite, [2, 98])
        if high <= low:
            high = low + 1.0
        stretched = np.clip((band - low) / (high - low), 0.0, 1.0)
        stretched[~np.isfinite(band)] = 0.0
        scaled[index] = np.round(stretched * 255).astype(np.uint8)
    return scaled
