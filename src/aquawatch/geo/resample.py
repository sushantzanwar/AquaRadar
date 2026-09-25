"""Resample 20 m SWIR onto the 10 m reference grid."""

from __future__ import annotations

import numpy as np


def upsample_nearest(array: np.ndarray, factor: int) -> np.ndarray:
    if factor < 1:
        raise ValueError("upsample factor must be >= 1")
    if factor == 1:
        return array
    return np.repeat(np.repeat(array, factor, axis=0), factor, axis=1)


def grids_match(shape_a, shape_b) -> bool:
    return tuple(shape_a) == tuple(shape_b)


def resample_to_reference(source: np.ndarray, reference_shape: tuple[int, int], scale: int) -> np.ndarray | None:
    """Exact integer upsample when the 20 m grid is a clean divisor of the 10 m grid.

    Georeferenced reprojection is handled by the caller when this returns None.
    """
    scaled = upsample_nearest(source, scale)
    if grids_match(scaled.shape, reference_shape):
        return scaled
    return None


def reproject_to_reference(source, source_transform, source_crs, reference_shape, reference_transform, reference_crs):
    import rasterio
    from rasterio.warp import Resampling, reproject

    destination = np.empty(reference_shape, dtype=np.float32)
    reproject(
        source=source,
        destination=destination,
        src_transform=source_transform,
        src_crs=source_crs,
        dst_transform=reference_transform,
        dst_crs=reference_crs,
        resampling=Resampling.bilinear,
    )
    return destination
