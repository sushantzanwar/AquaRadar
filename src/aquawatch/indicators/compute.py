"""qda_modelos indexes on valid water pixels, plus a grid of zone statistics.

Every value is a relative index. ``unit`` is ``index``. These are not
laboratory concentrations, NTU, or Secchi depths.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from aquawatch.geo.cloud_mask import valid_pixel_mask

INDICATOR_UNIT = "index"
INDICATOR_REPRESENTATION = "relative_index"
INDICATOR_LAB_GRADE = False
INDICATOR_DISCLAIMER = (
    "Relative index only. Not a laboratory concentration, NTU, or Secchi depth."
)
INDICATOR_MODELS = {
    "turbidity": "miller_mckee_2004",
    "chlorophyll": "dallolmo_gitelson_rundquist_2003",
    "transparency": "giardino_et_al_2001",
}

_BAND_ALIASES = {
    "B02": ("B02", "B2"),
    "B03": ("B03", "B3"),
    "B04": ("B04", "B4"),
    "B05": ("B05", "B5"),
    "B06": ("B06", "B6"),
}

Model = Callable[..., np.ndarray]


class IndicatorBackendMissing(RuntimeError):
    pass


def load_qda_models() -> dict[str, Model]:
    try:
        from qda_modelos.chlorophylla import dallolmo_gitelson_rundquist_2003
        from qda_modelos.total_suspended_solids_turbidity import miller_mckee_2004
        from qda_modelos.water_transparency import giardino_et_al_2001
    except ImportError as exc:
        raise IndicatorBackendMissing("qda_modelos is not installed") from exc
    return {
        "turbidity": miller_mckee_2004,
        "transparency": giardino_et_al_2001,
        "chlorophyll": dallolmo_gitelson_rundquist_2003,
    }


def valid_water_pixels(water_mask: np.ndarray, scl: np.ndarray, aoi: np.ndarray) -> np.ndarray:
    """Intersection of the water mask, clear SCL pixels, and the AOI."""
    water = np.asarray(water_mask).astype(bool)
    clear = valid_pixel_mask(np.asarray(scl))
    inside = np.asarray(aoi, dtype=bool)
    if water.shape != clear.shape or water.shape != inside.shape:
        raise ValueError("water mask, SCL, and AOI must share one shape")
    return water & clear & inside


def relative_indicators(
    bands: dict[str, np.ndarray],
    water: np.ndarray,
    models: dict[str, Model] | None = None,
) -> tuple[dict[str, np.ndarray], list[str]]:
    """Turbidity, transparency, and chlorophyll-a on ``water`` pixels only.

    Band keys may be ``B4`` or ``B04``. Chlorophyll-a needs the red-edge pair
    (B5 and B6). Pixels outside ``water`` are NaN.
    """
    selected = models or load_qda_models()
    reasons: list[str] = []
    red = _band(bands, "B04")
    green = _band(bands, "B03")
    blue = _band(bands, "B02")
    indicators = {
        "turbidity": _mask(selected["turbidity"](red), water),
        "transparency": _mask(selected["transparency"](green, blue), water),
    }
    if _present(bands, "B05") and _present(bands, "B06"):
        red_edge = _band(bands, "B05")
        nir_edge = _band(bands, "B06")
        chlorophyll = selected["chlorophyll"](nir_edge, red_edge, red)
        indicators["chlorophyll"] = _mask(chlorophyll, water)
    else:
        reasons.append("missing_red_edge_bands")
    return indicators, reasons


def grid_zone_ids(height: int, width: int, n_rows: int, n_cols: int) -> tuple[np.ndarray, dict[int, str]]:
    """Label every pixel with a regular grid cell id such as ``r0c1``."""
    if n_rows < 1 or n_cols < 1:
        raise ValueError("zone grid must be at least 1 by 1")
    if height < 1 or width < 1:
        raise ValueError("grid overlay needs a non-empty raster")
    zones = np.full((height, width), -1, dtype=np.int32)
    row_edges = np.linspace(0, height, n_rows + 1).astype(int)
    col_edges = np.linspace(0, width, n_cols + 1).astype(int)
    labels: dict[int, str] = {}
    index = 0
    for row in range(n_rows):
        row_start, row_stop = int(row_edges[row]), int(row_edges[row + 1])
        if row_stop <= row_start:
            continue
        for col in range(n_cols):
            col_start, col_stop = int(col_edges[col]), int(col_edges[col + 1])
            if col_stop <= col_start:
                continue
            zones[row_start:row_stop, col_start:col_stop] = index
            labels[index] = f"r{row}c{col}"
            index += 1
    return zones, labels


def zone_statistics(
    values: np.ndarray,
    zones: np.ndarray,
    labels: dict[int, str],
    indicator: str,
) -> list[dict]:
    """Mean and 90th percentile of finite water pixels in each grid cell."""
    if indicator not in INDICATOR_MODELS:
        raise KeyError(indicator)
    rows: list[dict] = []
    for index, zone_id in labels.items():
        sample = np.asarray(values, dtype=np.float64)[zones == index]
        finite = sample[np.isfinite(sample)]
        if finite.size == 0:
            continue
        rows.append(_labeled_row(zone_id, indicator, finite))
    return rows


def build_zone_series(
    bands: dict[str, np.ndarray],
    scl: np.ndarray,
    water_mask: np.ndarray,
    aoi: np.ndarray,
    n_rows: int,
    n_cols: int,
    models: dict[str, Model] | None = None,
) -> tuple[dict[str, np.ndarray], list[dict], list[str]]:
    """Full-resolution indexes and per-zone mean/p90 on valid water pixels."""
    water = valid_water_pixels(water_mask, scl, aoi)
    grids, reasons = relative_indicators(bands, water, models=models)
    zones, labels = grid_zone_ids(water.shape[0], water.shape[1], n_rows, n_cols)
    rows: list[dict] = []
    for name, values in grids.items():
        rows.extend(zone_statistics(values, zones, labels, name))
    return grids, rows, reasons


def _present(bands: dict[str, np.ndarray], canonical: str) -> bool:
    return any(name in bands for name in _BAND_ALIASES[canonical])


def _band(bands: dict[str, np.ndarray], canonical: str) -> np.ndarray:
    for name in _BAND_ALIASES[canonical]:
        if name in bands:
            return np.asarray(bands[name], dtype=np.float64)
    raise KeyError(canonical)


def _mask(array: np.ndarray, water: np.ndarray) -> np.ndarray:
    values = np.squeeze(np.asarray(array, dtype=np.float64))
    if values.shape != water.shape:
        raise ValueError(f"indicator shape {values.shape} does not match water mask {water.shape}")
    masked = np.where(np.asarray(water, dtype=bool), values, np.nan)
    masked = masked.astype(np.float64, copy=False)
    masked[~np.isfinite(masked)] = np.nan
    return masked


def _labeled_row(zone_id: str, indicator: str, finite: np.ndarray) -> dict:
    return {
        "zone_id": zone_id,
        "indicator": indicator,
        "mean": float(np.mean(finite)),
        "p90": float(np.percentile(finite, 90)),
        "pixel_count": int(finite.size),
        "unit": INDICATOR_UNIT,
        "representation": INDICATOR_REPRESENTATION,
        "lab_grade": int(INDICATOR_LAB_GRADE),
        "model": INDICATOR_MODELS[indicator],
        "disclaimer": INDICATOR_DISCLAIMER,
    }
