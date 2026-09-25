"""SCL classes that cannot support a water-quality retrieval."""

from __future__ import annotations

import numpy as np

# Sentinel-2 L2A scene classification. Water (6), vegetation (4), bare (5),
# and unclassified (7) stay. Cloud, shadow, snow, saturation, and no-data go.
INVALID_SCL = {0, 1, 3, 8, 9, 10, 11}


def valid_pixel_mask(scl: np.ndarray) -> np.ndarray:
    return ~np.isin(scl, list(INVALID_SCL))


def valid_fraction(mask: np.ndarray) -> float:
    if mask.size == 0:
        return 0.0
    return float(np.count_nonzero(mask)) / float(mask.size)


def insufficient_data(fraction: float, cutoff: float) -> bool:
    return fraction < cutoff
