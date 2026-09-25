"""Full-resolution before/after difference of two relative-index rasters."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def write_raster_diff(before: Path, after: Path, destination: Path) -> float | None:
    """Write ``after - before`` and return the mean of finite pixels.

    Returns None when either raster is missing or the grids do not match.
    The difference stays a relative index, not a laboratory concentration.
    """
    if not before.is_file() or not after.is_file():
        return None
    import rasterio

    with rasterio.open(before) as left, rasterio.open(after) as right:
        if left.shape != right.shape or left.transform != right.transform:
            return None
        difference = right.read(1).astype(np.float64) - left.read(1).astype(np.float64)
        profile = left.profile.copy()
    finite = difference[np.isfinite(difference)]
    if finite.size == 0:
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    profile.update(driver="GTiff", dtype="float32", count=1, nodata=np.nan, compress="deflate")
    with rasterio.open(destination, "w", **profile) as dest:
        dest.write(difference.astype(np.float32), 1)
        dest.set_band_description(1, "relative index difference (date2 - date1)")
        dest.update_tags(
            unit="index",
            representation="relative_index_difference",
            lab_grade="false",
            disclaimer="Relative index difference only. Not a laboratory concentration.",
        )
    return float(np.mean(finite))
