"""Paint a synthetic plume onto a copy of a cached scene."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np


def paint_disk(array: np.ndarray, row: int, col: int, radius_px: float, magnitude: float) -> np.ndarray:
    painted = array.astype(np.float64).copy()
    if radius_px <= 0:
        return painted
    height, width = painted.shape
    yy, xx = np.ogrid[:height, :width]
    distance = np.sqrt((yy - row) ** 2 + (xx - col) ** 2)
    falloff = np.clip(1.0 - distance / radius_px, 0, 1)
    painted += magnitude * falloff
    return painted


DRIVING_BANDS = {
    "turbidity": ("B04", "B4.tif", "B04.tif"),
    "transparency": ("B02", "B2.tif", "B02.tif"),
    "chlorophyll": ("B05", "B5.tif", "B05.tif"),
}


def copy_scene(source: Path, destination: Path) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    return destination


def _band_file(scene: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        path = scene / name
        if path.is_file():
            return path
    return None


def inject_plume(scene: Path, *, indicator: str, row: int, col: int, radius_px: float, magnitude: float) -> str:
    """Modify the copied scene in place. Returns the band that was painted."""
    import rasterio

    spec = DRIVING_BANDS[indicator]
    path = _band_file(scene, spec[1:])
    if path is None:
        raise FileNotFoundError(spec[0])
    with rasterio.open(path) as source:
        array = np.squeeze(source.read(1))
        profile = source.profile
    painted = paint_disk(array, row, col, radius_px, magnitude)
    profile.update(dtype="float32")
    with rasterio.open(path, "w", **profile) as dest:
        dest.write(painted.astype(np.float32), 1)
    return spec[0]
