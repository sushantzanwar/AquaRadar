"""Relative water-quality indexes from qda_modelos, clipped to water pixels."""

from __future__ import annotations

import numpy as np


class IndicatorBackendMissing(RuntimeError):
    pass


def _mask(array: np.ndarray, water: np.ndarray) -> np.ndarray:
    values = np.squeeze(np.asarray(array, dtype=np.float64))
    if values.shape != water.shape:
        raise ValueError(f"indicator shape {values.shape} does not match water mask {water.shape}")
    return np.where(water, values, np.nan)


def relative_indicators(bands: dict[str, np.ndarray], water: np.ndarray) -> tuple[dict[str, np.ndarray], list[str]]:
    try:
        from qda_modelos.total_suspended_solids_turbidity import miller_mckee_2004
        from qda_modelos.water_transparency import giardino_et_al_2001
    except ImportError as exc:
        raise IndicatorBackendMissing("qda_modelos is not installed") from exc

    reasons: list[str] = []
    turbidity = _mask(miller_mckee_2004(bands["B04"].astype(np.float64)), water)
    transparency = _mask(giardino_et_al_2001(bands["B03"].astype(np.float64), bands["B02"].astype(np.float64)), water)
    indicators = {"turbidity": turbidity, "transparency": transparency}
    if "B05" in bands and "B06" in bands:
        from qda_modelos.chlorophylla import dallolmo_gitelson_rundquist_2003

        chlorophyll = dallolmo_gitelson_rundquist_2003(
            bands["B06"].astype(np.float64),
            bands["B05"].astype(np.float64),
            bands["B04"].astype(np.float64),
        )
        indicators["chlorophyll"] = _mask(chlorophyll, water)
    else:
        reasons.append("missing_red_edge_bands")
    return indicators, reasons
