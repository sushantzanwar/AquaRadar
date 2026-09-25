"""Resample SWIR, mask clouds, clip to the AOI, and gate thin scenes."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from aquawatch.geo.clip import apply_aoi, load_features, rasterize_aoi
from aquawatch.geo.cloud_mask import insufficient_data, valid_fraction, valid_pixel_mask
from aquawatch.geo.resample import reproject_to_reference, resample_to_reference
from aquawatch.pipeline.ingest import BandStack


@dataclass
class PreprocessResult:
    status: str
    reason: str | None
    confidence: float
    confidence_reasons: list[str] = field(default_factory=list)
    bands: dict[str, np.ndarray] | None = None
    valid: np.ndarray | None = None
    transform: object | None = None
    crs: object | None = None
    pixel_area_m2: float = 100.0
    profile: dict | None = None


def pixel_area_m2(transform, crs, fallback: float) -> tuple[float, list[str]]:
    width = abs(float(transform.a))
    height = abs(float(transform.e))
    crs_text = str(crs).upper() if crs is not None else ""
    geographic = "EPSG:4326" in crs_text or "GEOGCS" in crs_text or "WGS 84" in crs_text
    if geographic or width < 1:
        # Degree-sized pixels. Approximate metres at the equator of the transform origin.
        lat = float(transform.f)
        metres_lat = 111_320.0
        metres_lon = 111_320.0 * math.cos(math.radians(lat))
        area = width * metres_lon * height * metres_lat
        return abs(area), ["pixel_area_from_transform"]
    return width * height, []


def preprocess_stack(stack: BandStack, boundary_path, *, swir_scale: int, min_valid_fraction: float, fallback_area: float) -> PreprocessResult:
    reference = stack.reference()
    bands = {name: array for name, array in stack.arrays.items()}
    reasons: list[str] = []
    for swir in ("B11", "B12", "SCL", "B05", "B06"):
        if swir not in bands:
            continue
        aligned = resample_to_reference(bands[swir], reference.shape, swir_scale)
        if aligned is None:
            if bands[swir].shape == reference.shape:
                aligned = bands[swir]
            else:
                try:
                    aligned = reproject_to_reference(
                        bands[swir],
                        stack.transforms[swir],
                        stack.crs,
                        reference.shape,
                        stack.transforms["B02"],
                        stack.crs,
                    )
                except Exception:
                    return PreprocessResult(
                        status="unusable",
                        reason=f"swir_not_aligned:{swir}",
                        confidence=0.0,
                        confidence_reasons=["swir_not_aligned"],
                    )
        bands[swir] = aligned

    features = load_features(boundary_path)
    if not features:
        return PreprocessResult(
            status="unusable",
            reason="missing_boundary",
            confidence=0.0,
            confidence_reasons=["missing_boundary"],
        )
    try:
        inside = rasterize_aoi(features, reference.shape, stack.transforms["B02"])
    except Exception as exc:
        return PreprocessResult(
            status="geo_backend_missing",
            reason=f"rasterize_failed:{exc.__class__.__name__}",
            confidence=0.0,
            confidence_reasons=["geo_backend_missing"],
        )
    valid = apply_aoi(valid_pixel_mask(bands["SCL"]), inside)
    fraction = valid_fraction(valid)
    if insufficient_data(fraction, min_valid_fraction):
        return PreprocessResult(
            status="insufficient_data",
            reason=f"valid_fraction:{fraction:.3f}",
            confidence=0.0,
            confidence_reasons=["insufficient_data"],
            valid=valid,
            transform=stack.transforms["B02"],
            crs=stack.crs,
        )
    area, area_reasons = pixel_area_m2(stack.transforms["B02"], stack.crs, fallback_area)
    reasons.extend(area_reasons)
    if not area_reasons:
        area = fallback_area if abs(area - fallback_area) < 1 else area
    return PreprocessResult(
        status="ok",
        reason=None,
        confidence=1.0,
        confidence_reasons=reasons,
        bands=bands,
        valid=valid,
        transform=stack.transforms["B02"],
        crs=stack.crs,
        pixel_area_m2=area,
        profile=stack.profile,
    )
