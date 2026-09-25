"""SCL cloud and cloud-shadow mask inside the water-body AOI."""

from __future__ import annotations

import numpy as np

from aquawatch.geo.cloud_mask import INVALID_SCL, valid_pixel_mask

MIN_VALID_FRACTION = 0.60


def aoi_mask_from_reflectance(reflectance: np.ndarray) -> np.ndarray:
    """Pixels inside the clipped AOI. Exterior pixels are NaN after the loader clip."""
    return np.isfinite(reflectance)


def aoi_valid_fraction(scl: np.ndarray, aoi: np.ndarray) -> float:
    area = int(np.count_nonzero(aoi))
    if area == 0:
        return 0.0
    valid = valid_pixel_mask(scl) & aoi
    return float(np.count_nonzero(valid)) / float(area)


def scene_validity(scl: np.ndarray, aoi: np.ndarray, minimum: float = MIN_VALID_FRACTION) -> tuple[bool, float, np.ndarray]:
    """Return whether the scene is usable, the valid fraction, and the valid-pixel mask.

    Cloud, cloud shadow, cirrus, snow, saturation, and no-data SCL classes are invalid.
    A scene is insufficient when less than 60% of the AOI is valid.
    """
    valid = valid_pixel_mask(np.asarray(scl)) & np.asarray(aoi, dtype=bool)
    fraction = aoi_valid_fraction(scl, aoi)
    return fraction >= minimum, fraction, valid


def scl_classes_removed() -> set[int]:
    return set(INVALID_SCL)
