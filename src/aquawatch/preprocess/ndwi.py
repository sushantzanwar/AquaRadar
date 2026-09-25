"""NDWI cross-check against the water-model mask."""

from __future__ import annotations

import numpy as np

DISAGREEMENT_LIMIT = 0.25


def ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    green = green.astype(np.float64)
    nir = nir.astype(np.float64)
    denom = green + nir
    with np.errstate(divide="ignore", invalid="ignore"):
        index = (green - nir) / denom
    return np.where(denom == 0, np.nan, index)


def ndwi_water(green: np.ndarray, nir: np.ndarray, threshold: float = 0.0) -> np.ndarray:
    index = ndwi(green, nir)
    return np.isfinite(index) & (index > threshold)


def disagreement_fraction(model_mask: np.ndarray, ndwi_mask: np.ndarray, valid: np.ndarray) -> float:
    """Share of the valid AOI where the model and NDWI water masks differ."""
    area = int(np.count_nonzero(valid))
    if area == 0:
        return 1.0
    differ = (model_mask.astype(bool) != ndwi_mask.astype(bool)) & valid
    return float(np.count_nonzero(differ)) / float(area)


def low_confidence(fraction: float, limit: float = DISAGREEMENT_LIMIT) -> bool:
    return fraction > limit
