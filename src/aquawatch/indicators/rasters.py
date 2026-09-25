"""GeoTIFF writer for a full-resolution relative indicator."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from aquawatch.indicators.compute import (
    INDICATOR_DISCLAIMER,
    INDICATOR_LAB_GRADE,
    INDICATOR_MODELS,
    INDICATOR_REPRESENTATION,
    INDICATOR_UNIT,
)


def affine_from_centers(x: np.ndarray, y: np.ndarray):
    from rasterio.transform import Affine

    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    dx = float(x[1] - x[0]) if x.size > 1 else 10.0
    dy = float(y[1] - y[0]) if y.size > 1 else -10.0
    return Affine(dx, 0.0, float(x[0] - dx / 2.0), 0.0, dy, float(y[0] - dy / 2.0))


def write_indicator_raster(path: Path, values: np.ndarray, transform, crs, *, name: str) -> None:
    """Write one float32 index raster. NoData is NaN. Tags say it is not lab-grade."""
    import rasterio

    path.parent.mkdir(parents=True, exist_ok=True)
    array = np.asarray(values, dtype=np.float32)
    profile = {
        "driver": "GTiff",
        "height": array.shape[0],
        "width": array.shape[1],
        "count": 1,
        "dtype": "float32",
        "transform": transform,
        "compress": "deflate",
        "nodata": np.nan,
    }
    if crs:
        profile["crs"] = crs
    with rasterio.open(path, "w", **profile) as dest:
        dest.write(array, 1)
        dest.set_band_description(1, f"{name} relative index")
        dest.update_tags(
            indicator=name,
            unit=INDICATOR_UNIT,
            representation=INDICATOR_REPRESENTATION,
            lab_grade=str(INDICATOR_LAB_GRADE).lower(),
            model=INDICATOR_MODELS[name],
            disclaimer=INDICATOR_DISCLAIMER,
        )
